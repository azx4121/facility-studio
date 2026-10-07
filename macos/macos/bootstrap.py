"""Entry script for the self-contained macOS application."""

import os
from pathlib import Path
import platform
import sys
import traceback


def bundle_paths(resources, machine):
    architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64"}.get(
        machine
    )
    if architecture is None:
        raise RuntimeError("This application supports Apple Silicon and Intel Macs.")
    resources = Path(resources).resolve()
    packages = resources / "python-packages" / architecture
    source = resources / "app"
    framework = (
        resources.parent / "Frameworks" / "Python.framework" / "Versions" / "3.13"
    )
    if not (packages.is_dir() and (source / "facility_studio" / "cli.py").is_file()):
        raise RuntimeError(
            "Application files are incomplete. Please extract the original ZIP again."
        )
    return source, packages, framework


def configure_runtime(resources):
    source, packages, framework = bundle_paths(resources, platform.machine())
    if sys.platform != "darwin":
        raise RuntimeError("The native application is intended for macOS.")
    if Path(sys.prefix).resolve() != framework.resolve() or sys.version_info[:2] != (
        3,
        13,
    ):
        raise RuntimeError("The bundled Python runtime was not loaded.")
    # Keep only this app's standard library. Add only its matching wheel set.
    sys.path[:] = [
        str(source),
        str(packages),
        *[
            entry
            for entry in sys.path
            if entry and Path(entry).resolve().is_relative_to(framework.resolve())
        ],
    ]
    framework_resources = framework / "Frameworks"
    os.environ["TCL_LIBRARY"] = str(
        framework_resources
        / "Tcl.framework"
        / "Versions"
        / "8.6"
        / "Resources"
        / "Scripts"
    )
    os.environ["TK_LIBRARY"] = str(
        framework_resources
        / "Tk.framework"
        / "Versions"
        / "8.6"
        / "Resources"
        / "Scripts"
    )
    cache = Path.home() / "Library" / "Caches" / "Facility_Studio_V5_5" / "matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cache)
    os.environ["MPLBACKEND"] = "TkAgg"
    return source


def main():
    resources = Path(__file__).resolve().parent
    log = None
    try:
        configure_runtime(resources)
        sys.argv[:] = [
            sys.argv[0],
            *[arg for arg in sys.argv[1:] if not arg.startswith("-psn_")],
        ]
        if "--self-test" in sys.argv:
            from mac_selftest import run

            return run()
        if len(sys.argv) == 1 or sys.argv[1:] == ["--full"]:
            logs = Path.home() / "Library" / "Logs" / "Facility_Studio_V5_5"
            logs.mkdir(parents=True, exist_ok=True)
            log = (logs / "startup.log").open("w", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = log
        from facility_studio.cli import main as app_main

        return app_main()
    except Exception as error:
        details = traceback.format_exc()
        logs = Path.home() / "Library" / "Logs" / "Facility_Studio_V5_5"
        try:
            logs.mkdir(parents=True, exist_ok=True)
            (logs / "startup-error.log").write_text(details, encoding="utf-8")
        except OSError:
            pass
        if log is not None:
            log.write(details)
        else:
            print(details, file=sys.stderr)
        # Automated diagnostics must finish with a nonzero exit code rather
        # than wait indefinitely for a person to close a modal error dialog.
        if "--self-test" in sys.argv:
            return 2
        try:
            import tkinter as tk
            from tkinter import messagebox

            try:
                from facility_studio import i18n

                i18n.initialize()
                english = i18n.language() == "en"
                error_text = i18n.translate(error)
            except ImportError:
                english, error_text = True, str(error)
            title = (
                "Facility Studio — Startup error"
                if english
                else "Facility Studio 啟動未完成"
            )
            guidance = (
                "Keep the complete app together and extract the original package again.\nError log: "
                if english
                else "請將完整 App 保持在同一位置，並重新解壓縮懶人包。\n錯誤記錄："
            )
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                title,
                f"{error_text}\n\n{guidance}{logs / 'startup-error.log'}",
                parent=root,
            )
            root.destroy()
        except Exception:
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
