"""Verify the actual staged release and reject incomplete or changed payloads."""

from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nsis_integrity import expected_members, verify_setup

spec = importlib.util.spec_from_file_location(
    "release_bootstrap", ROOT / "installer/oneclick_setup.py"
)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)
checks = []


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    assert condition, name


def rejected(name, callback):
    try:
        callback()
    except RuntimeError:
        check(name, True)
    else:
        check(name, False)


manifest = bootstrap.verify_payload(ROOT / "installer")
check("01_real_payload_manifest", bool(manifest))
payload = ROOT / "installer/payload"
check(
    "02_payload_matches_release_sources",
    all(
        (ROOT / relative).read_bytes() == (payload / relative).read_bytes()
        for relative in manifest
    ),
)
modules = ROOT / "facility_studio"
missing = []
for path in modules.glob("*.py"):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            name = node.module.split(".")[0]
            if not (modules / (name + ".py")).is_file():
                missing.append(name)
check("03_all_local_module_dependencies_present", not missing)
required = (
    "LICENSE",
    "LICENSE_GUIDE.md",
    "LICENSE_LEGACY_MIT",
    "THIRD_PARTY_NOTICES.md",
    "Facility_Studio_V5_5.py",
    "facility_studio/ahu_schema.py",
    "facility_studio/simple_desktop.py",
    "facility_studio/simple_engines.py",
    "facility_studio/air_chart.py",
    "facility_studio/equipment_schema.py",
    "facility_studio/equipment_io.py",
    "facility_studio/json_io.py",
    "facility_studio/equipment_analysis.py",
    "facility_studio/equipment_view.py",
    "facility_studio/resources/Equipment_Template.xlsx",
    "facility_studio/resources/app.ico",
    "facility_studio/resources/engineering_tables.json",
)
required += tuple(
    "facility_studio/resources/equipment_csv/" + system + ".csv"
    for system in ("電力", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV")
)
with tempfile.TemporaryDirectory(prefix="facility_payload_test_") as directory:
    root = Path(directory)
    for relative in required:
        path = root / "payload" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    records = {
        relative: hashlib.sha256(b"fixture").hexdigest() for relative in required
    }
    manifest_path = root / "payload_sha256.json"
    manifest_path.write_text(json.dumps(records), encoding="utf-8")
    bootstrap.verify_payload(root)
    schema = root / "payload/facility_studio/ahu_schema.py"
    schema.unlink()
    rejected("04_missing_AHU_schema_blocked", lambda: bootstrap.verify_payload(root))
    schema.write_bytes(b"changed")
    rejected("05_modified_module_blocked", lambda: bootstrap.verify_payload(root))
    schema.write_bytes(b"fixture")
    simple = root / "payload/facility_studio/simple_desktop.py"
    simple.unlink()
    rejected(
        "11_missing_simple_tool_UI_blocked", lambda: bootstrap.verify_payload(root)
    )
    simple.write_bytes(b"fixture")
    template = root / "payload/facility_studio/resources/Equipment_Template.xlsx"
    template.unlink()
    rejected("14_missing_template_blocked", lambda: bootstrap.verify_payload(root))
    template.write_bytes(b"fixture")
    for index, relative in enumerate(
        ("LICENSE", "LICENSE_GUIDE.md", "LICENSE_LEGACY_MIT", "facility_studio/json_io.py"),
        start=16,
    ):
        member = root / "payload" / relative
        member.unlink()
        rejected(f"{index}_missing_license_or_security_member_blocked",
                 lambda: bootstrap.verify_payload(root))
        member.write_bytes(b"fixture")
    extra = root / "payload/facility_studio/obsolete.py"
    extra.write_bytes(b"fixture")
    rejected("06_unexpected_module_blocked", lambda: bootstrap.verify_payload(root))
    extra.unlink()
    manifest_path.write_text("{}", encoding="utf-8")
    rejected("07_empty_manifest_blocked", lambda: bootstrap.verify_payload(root))
    manifest_path.write_text(
        json.dumps(dict(records, **{"../outside.py": "0" * 64})), encoding="utf-8"
    )
    rejected("08_path_traversal_blocked", lambda: bootstrap.verify_payload(root))

binary = (ROOT / "Facility_Studio_V5_5_4_Setup.exe").read_bytes()
offset = struct.unpack_from("<I", binary, 0x3C)[0]
check(
    "09_setup_is_windows_PE",
    binary[:2] == b"MZ" and binary[offset : offset + 4] == b"PE\0\0",
)
check("10_setup_version_resource", "5.5.4".encode("utf-16-le") in binary)
integrity = verify_setup(binary, expected_members(ROOT / "installer"))
check("12_setup_NSIS_integrity", integrity["passed"] and integrity["forced_crc"])
check(
    "13_setup_complete_archive_files",
    integrity["embedded_files"] == len(expected_members(ROOT / "installer")),
)
command = (ROOT / "installer/START.cmd").read_bytes()
check(
    "15_CMD_real_line_endings_and_version",
    b"\r\n" in command and b"5.5.4" in command and b"5.5.3" not in command,
)
(ROOT / "evidence/Packaging_Checks.json").write_text(
    json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"{len(checks)} packaging checks passed; Windows installation remains untested")
