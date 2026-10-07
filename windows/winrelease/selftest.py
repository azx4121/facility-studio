"""Exercise the delivered EXE, native Tk, resources and actual GUI workflows."""

import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import traceback


def run(destination):
    checks = []

    def check(name, action):
        print("Checking: " + name, flush=True)
        try:
            if action() is False:
                raise AssertionError(name)
            checks.append({"name": name, "passed": True})
        except Exception:
            checks.append(
                {"name": name, "passed": False, "detail": traceback.format_exc()}
            )

    import numpy as np
    import matplotlib
    from PIL import Image, ImageGrab
    import tkinter as tk
    from facility_studio import __version__
    from facility_studio.engine import calculate
    from facility_studio.schema import default_project
    from facility_studio.simple_schema import defaults
    from facility_studio.simple_engines import calculate_tool
    from facility_studio.equipment_io import (
        export_template,
        load_equipment,
        EquipmentImportError,
    )
    from facility_studio.equipment_analysis import analyze_equipment
    from facility_studio.equipment_schema import SCHEMAS, SYSTEMS, example
    from facility_studio.ui_common import is_keypad_decimal
    from types import SimpleNamespace

    runtime = Path(getattr(sys, "_MEIPASS", ""))
    check(
        "Frozen standalone Windows x64 executable",
        lambda: sys.platform == "win32"
        and getattr(sys, "frozen", False)
        and platform.machine().upper() in ("AMD64", "X86_64"),
    )
    check(
        "Bundled CPython 3.13 runtime",
        lambda: sys.version_info[:2] == (3, 13)
        and (runtime / "python313.dll").is_file(),
    )
    check(
        "Application loaded from bundle",
        lambda: Path(__import__("facility_studio").__file__)
        .resolve()
        .is_relative_to(runtime.resolve()),
    )
    check(
        "No external Python environment",
        lambda: Path(sys.prefix).resolve().is_relative_to(runtime.resolve()),
    )
    check(
        "NumPy native extension",
        lambda: math.isclose(float(np.dot([1, 2], [3, 4])), 11),
    )
    check(
        "Pillow native extension",
        lambda: Image.new("RGB", (2, 2)).resize((4, 4)).size == (4, 4),
    )
    for name in (
        "LICENSE",
        "LICENSE_GUIDE.md",
        "LICENSE_LEGACY_MIT",
        "THIRD_PARTY_NOTICES.md",
        "THIRD_PARTY_LICENSES.txt",
    ):
        check("Bundled notice: " + name, lambda item=name: (runtime / item).is_file())
    check("Full engineering defaults", lambda: bool(calculate(default_project())))
    for tool in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):
        check(
            "Independent calculation: " + tool,
            lambda name=tool: bool(calculate_tool(name, defaults(name))),
        )
    check(
        "Windows keypad decimal recognized",
        lambda: is_keypad_decimal(
            SimpleNamespace(keysym="Delete", keycode=110), "win32"
        ),
    )
    check(
        "Normal Delete remains Delete",
        lambda: not is_keypad_decimal(
            SimpleNamespace(keysym="Delete", keycode=46), "win32"
        ),
    )

    with tempfile.TemporaryDirectory(prefix="FacilityStudio設備 ") as directory:
        template = Path(directory) / "設備 範本.xlsx"
        check(
            "Unicode path Excel export",
            lambda: (export_template(template), template.is_file())[1],
        )
        check(
            "Seven Excel worksheets load",
            lambda: len(load_equipment(template)["systems"]) == 7,
        )

        def disabled():
            try:
                analyze_equipment(load_equipment(template))
            except EquipmentImportError:
                return True
            return False

        check("Disabled template never fabricates demand", disabled)
        for system in SYSTEMS:
            path = Path(directory) / (system + " 設備.csv")
            row = example(system)
            row["enabled"] = 1
            schema = SCHEMAS[system]
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([column["label"] for column in schema])
                writer.writerow([row[column["key"]] for column in schema])
            check(
                "Active equipment analysis: " + system,
                lambda source=path, name=system: bool(
                    analyze_equipment(load_equipment(source, name))
                ),
            )

    callback_errors = []
    # Acceptance uses temporary application data, preserving existing projects.
    with tempfile.TemporaryDirectory(prefix="FacilityStudioGui-") as directory:
        old_storage = os.environ.get("LOCALAPPDATA")
        old_preferences = os.environ.get("FACILITY_STUDIO_PREFERENCES")
        os.environ["FACILITY_STUDIO_PREFERENCES"] = str(Path(directory) / "preferences.json")
        from facility_studio import i18n
        i18n.set_language("zh-Hant", persist=False)
        os.environ["LOCALAPPDATA"] = directory
        root = tk.Tk()

        def callback_error(*details):
            callback_errors.append("".join(traceback.format_exception(*details)))

        root.report_callback_exception = callback_error

        def pump():
            started = time.monotonic()
            root.after(200, root.quit)
            root.mainloop()
            if time.monotonic() - started > 5:
                raise AssertionError("Native GUI event processing stalled")

        try:
            from facility_studio.simple_desktop import SimpleToolsApp

            app = SimpleToolsApp(root)
            root.geometry("1100x760+0+0")
            pump()
            check(
                "Native Windows Tk window system",
                lambda: root.tk.call("tk", "windowingsystem") == "win32",
            )
            check("Application icon resources", lambda: bool(root._app_icon))
            for name in (
                "electrical",
                "duct",
                "gas",
                "lighting",
                "water",
                "air",
                "units",
            ):

                def open_tool(tool=name):
                    app.show_tool(tool)
                    pump()
                    return app.active_page().result is not None

                check("Live GUI: " + name, open_tool)
            check(
                "Equipment import window",
                lambda: app.open_equipment().win.winfo_exists() == 1,
            )
            workbench = app.open_workbench()
            root.report_callback_exception = callback_error
            workbench.root.report_callback_exception = callback_error
            pump()
            check(
                "Full engineering workbench calculates",
                lambda: workbench.result is not None,
            )
            for index in range(9):

                def open_page(page=index):
                    workbench.show_page(page)
                    pump()
                    return workbench.pages[page].winfo_ismapped() == 1

                check("Workbench page: " + str(index), open_page)
            from facility_studio.language_acceptance import run as check_languages

            check_languages(root, app, workbench, check, pump, destination)
            from facility_studio.tutorial_acceptance import run as check_tutorial

            check_tutorial(root, app, workbench, check, pump)
            check("Native GUI heartbeat", lambda: (pump(), True)[1])
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            figure = Figure(figsize=(2, 2))
            figure.add_subplot().plot([0, 1], [0, 1])
            canvas = FigureCanvasTkAgg(figure, master=root)
            check("Native Matplotlib TkAgg drawing", lambda: (canvas.draw(), True)[1])
            check("No GUI callback exceptions", lambda: not callback_errors)
            # Best effort screenshots are evidence; display size is runner-dependent.
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                workbench.root.withdraw()
                root.deiconify()
                app.show_tool("electrical")
                pump()
                ImageGrab.grab().save(destination.with_name("Windows_Electrical.png"))
                app.show_tool("air")
                pump()
                ImageGrab.grab().save(destination.with_name("Windows_Air.png"))
            except Exception:
                print("Screenshot capture unavailable: " + traceback.format_exc())
            from unittest.mock import patch

            with patch("tkinter.messagebox.askyesnocancel", return_value=False):
                app.close()
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass
            if old_preferences is None:
                os.environ.pop("FACILITY_STUDIO_PREFERENCES", None)
            else:
                os.environ["FACILITY_STUDIO_PREFERENCES"] = old_preferences
            if old_storage is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_storage

    result = {
        "version": __version__,
        "revision": "win.2",
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version,
        "numpy": np.__version__,
        "matplotlib": matplotlib.__version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "offline_network_audit": os.environ.get("FACILITY_TEST_BLOCK_NETWORK") == "1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
    }
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2
