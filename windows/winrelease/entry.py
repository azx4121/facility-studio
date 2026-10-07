"""Windowed frozen entry point; all runtime dependencies are bundled."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import traceback


def main():
    frozen = bool(getattr(sys, "frozen", False))
    logs = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Facility_Studio_V5_5" / "Logs"
    log_file = None
    if frozen:
        logs.mkdir(parents=True, exist_ok=True)
        # Windowed PyInstaller executables have no stdout/stderr. Keep useful
        # startup diagnostics without opening a console or touching projects.
        log_file = (logs / "Windows_Runtime.log").open("a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log_file
        if sys.stderr is None:
            sys.stderr = log_file
        print("\nFacility Studio win.2 start " + datetime.now().isoformat())

    if os.environ.get("FACILITY_TEST_BLOCK_NETWORK") == "1":
        def offline_audit(event, arguments):
            if event in ("socket.connect", "socket.getaddrinfo", "socket.sendto"):
                raise RuntimeError("Offline acceptance forbids network access: " + event)
        sys.addaudithook(offline_audit)

    try:
        if "--self-test" in sys.argv:
            parser = argparse.ArgumentParser(description="Local Windows acceptance; no uploads")
            parser.add_argument("--self-test", action="store_true")
            parser.add_argument("--self-test-result", type=Path, default=logs / "Windows_Acceptance.json")
            args = parser.parse_args()
            from winrelease.selftest import run
            return run(args.self_test_result)
        from facility_studio.cli import main as application_main
        return application_main()
    except Exception:
        details = traceback.format_exc()
        print(details, file=sys.stderr)
        if frozen and "--self-test" not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "程式啟動失敗。請提供錯誤記錄：\n" + str(logs / "Windows_Runtime.log"),
                "Facility Studio", 0x10,
            )
        return 2
    finally:
        if log_file is not None:
            log_file.flush()


if __name__ == "__main__":
    raise SystemExit(main())
