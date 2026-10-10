"""Optional real-Mac acceptance check shipped with the application."""

from datetime import datetime, timezone
import csv
import faulthandler
import json
import math
import os
from pathlib import Path
import platform
import sys
import subprocess
import tempfile
import time
import traceback


def run():
    checks = []
    destination = Path.home() / "Library/Logs/Facility_Studio_V5_5"
    destination.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        faulthandler.dump_traceback_later(25, repeat=True)

    def check(name, action):
        print("Checking: " + name, flush=True)
        try:
            value = action()
            if value is False:
                raise AssertionError(name)
            checks.append({"name": name, "passed": True})
        except Exception:
            checks.append(
                {"name": name, "passed": False, "detail": traceback.format_exc()}
            )

    print("Loading native calculation and graphics libraries...", flush=True)
    import numpy as np
    import matplotlib
    from PIL import Image
    import tkinter as tk
    from facility_studio import __version__
    from facility_studio.schema import default_project
    from facility_studio.engine import calculate
    from facility_studio.simple_schema import defaults
    from facility_studio.simple_engines import calculate_tool
    from facility_studio.equipment_io import (
        load_equipment,
        export_template,
        EquipmentImportError,
    )
    from facility_studio.equipment_analysis import analyze_equipment
    from facility_studio.equipment_schema import SCHEMAS, SYSTEMS, example

    app_path = Path(sys.executable).resolve().parents[2]

    def native_signature_check():
        result = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return True

    check("Apple native deep signature verification", native_signature_check)

    check("Bundled CPython 3.13", lambda: sys.version_info[:2] == (3, 13))
    check("Native CPU supported", lambda: platform.machine() in ("arm64", "x86_64"))
    check(
        "NumPy native extension",
        lambda: math.isclose(float(np.dot([1.0, 2.0], [3.0, 4.0])), 11.0),
    )
    check(
        "Pillow native extension",
        lambda: Image.new("RGB", (2, 2)).resize((4, 4)).size == (4, 4),
    )
    check("Full engineering calculation", lambda: bool(calculate(default_project())))
    from facility_studio.inactive_acceptance import run_checks as check_inactive
    check("V557 complete-output inactive-field regression", lambda: check_inactive(random_repeats=0)["passed"])
    for tool in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):
        check(
            f"Independent tool: {tool}",
            lambda name=tool: bool(calculate_tool(name, defaults(name))),
        )
    with tempfile.TemporaryDirectory(prefix="FacilityStudioMac-") as directory:
        template = Path(directory) / "範本 空間.xlsx"
        check(
            "Export Excel template with Unicode path",
            lambda: (export_template(template), template.is_file())[1],
        )
        check(
            "Read all seven system worksheets",
            lambda: len(load_equipment(template)["systems"]) == 7,
        )

        def reject_disabled_template():
            document = load_equipment(template)
            assert all(
                int(row["cells"]["enabled"].value) == 0 for row in document["records"]
            )
            try:
                analyze_equipment(document)
            except EquipmentImportError:
                return True
            return False

        check(
            "Disabled template does not fabricate demand totals",
            reject_disabled_template,
        )
        for system in SYSTEMS:
            path = Path(directory) / f"實際設備 {system}.csv"
            schema = SCHEMAS[system]
            row = example(system)
            row["enabled"] = 1
            with path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([column["label"] for column in schema])
                writer.writerow([row[column["key"]] for column in schema])
            check(
                f"Active CSV equipment analysis: {system}",
                lambda source=path, name=system: bool(
                    analyze_equipment(load_equipment(source, name))
                ),
            )

    gui_storage = tempfile.TemporaryDirectory(prefix="FacilityStudioMacGui-")
    old_storage = os.environ.get("LOCALAPPDATA")
    old_preferences = os.environ.get("FACILITY_STUDIO_PREFERENCES")
    os.environ["FACILITY_STUDIO_PREFERENCES"] = str(
        Path(gui_storage.name) / "preferences.json"
    )
    from facility_studio import i18n

    i18n.set_language("zh-Hant", persist=False)
    os.environ["LOCALAPPDATA"] = gui_storage.name
    print("Creating native Tk window...", flush=True)
    root = tk.Tk()
    callback_errors = []

    def callback_error(*details):
        callback_errors.append("".join(traceback.format_exception(*details)))

    root.report_callback_exception = callback_error

    ui_timings = []

    def pump_gui(*, initial_render=False):
        # Exercise the actual application event loop. Tk Aqua's update() can
        # wait indefinitely with hidden multiple-window layouts. A timed
        # mainloop also proves that native UI timers are still responsive.
        started = time.monotonic()
        root.after(150, root.quit)
        root.mainloop()
        elapsed = time.monotonic() - started
        budget = 20 if initial_render else 5
        timing = {
            "phase": "initial-render" if initial_render else "interaction",
            "elapsed_seconds": round(elapsed, 3),
            "budget_seconds": budget,
        }
        ui_timings.append(timing)
        (destination / "Native_UITiming.json").write_text(
            json.dumps(ui_timings, indent=2), encoding="utf-8"
        )
        if initial_render or elapsed > 1:
            print("Native UI timing: " + json.dumps(timing), flush=True)
        if elapsed > budget:
            raise AssertionError(
                f"Native UI {timing['phase']} took {elapsed:.2f}s; limit {budget}s"
            )

    try:
        from facility_studio.simple_desktop import SimpleToolsApp

        print("Creating independent-tools interface...", flush=True)
        app = SimpleToolsApp(root)
        root.geometry("1100x760")
        pump_gui(initial_render=True)
        check(
            "Tk Aqua native window system",
            lambda: root.tk.call("tk", "windowingsystem") == "aqua",
        )
        for name in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):

            def open_tool(tool=name):
                app.show_tool(tool)
                pump_gui()
                return app.active_page().result is not None

            check(f"Live GUI: {name}", open_tool)
        check(
            "Equipment import window",
            lambda: app.open_equipment().win.winfo_exists() == 1,
        )
        check(
            "Mac application Quit uses the document workflow",
            lambda: bool(root.tk.call("info", "commands", "tk::mac::Quit")),
        )
        print("Creating engineering workbench...", flush=True)
        workbench = app.open_workbench()
        root.report_callback_exception = callback_error
        pump_gui(initial_render=True)
        check("Full workbench GUI calculates", lambda: workbench.result is not None)
        for page in range(9):

            def open_page(index=page):
                workbench.show_page(index)
                pump_gui()
                return workbench.pages[index].winfo_ismapped() == 1

            check(f"Workbench live page: {page}", open_page)
        from facility_studio.language_acceptance import run as check_languages

        check_languages(
            root, app, workbench, check, pump_gui, destination / "Mac_Acceptance.json"
        )
        from facility_studio.tutorial_acceptance import run as check_tutorial

        check_tutorial(root, app, workbench, check, pump_gui)
        from facility_studio.usability_acceptance import run as check_usability
        check_usability(root, app, workbench, check, pump_gui, destination)
        from facility_studio.inactive_acceptance import run_ui as check_inactive_ui
        check_inactive_ui(workbench, check, pump_gui)
        check("Native UI heartbeat", lambda: (pump_gui(), True)[1])
        check("No native GUI callback exceptions", lambda: not callback_errors)
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        figure = Figure(figsize=(2, 2))
        figure.add_subplot().plot([0, 1], [0, 1])
        canvas = FigureCanvasTkAgg(figure, master=root)
        check("Matplotlib TkAgg drawing", lambda: (canvas.draw(), True)[1])
        from unittest.mock import patch

        with patch("tkinter.messagebox.askyesnocancel", return_value=False):
            app.close()
    finally:
        try:
            if root.winfo_exists():
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
        gui_storage.cleanup()
    destination = Path.home() / "Library" / "Logs" / "Facility_Studio_V5_5"
    destination.mkdir(parents=True, exist_ok=True)
    report = {
        "version": __version__,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version,
        "matplotlib": matplotlib.__version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ui_event_timings": ui_timings,
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
    }
    path = destination / "Mac_Acceptance.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nMac acceptance report: {path}")
    if sys.platform == "darwin":
        faulthandler.cancel_dump_traceback_later()
    return 0 if report["passed"] else 2
