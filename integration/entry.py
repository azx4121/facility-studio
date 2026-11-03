"""Independent data directory, native executable, no service or API calls."""
import os
from pathlib import Path
import sys
import traceback


def main():
    data = Path(os.environ.get("FACILITY_STUDIO_FUSION_DATA", Path.home() / "Facility Studio 測試資料-5.7.3"))
    data.mkdir(parents=True, exist_ok=True)
    os.environ.update(FACILITY_STUDIO_SANDBOX="1", FACILITY_STUDIO_SANDBOX_DATA=str(data),
                      LOCALAPPDATA=str(data), FACILITY_STUDIO_PREFERENCES=str(data / "preferences.json"),
                      MPLCONFIGDIR=str(data / "cache/matplotlib"), MPLBACKEND="TkAgg")
    log = (data / "啟動與驗收記錄.log").open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log
    # Windows console/CI may supply cp1252 streams even to a GUI executable.
    # All diagnostic output must support the product's Traditional Chinese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        from facility_studio import i18n
        i18n.set_language("zh-Hant", persist=False)
        if os.environ.get("FACILITY_TEST_BLOCK_NETWORK") == "1":
            def offline(event, args):
                if event in ("socket.connect", "socket.getaddrinfo", "socket.sendto"):
                    raise RuntimeError("離線驗收禁止網路連線：" + event)
            sys.addaudithook(offline)
        if "--fusion-self-test" in sys.argv:
            from facility_studio.fusion_acceptance import run
            return run(sys.argv[sys.argv.index("--fusion-self-test") + 1])
        if "--facilities-self-test" in sys.argv:
            from facility_studio.facilities_acceptance import run
            return run(sys.argv[sys.argv.index("--facilities-self-test") + 1])
        if "--sandbox-self-test" in sys.argv:
            from facility_studio.sandbox_selftest import run
            return run(sys.argv[sys.argv.index("--sandbox-self-test") + 1])
        from facility_studio.cli import main as app_main
        return app_main()
    except Exception:
        traceback.print_exc()
        return 2
    finally:
        log.flush()


if __name__ == "__main__":
    raise SystemExit(main())
