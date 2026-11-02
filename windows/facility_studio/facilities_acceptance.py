"""Executable acceptance for the requested simplified workflows, synthetic data only."""
import json
import os
from pathlib import Path
import sys


def run(destination):
    from .localized_tk import tk
    from .simple_desktop import SimpleToolsApp
    from .simple_schema import defaults
    from .simple_engines import calculate_tool
    from . import i18n
    from .version import BUILD_VERSION
    i18n.set_language('zh-Hant', persist=False)
    checks = []

    def check(name, condition):
        checks.append(dict(name=name, passed=bool(condition)))
        if not condition:
            raise AssertionError(name)

    root = tk.Tk()
    app = SimpleToolsApp(root)
    try:
        app.open_pv()
        root.update()
        check('PV 留在簡易工具，未建立完整工作台', app.current == 'vacuum' and app.workbench is None)
        pv = app.active_page()
        before = pv.result['pressure_pa']
        pv.variables['vacuum_unit'].set('kPa(abs)')
        pv.calculate()
        check('真空換單位保持原絕壓', abs(pv.result['pressure_pa'] - before) < 1e-7)
        app.open_engineering_verification('units')
        root.update()
        check('工程單位換算合併至同一頁', app.current == 'units' and app.verification_host is None)
        app.open_engineering_verification('pipe')
        check('材料與液體計算留在簡易頁', app.current == 'liquid' and app.workbench is None)
        liquid = app.active_page()
        liquid.variables['geometry'].set('指定外徑及管壁')
        liquid.variables['outer_mm'].set('16')
        liquid.variables['wall_mm'].set('2')
        liquid.calculate()
        check('高流速在同頁警告', liquid.result['velocity_mps'] > 10 and any('流速' in w for w in liquid.result['warnings']))
        liquid.variables['liquid'].set('鹽酸')
        liquid.calculate()
        check('化學液體缺物性不沿用水', liquid.result is None)
        for key, value in dict(liquid_rho='1100', liquid_mu='.003', liquid_cp='3.7', property_reference='合成案例20°C20wt%').items():
            liquid.variables[key].set(value)
        liquid.calculate()
        check('具來源之液體物性參與計算', liquid.result is not None and liquid.result['rho'] == 1100)
        liquid.variables['liquid_t'].set('40')
        liquid.calculate()
        check('變更物性工況必須重新確認來源', liquid.result is None and not liquid.variables['property_reference'].get())
        app.show_tool('cleanroom')
        clean = app.active_page()
        clean.variables['oa_cmh'].set('3000')
        clean.calculate()
        r = clean.result
        check('GEMINI 案例總風不重複', r['ffu_total_cmh'] == 18000 and r['dcc_cmh'] == 15000)
        check('超額外氣洩壓量明列', r['relief_required_cmh'] == 2700 and abs(r['airflow_balance_residual_cmh']) < 1e-8)
        app.show_tool('duct')
        duct = app.active_page()
        check('風管板厚聯動至選管結果', duct.result['rectangle']['sheet']['thickness_mm'] > 0)
        app.show_tool('liquid')
        liquid.reset()
        liquid.variables['insulate'].set('1')
        liquid.variables['liquid_t'].set('7')
        liquid.calculate()
        check('液體頁保溫聯動成功', liquid.result is not None and liquid.result['insulation']['feasible'])
        app.show_tool('water')
        water = app.active_page()
        water.variables['insulate'].set('1')
        water.variables['insulation_outer_mm'].set('48.3')
        water.calculate()
        check('冷熱水採用確認之外徑作保溫', water.result is not None and water.result['insulation']['feasible'])
        water.variables['flow'].set('200')
        water.calculate()
        check('變更自動選管條件使舊外徑失效', water.result is None and not water.variables['insulation_outer_mm'].get())
        water.reset()
        water.variables['flow'].set('350')
        water.calculate()
        app.open_engineering_verification('pipe', carry_water=True)
        liquid = app.active_page()
        check('冷熱水流量帶入液體原頁', liquid.result is not None and liquid.result['flow_lpm'] == 350 and app.verification_host is None)
        water.variables['flow'].set('700')
        import tempfile
        with tempfile.TemporaryDirectory(prefix='facility-stale-export-') as folder:
            report = Path(folder) / 'stale.txt'
            check('上游水量改動阻擋過期液體匯出', liquid.upstream_stale and not app.export_result(report) and not report.exists())
        water.calculate()
        check('明確重新帶入後液體流量恢復', liquid.import_upstream('water') and liquid.result['flow_lpm'] == 700)
        for tool in ('vacuum', 'liquid', 'units', 'cleanroom', 'duct'):
            app.show_tool(tool)
            root.update()
            check(tool + ' 計算與匯出按鈕可用', app.calc_button.winfo_ismapped())
            if os.environ.get('FACILITY_CAPTURE_SYNTHETIC_UI') == '1':
                from PIL import ImageGrab
                Path(destination).parent.mkdir(parents=True, exist_ok=True)
                ImageGrab.grab().save(Path(destination).parent / (tool + '_簡易工具.png'))
        for tool in ('water','air','electrical','pumps'):
            check(tool + ' 既有核心仍可計算', calculate_tool(tool, defaults(tool))['tool'] == tool)
    finally:
        root.destroy()
    output = dict(version=BUILD_VERSION, frozen=bool(getattr(sys, 'frozen', False)), checks=checks,
                  passed=all(x['passed'] for x in checks), certification=False)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if output['passed'] else 1
