"""Small native-runtime acceptance, executed identically on both architectures."""

import json
import math
from pathlib import Path
import platform
import sys
import tempfile


def run(destination):
    from .engineering_verification import (
        BUILD,
        compare_defaults,
        pipe_calculate,
        convert_units,
        export_report,
    )
    from .feed_review_preview import PIPE_DEFAULTS, VerificationWindow
    from .sandbox_ui import install_menus
    import tkinter as tk

    checks = []

    def check(name, fn):
        try:
            if not fn():
                raise AssertionError(name)
            checks.append({"name": name, "passed": True})
        except Exception as error:
            checks.append({"name": name, "passed": False, "error": str(error)})

    ahu = compare_defaults()
    pipe = pipe_calculate(PIPE_DEFAULTS)
    check("四個執行套件皆可載入", lambda: len(ahu["versions"]) == 4)
    check(
        "AHU 數值門檻與工程狀態分開",
        lambda: (
            ahu["numerical_summary"]["outside_limit"] == 0
            and ahu["model_quality"]["status"] == "未達條件"
        ),
    )
    check(
        "水管壓損與熱物性有限",
        lambda: (
            math.isfinite(pipe["total_pa"])
            and pipe["total_pa"] > 0
            and 990 < pipe["rho_kg_m3"] < 1005
        ),
    )
    check("溫度換算", lambda: abs(convert_units(0, "溫度", "°C")["°F"] - 32) < 1e-9)
    parallel = pipe_calculate({**PIPE_DEFAULTS, "flow_lpm": "200", "runs": "2"})
    check(
        "並聯總流量依支數分流",
        lambda: abs(parallel["total_pa"] - pipe["total_pa"]) < 1e-8,
    )
    root = tk.Tk()
    root.withdraw()
    install_menus(root)
    view = VerificationWindow(root)
    try:
        root.update()
        if sys.platform == "darwin":
            from .sandbox_native_menu import application_menu_titles

            check(
                "原生應用程式選單繁體中文",
                lambda: (
                    bool(application_menu_titles())
                    and not any(
                        title.startswith(
                            ("Preferences", "Services", "Hide ", "Quit ", "Show All")
                        )
                        for title in application_menu_titles()
                    )
                ),
            )
        else:
            menu = root._sandbox_menu
            titles = [
                menu.entrycget(i, "label")
                for i in range(menu.index("end") + 1)
                if menu.type(i) == "cascade"
            ]
            check(
                "原生應用程式選單繁體中文",
                lambda: {"檔案", "編輯", "視窗", "說明"}.issubset(titles),
            )
        check("三個功能分頁", lambda: len(view.nb.tabs()) == 3)
        check(
            "工程品質原因可見",
            lambda: "工程品質明細" in view.texts["ahu"].get("1.0", "end"),
        )
        view.nb.select(1)
        root.update()
        view.run("pipe", lambda: pipe_calculate(view.pipe_data()))
        check("水管介面完成運算", lambda: "pipe" in view.results)
        view.pipe_vars["id_mm"].set("0")
        view.run("pipe", lambda: pipe_calculate(view.pipe_data()))
        check("無效輸入清除舊結果", lambda: "pipe" not in view.results)
        with tempfile.TemporaryDirectory() as d:
            for ext in ("txt", "json", "html"):
                path = Path(d) / ("驗證報告." + ext)
                check(
                    "匯出 " + ext,
                    lambda p=path: bool(export_report(ahu, p)) and p.stat().st_size > 0,
                )
        for size in ("1120x820", "720x520"):
            view.win.geometry(size)
            root.update()
            check(
                "視窗尺寸 " + size,
                lambda: (
                    view.win.winfo_width() >= 720 and view.win.winfo_height() >= 520
                ),
            )
        from .simple_desktop import SimpleToolsApp
        app = SimpleToolsApp(root)
        app.show_tool("water")
        water = app.active_page()
        water.variables["flow"].set("350")
        host = app.open_engineering_verification("pipe", carry_water=True)
        embedded = app.verification
        app.calculate_active()
        check("檢核中心嵌入主畫面", lambda: host.winfo_toplevel() is root and app.verification_active)
        check("冷熱水帶入並計算", lambda: abs(embedded.results["pipe"]["flow_m3s"] - 350/60000) < 1e-12)
        water.variables["flow"].set("700")
        app.calculate_active()
        check("上游變更禁止採用舊資料", lambda: "pipe" not in embedded.results)
        app.open_engineering_verification("units")
        embedded.group.set("溫度")
        embedded.value.set("0")
        app.calculate_active()
        check("主畫面快捷計算使用目前功能", lambda: abs(embedded.results["units"]["values"]["°F"] - 32) < 1e-9)
        app.open_engineering_verification("pipe")
        root.geometry("1000x760")
        root.deiconify()
        root.update()
        check("小視窗保留可見匯出按鈕", lambda: embedded.export_button.winfo_ismapped()
              and embedded.export_button.winfo_rooty() + embedded.export_button.winfo_height()
              <= root.winfo_rooty() + root.winfo_height())
    finally:
        view.win.destroy()
        root.destroy()
    result = {
        "build": BUILD,
        "architecture": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "offline_network_audit": __import__("os").environ.get(
            "FACILITY_TEST_BLOCK_NETWORK"
        )
        == "1",
        "checks": checks,
        "passed": all(x["passed"] for x in checks),
        "engineering_approval": False,
    }
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1
