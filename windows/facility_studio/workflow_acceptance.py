"""Independent field-workflow checks for source and the delivered Windows EXE."""
import copy
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
import traceback


def run(destination, gui=True):
    checks = []
    def check(name, condition):
        checks.append(dict(name=name, passed=bool(condition)))
        if not condition:
            raise AssertionError(name)
    def near(name, actual, expected):
        check(name, math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9))
    from .simple_engines import calculate_tool
    from .simple_schema import defaults
    from .simple_reports import tool_report
    from .errors import ValidationError
    from .grounding import equipment_pe
    from .engine import calculate
    from .schema import default_project
    from .services import upstream_values
    from .air_chart import chart_data
    from .version import BUILD_VERSION
    root = None
    errors = []
    report = dict(build=BUILD_VERSION, host=platform.platform(), python=sys.version,
                  frozen=bool(getattr(sys, "frozen", False)), checks=checks)
    try:
        lamp = defaults('lighting')
        lamp.update(area='8300', target='500', watts='12.5', mode='反算燈數')
        led = calculate_tool('lighting', lamp)
        lamp['lumen_mode'] = '燈具型錄流明'
        catalog = calculate_tool('lighting', lamp)
        check('8300 m2: 12.5 W x 100 lm/W gives 6917 fixtures', led['quantity'] == 6917)
        check('8300 m2: 4000 lm gives 2162 fixtures', catalog['quantity'] == 2162)
        near('LED lighting density W/m2', led['lighting_w_m2'], 6917*12.5/8300)
        near('Catalog lighting density W/m2', catalog['lighting_w_m2'], 2162*12.5/8300)
        near('Catalog implied efficacy is 320 lm/W', catalog['comparison']['catalog_efficacy'], 320)
        check('Mismatched lumens produce a visible diagnostic', len(catalog['warnings']) >= 1)
        for area in (1, 30, 1000, 8300):
            for efficacy in (80, 100, 150):
                i = defaults('lighting')
                i.update(area=str(area), efficacy=str(efficacy), lumens=str(40*efficacy), mode='反算燈數')
                a=calculate_tool('lighting',i)
                i['lumen_mode']='燈具型錄流明'
                b=calculate_tool('lighting',i)
                check(f'Equal lumens / equal count {area} {efficacy}', a['quantity']==b['quantity'])
        exported = tool_report(catalog,lamp)
        check('Lighting report contains both counts and W/m2', '6,917' in exported and '2,162' in exported and 'W/m²' in exported)
        patch=upstream_values('heat_loads',{'lighting':catalog},defaults('heat_loads'))
        near('Lighting area adoption',float(patch['area']),8300)
        near('Lighting density adoption',float(patch['lighting_w_m2']),2162*12.5/8300)
        heat=calculate_tool('heat_loads',dict(defaults('heat_loads'),**patch))
        near('Lighting heat conserves actual input power',heat['q_lighting_kw'],2162*12.5/1000)
        for breaker,size in ((20,2),(20.01,3.5),(30,3.5),(31,5.5),(60,5.5),(61,8),(100,8),
                             (101,14),(200,14),(201,22),(400,22),(401,38),(600,38),(800,50),
                             (1000,60),(1200,80),(1600,100),(2000,125),(2500,150),(3000,200),
                             (4000,250),(5000,325),(6300,400)):
            pe=equipment_pe(breaker,3)
            near(f'Table 93-2 breakpoint {breaker}',pe['pe_mm2'],size)
            check(f'Parallel raceways keep full PE size {breaker}',pe['pe_count']==3)
        check('Zero power has no PE demand',equipment_pe(0)['pe_count']==0)
        check('Beyond table is pending, not an invented size',equipment_pe(6301)['pe_mm2'] is None)
        for kw in (1,10,50,300,1000):
            d=defaults('electrical');d['power']=str(kw)
            e=calculate_tool('electrical',d)['selected']
            check(f'Electrical PE attached at {kw} kW',e['pe_mm2']==equipment_pe(e['nfb_a'])['pe_mm2'])
        main=default_project()
        clean=calculate(main)
        near('Single coil precooling water load is zero',clean['summer']['c1']['water_kw'],0)
        near('Single coil MCHW flow is zero',clean['water']['MCHW']['lpm'],0)
        draft=copy.deepcopy(main)
        draft['inputs'].update(chw1_in='unfinished',pre_t='unfinished',pre_rh='unfinished',chw1_dt='unfinished')
        same=calculate(draft)
        near('Inactive precoil drafts cannot affect cooling',same['summer']['c2']['water_kw'],clean['summer']['c2']['water_kw'])
        from .json_io import read_json_file
        # Historical cases explicitly keep two-coil settings; source shape unchanged.
        old=copy.deepcopy(main);old['inputs'].update(pre_mode='自動旁通因子估算',pre_t='18')
        dual=calculate(old)
        check('Dual coil option remains functional',dual['summer']['c1']['water_kw']>0)
        from .workspace_store import new_workspace,validate_workspace
        check('Workspace round trip preserves configuration',validate_workspace(new_workspace(old))['main']['inputs']==old['inputs'])
        air=calculate_tool('air',defaults('air'))
        a,b=air['state'],air['comparison_state']
        # Saturation pressures at 35 and 26 C independently tabulated by the existing ASHRAE correlation.
        def expected(t,rh,pws):
            w=.621945*(rh/100*pws)/(101325-rh/100*pws)
            return 1.006*t+w*(2501+1.86*t)
        near('Outdoor/room enthalpy difference',air['delta_h_kj_kg'],expected(35,60,5627.81944654024)-expected(26,50,3363.132388969139))
        lines=chart_data(a,b)
        for contour in lines['enthalpy_lines']:
            for t,w in contour['points'][::31]:
                near('Enthalpy contour independent equation',1.006*t+w/1000*(2501+1.86*t),contour['value'])
        patch=upstream_values('heat_loads',{'air':air},defaults('heat_loads'))
        near('Air delta h adoption',float(patch['oa_delta_h']),a['h']-b['h'])
        reverse=dict(air,delta_h_kj_kg=-1)
        try:
            upstream_values('heat_loads',{'air':reverse},defaults('heat_loads'))
        except ValidationError:
            check('Heating cannot masquerade as a cooling enthalpy difference',True)
        else:check('Heating cannot masquerade as a cooling enthalpy difference',False)
        h=defaults('heat_loads');h.update(area='8300',envelope_w_m2='unfinished')
        near('Area-only envelope estimate',calculate_tool('heat_loads',h)['q_envelope_kw'],166)
        h.update(envelope_mode='自訂熱負荷密度',envelope_w_m2='30')
        near('Custom envelope density remains available',calculate_tool('heat_loads',h)['q_envelope_kw'],249)
        h.update(envelope_mode='面積推估外牆／樓板',area='100')
        near('Geometric UA delta-T envelope',calculate_tool('heat_loads',h)['q_envelope_kw'],(120*1.6*9+100*3.8*4)/1000)
        if gui:
            with tempfile.TemporaryDirectory(prefix='facility-workflow-') as temp:
                os.environ['LOCALAPPDATA']=temp
                os.environ['FACILITY_STUDIO_PREFERENCES']=str(Path(temp)/'prefs.json')
                from .localized_tk import tk
                from .simple_desktop import SimpleToolsApp
                root=tk.Tk()
                app=SimpleToolsApp(root)
                root.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
                root.update()
                check('PV navigation is aligned with the other sidebar items',
                      app.pv_button.winfo_x()==app.nav['gas'].winfo_x() and app.pv_button.winfo_width()==app.nav['gas'].winfo_width()
                      and app.pv_button.winfo_height()==app.nav['gas'].winfo_height())
                def set_page(page,**values):
                    page.suspended=True
                    for k,v in values.items():page.variables[k].set(str(v))
                    page.suspended=False
                    page.previous=page.data();page.update_visibility();page.calculate();root.update()
                app.show_tool('lighting');light=app.active_page()
                set_page(light,**lamp)
                check('GUI reproduces the catalog count',light.result['quantity']==2162)
                app.show_tool('heat_loads');heat=app.active_page()
                check('Dedicated lighting transfer works',heat.import_upstream('lighting'))
                app.show_tool('air');airpage=app.active_page();root.update()
                check('Equal summary and chart halves',abs(airpage.output_scroll.winfo_height()-(airpage.air_chart.winfo_height()+8))<=1)
                check('Chart renders both states',bool(airpage.air_chart.find_withtag('comparison_point')))
                check('Chart renders enthalpy and wet-bulb contours',bool(airpage.air_chart.find_withtag('enthalpy')) and bool(airpage.air_chart.find_withtag('wetbulb')))
                app.show_tool('heat_loads')
                check('Dedicated air transfer works',heat.import_upstream('air'))
                check('Both upstream dependencies survive adoption',heat.upstream_sources=={'air','lighting'})
                before=[w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]
                workbench=app.open_workbench();root.update()
                root.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
                check('Workbench shares the same top-level',workbench.root is root)
                check('Opening workbench creates no Toplevel',[w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]==before)
                workbench.variables['project_name'].set('review-snapshot')
                for j in range(4):
                    app.show_simple_tools();root.update()
                    check(f'Simple result retained through switching {j}',light.result['quantity']==2162)
                    app.open_workbench();root.update()
                    check(f'Main input retained through switching {j}',workbench.variables['project_name'].get()=='review-snapshot')
                check('Single coil hides precooling water inputs',not workbench.form_rows['chw1_in'].winfo_manager())
                app.show_simple_tools();extra=app.open_extra_tools();root.update()
                check('Extra tools are embedded',extra.win.winfo_toplevel() is root and not isinstance(extra.win,tk.Toplevel))
                def popup(widget):
                    root.tk.call('ttk::combobox::Post',str(widget));root.update()
                    root.tk.call('ttk::combobox::Unpost',str(widget));root.update()
                for name in extra.allowed_tools:
                    extra.tool.set(name);extra.build();extra.calculate();root.update()
                    check('Additional calculator '+name,extra.result is not None)
                    popup(extra.selector)
                    for widget in extra.widgets.values():
                        if widget.winfo_class()=='TCombobox' and str(widget.cget('state'))=='readonly':
                            popup(widget)
                    check('Actual dropdown popdowns '+name,not errors)
                from .simple_schema import TOOLS
                for tool in TOOLS:
                    app.show_tool(tool);root.update()
                    for widget in app.active_page().widgets.values():
                        if widget.winfo_class()=='TCombobox' and widget.winfo_ismapped() and str(widget.cget('state'))=='readonly':
                            popup(widget)
                    check('Simple tool dropdowns '+tool,not errors)
                app.show_tool('air');airpage.variables['temperature_b'].set('27');root.update()
                check('Changing air marks adopted heat result stale',heat.upstream_stale and heat.result is None)
                root.geometry('1000x700');root.update()
                check('Narrow chart retains both markers',bool(airpage.air_chart.find_withtag('comparison_point')))
                check('Narrow layout preserves equal result heights',abs(airpage.output_scroll.winfo_height()-(airpage.air_chart.winfo_height()+8))<=1)
                kpi_bottom=max(box.winfo_rooty()+box.winfo_height() for box in airpage.result_box.boxes)
                check('All four calculation cards remain visible',kpi_bottom<=airpage.output_scroll.canvas.winfo_rooty()+airpage.output_scroll.canvas.winfo_height())
                graph_bottom=airpage.air_chart.winfo_rooty()+airpage.air_chart.winfo_height()
                viewport_bottom=airpage.output_frame.winfo_rooty()+airpage.output_frame.winfo_height()
                check('Entire chart is inside the visible viewport',graph_bottom<=viewport_bottom)
                check('No Tk callback exceptions',not errors)
                root.destroy();root=None
        report['passed']=True
    except Exception:
        report['passed']=False
        report['error']=traceback.format_exc()
    finally:
        if root is not None:
            root.destroy()
        report['check_count']=len(checks)
        report['callback_errors']=errors
        Path(destination).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['passed'] else 1
