"""Small native-runtime acceptance, executed identically on both architectures."""

import json
import math
from pathlib import Path
import platform
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
    root = tk.Tk()
    root.withdraw()
    install_menus(root)
    view = VerificationWindow(root)
    try:
        root.update()
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
    finally:
        view.win.destroy()
        root.destroy()
    result = {
        "build": BUILD,
        "architecture": platform.machine(),
        "checks": checks,
        "passed": all(x["passed"] for x in checks),
        "engineering_approval": False,
    }
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1
