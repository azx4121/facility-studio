"""Exercise the acceptance tool on the host without pretending it is a Mac."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "macos"))
import mac_selftest

with tempfile.TemporaryDirectory(prefix="mac_acceptance_host_") as directory:
    with patch("pathlib.Path.home", return_value=Path(directory)):
        with redirect_stdout(io.StringIO()):
            status = mac_selftest.run()
    result = json.loads((Path(directory) / "Library/Logs/Facility_Studio_V5_5/Mac_Acceptance.json").read_text(encoding="utf-8"))
    expected_unavailable = {
        "Apple native deep signature verification",
        "Bundled CPython 3.13",
        "Tk Aqua native window system",
        "Mac application Quit uses the document workflow",
    }
    failed = {item["name"] for item in result["checks"] if not item["passed"]}
    assert status == 2 and failed == expected_unavailable, failed
    assert "Linux" in result["platform"] and not result["passed"]
    checked = len(result["checks"]) - len(expected_unavailable)
    record = {
        "environment": "Linux real Tk/Xvfb; not native Mac acceptance",
        "passed": True,
        "cross_platform_acceptance_tool_checks": checked,
        "expected_unavailable_native_checks": sorted(expected_unavailable),
        "native_acceptance_was_correctly_reported_as_failed": True,
        "checks": result["checks"],
    }
    (ROOT / "evidence/Host_Selftest_Validation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Acceptance tool: {checked} cross-platform checks passed; 4 unavailable native checks correctly failed on Linux.")
