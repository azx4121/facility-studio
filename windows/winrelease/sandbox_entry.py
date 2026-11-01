"""Isolated per-user sandbox entry; configure storage before importing the app."""

import os
from pathlib import Path
import sys


def configure():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    data = Path(
        os.environ.get(
            "FACILITY_STUDIO_SANDBOX_DATA",
            base / "Facility Studio FEED Sandbox" / "Data",
        )
    )
    data.mkdir(parents=True, exist_ok=True)
    os.environ["FACILITY_STUDIO_SANDBOX"] = "1"
    os.environ["FACILITY_STUDIO_SANDBOX_DATA"] = str(data)
    os.environ["LOCALAPPDATA"] = str(data)
    os.environ["FACILITY_STUDIO_PREFERENCES"] = str(data / "preferences.json")
    os.environ["MPLCONFIGDIR"] = str(data / "cache/matplotlib")
    os.environ["MPLBACKEND"] = "TkAgg"
    sys.dont_write_bytecode = True
    return data


def main():
    data = configure()
    if "--sandbox-self-test" in sys.argv:
        target = Path(sys.argv[sys.argv.index("--sandbox-self-test") + 1])
        try:
            from facility_studio.sandbox_selftest import run

            # Windowed executables keep a live stream until interpreter exit.
            log = (data / "sandbox-native.log").open("a", encoding="utf-8")
            if sys.stdout is None:
                sys.stdout = log
            if sys.stderr is None:
                sys.stderr = log
            if os.environ.get("FACILITY_TEST_BLOCK_NETWORK") == "1":

                def offline_audit(event, arguments):
                    if event in (
                        "socket.connect",
                        "socket.getaddrinfo",
                        "socket.sendto",
                    ):
                        raise RuntimeError("離線驗收禁止網路連線：" + event)

                sys.addaudithook(offline_audit)
            try:
                return run(target)
            finally:
                log.flush()
        except Exception:
            import traceback

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(traceback.format_exc(), encoding="utf-8")
            return 2
    from winrelease.entry import main as regular_entry

    return regular_entry()


if __name__ == "__main__":
    raise SystemExit(main())
