"""Acceptance executed inside the delivered executable, with synthetic data."""
import copy
import json
import os
from pathlib import Path
import platform
import sys


def run(destination):
    from .schema import default_project
    from .engine import calculate
    from .ahu_schema import NM_DEFAULTS
    from .ahu_engine import nm_calculate
    from .quick_tools import convert_all
    from .reports import report, nm_report
    from .simple_schema import defaults
    from .simple_engines import calculate_tool
    from .engineering_backends import manifest
    from .version import BUILD_VERSION
    checks = []
    def check(name, passed):
        checks.append(dict(name=name, passed=bool(passed)))
    check("五套工程計算庫可載入", len(manifest()) == 5)
    # Exercise the actual supported spreadsheet workflow after excluding
    # pandas' unused optional Arrow/Parquet binaries from native packaging.
    import tempfile
    from .equipment_io import export_template, load_equipment
    with tempfile.TemporaryDirectory(prefix="facility-fusion-excel-") as folder:
        workbook = Path(folder) / "合成設備需求.xlsx"
        export_template(workbook)
        check("交付程式可匯出再讀取七表 Excel", len(load_equipment(workbook)["systems"]) == 7)
    check("絕對溫度零點", abs(convert_all("溫度", 0, "°C")["°F"] - 32) < 1e-9)
    check("溫差沒有零點位移", abs(convert_all("溫度差（升溫／降溫）", 5, "°C差")["°F差"] - 9) < 1e-9)
    conditions = []
    for temperature in (5, 10, 40, 80):
        data = defaults("water")
        data.update(property_source="CoolProp 純水溫壓", water_t=str(temperature), water_p="300",
                    flow="221.75", velocity="2", sizing_basis="流速與摩擦壓損", friction_limit="350")
        water = calculate_tool("water", data)
        props = water["fluid_properties"]
        expected = 221.75 / 60000 * props["rho"] * props["cp"] * 5
        check(f"{temperature}°C 純水熱量與實際物性一致", abs(water["load_kw"] - expected) < 1e-8)
        check(f"{temperature}°C 雙條件自動選管", water["pressure"]["friction_pa_m"] <= 350 and water["pipe"]["velocity_mps"] <= 2)
        conditions.append(dict(temperature_c=temperature, **water))
    project = default_project()
    project["inputs"].update(chw_property_source="CoolProp 純水溫壓", chw_property_t="10", chw_property_p="300",
                              water_sizing_basis="流速與摩擦壓損", water_friction_limit="350",
                              np_auto_mode="自動加總本案（手填為額外負荷）", main_fan_input_kw="3",
                              ffu_input_w="80", main_reheat_source="電熱", main_humidifier_input_kw="10")
    before = copy.deepcopy(project)
    result = calculate(project)
    check("主案計算不改寫原輸入", project == before)
    check("重算不重複累加 NP", result["electric"] == calculate(project)["electric"])
    check("NP 設備電氣輸入已連動", result["electric"]["NP"]["kw"] > 3)
    check("主案水路直接使用 CoolProp", "HEOS" in result["water"]["CHW"]["fluid_properties"]["source"])
    check("工程報告顯示容量邊界並省略套件品牌", "水路供冷容量包絡" in report(result) and all(x not in report(result) for x in ("PsychroLib", "python-hvac", "fluids", "CoolProp", "Pint")))
    ahu = nm_calculate(dict(NM_DEFAULTS, flow="850", summer_t="26", summer_rh="50", sa_t="15", sa_rh="85",
                            coil_rating_mode="幾何 ε-NTU（python-hvac）"))
    rating = ahu["summer"]["coil_rating"]
    if getattr(sys, "frozen", False):
        check("交付程式未載入未使用的 IAPWS 套件", not any(k == "iapws" or k.startswith("iapws.") for k in sys.modules))
    check("AHU 直接執行幾何 ε-NTU", "error" not in rating and 4.5 < rating["capacity_kw"] < 5)
    check("盤管空氣側熱平衡", abs(rating["air_balance_residual_kw"]) < .001)
    check("盤管兩側壓降", rating["air_dp_pa"] > 0 and rating["water_dp_pa"] > 0)
    check("幾何結果進入既有校核書", "C2 ε-NTU" in nm_report(ahu))
    from .localized_tk import tk
    from . import i18n
    from .desktop import DesktopApp
    from .fusion_settings import open_settings
    i18n.set_language("zh-Hant", persist=False)
    root = tk.Tk()
    app = DesktopApp(root)
    try:
        root.update()
        check("原生 GUI 有完整主案結果", app.result is not None)
        settings = open_settings(app)
        root.update()
        check("工程設定完整可編輯", all(k in settings.fusion_values for k in ("c2_bf_min", "winter_terminal_heat_source", "np_auto_mode", "chw_property_source")))
        settings.fusion_values["water_friction_limit"].set("350")
        settings.fusion_values["water_sizing_basis"].set("流速與摩擦壓損")
        settings.apply_fusion_settings()
        root.update()
        check("GUI 採用設定並重算", app.result is not None and app.snapshot()["inputs"]["water_friction_limit"] == "350")
        # Reopen verifies persistence in the live project, without touching a
        # pre-existing project file or the installed application's preferences.
        settings = open_settings(app)
        root.update()
        check("重新開啟設定保留採用值", settings.fusion_values["water_friction_limit"].get() == "350")
        settings.destroy()
        root.geometry("880x560")
        root.update()
        buttons = [w for w in _widgets(root) if w.winfo_class() in ("TButton", "Button") and "進階工程設定" in str(w.cget("text"))]
        check("最小視窗仍可開啟工程設定", len(buttons) == 1 and buttons[0].winfo_ismapped()
              and buttons[0].winfo_rootx() >= root.winfo_rootx()
              and buttons[0].winfo_rootx() + buttons[0].winfo_width() <= root.winfo_rootx() + root.winfo_width()
              and buttons[0].winfo_rooty() + buttons[0].winfo_height() <= root.winfo_rooty() + root.winfo_height())
        if os.environ.get("FACILITY_CAPTURE_SYNTHETIC_UI") == "1":
            # Opt-in only on the isolated CI desktop. Never capture the user's
            # locked screen, other applications, or private project contents.
            from PIL import ImageGrab
            target = Path(destination).parent
            target.mkdir(parents=True, exist_ok=True)
            ImageGrab.grab().save(target / "主工作台.png")
            settings = open_settings(app)
            root.update()
            for index, title in enumerate(("空調冬季", "水路選管", "NP用電")):
                settings.fusion_notebook.select(index)
                root.update()
                ImageGrab.grab().save(target / ("工程模型設定_" + title + ".png"))
            settings.destroy()
    finally:
        root.destroy()
    from .simple_desktop import SimpleToolsApp
    simple_root = tk.Tk()
    simple = SimpleToolsApp(simple_root)
    try:
        simple.show_tool("cleanroom")
        simple_root.update()
        page = simple.pages["cleanroom"]
        check("潔淨室基本畫面可直接輸入溫濕度", all(page.rows[k].winfo_ismapped() for k in ("room_t", "room_rh", "outdoor_t", "outdoor_rh")))
        page.variables["oa_cmh"].set("3000")
        page.variables["room_rh"].set("60")
        page.calculate(True)
        humid = page.result["mau"]["coil_condensate_kg_h"]
        page.variables["room_rh"].set("50")
        page.calculate(True)
        check("GUI 降低濕度目標增加除濕需求", page.result["mau"]["coil_condensate_kg_h"] > humid)
        ahu_window = page.open_cleanroom_ahu()
        simple_root.update()
        check("潔淨室可建立獨立 MAU 核對案", ahu_window is not None and ahu_window.result is not None and ahu_window.source_project_id == "")
        check("MAU 核對案保留乾空氣流率", abs(ahu_window.result["summer"]["mass"] - page.result["mau"]["mass_da_kg_s"]) < 1e-10)
        if os.environ.get("FACILITY_CAPTURE_SYNTHETIC_UI") == "1":
            from PIL import ImageGrab
            ahu_window.win.withdraw()
            simple_root.update()
            ImageGrab.grab().save(Path(destination).parent / "潔淨室溫濕度與除濕需求.png")
        ahu_window.win.destroy()
    finally:
        simple_root.destroy()
    from .candidate_acceptance import build_identity
    output = dict(**build_identity(), suite="fusion", version=BUILD_VERSION, python=platform.python_version(), platform=platform.platform(),
                  frozen=bool(getattr(sys, "frozen", False)), backends=manifest(), checks=checks,
                  passed=all(c["passed"] for c in checks), engineering_certification=False,
                  synthetic_water_conditions=conditions, ahu_rating=rating)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if output["passed"] else 1


def _widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from _widgets(child)
