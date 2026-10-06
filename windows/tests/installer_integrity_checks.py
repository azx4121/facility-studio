"""Read and extract the real installer; fail on incomplete/corrupt variants."""

from pathlib import Path
import hashlib
import importlib.util
import json
import struct
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nsis_integrity import InstallerIntegrityError, expected_members, verify_setup

checks = []
members = expected_members(ROOT / "installer")
binary = (ROOT / "Facility_Studio_V5_5_4_Setup.exe").read_bytes()
offset = binary.find(b"\xef\xbe\xad\xdeNullsoftInst") - 4


def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))
    assert condition, name


def rejected(name, candidate, expected=None):
    try:
        verify_setup(candidate, members if expected is None else expected)
    except InstallerIntegrityError:
        check(name, True)
    else:
        check(name, False)


def changed(position, replacement):
    data = bytearray(binary)
    data[position : position + len(replacement)] = replacement
    data[-4:] = struct.pack("<I", zlib.crc32(data[512:-4]) & 0xFFFFFFFF)
    return bytes(data)


with tempfile.TemporaryDirectory(prefix="nsis_contents_check_") as temporary:
    target = Path(temporary)
    result = verify_setup(binary, members, extract_to=target)
    check(
        "01_real_forced_CRC_matches",
        result["forced_crc"]
        and struct.unpack_from("<I", binary, len(binary) - 4)[0]
        == zlib.crc32(binary[512:-4]) & 0xFFFFFFFF,
    )
    check(
        "02_nonzero_complete_archive",
        result["archive_length"] > 10000
        and offset + result["archive_length"] == len(binary),
    )
    check(
        "03_all_installer_files_decompressed", result["embedded_files"] == len(members)
    )
    check(
        "04_extracted_bytes_equal_inputs",
        all((target / name).read_bytes() == body for name, body in members.items()),
    )
    spec = importlib.util.spec_from_file_location(
        "extracted_installer", target / "oneclick_setup.py"
    )
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    check(
        "05_extracted_payload_manifest_valid",
        len(bootstrap.verify_payload(target))
        == len(json.loads((ROOT / "installer/payload_sha256.json").read_text())),
    )

# A compiler exit status or PE header alone must never approve these cases.
rejected("06_original_partial_output_pattern", binary[: offset + 33])
rejected("07_missing_CRC_footer", binary[:-4])
rejected("08_compressed_stream_truncated", binary[: offset + 40])
corrupt = bytearray(binary)
corrupt[1024] ^= 1
rejected("09_changed_CRC_covered_byte", bytes(corrupt))
rejected("10_appended_unexpected_data", binary + b"extra")
rejected("11_zero_archive_length", changed(offset + 24, b"\0\0\0\0"))
flags = struct.unpack_from("<I", binary, offset)[0]
rejected(
    "12_CRC_disabled_despite_correct_checksum",
    changed(offset, struct.pack("<I", flags | 4)),
)
rejected("13_forced_CRC_removed", changed(offset, struct.pack("<I", flags & ~8)))
rejected("14_invalid_LZMA_properties", changed(offset + 28, b"\xff"))
rejected(
    "15_excessive_decoder_memory", changed(offset + 29, struct.pack("<I", 1 << 30))
)
rejected("16_bad_stream_with_recomputed_CRC", changed(offset + 33, b"\xff" * 20))
rejected(
    "17_decoded_header_length_mismatch",
    changed(offset + 20, struct.pack("<I", result["header_length"] + 1)),
)
rejected(
    "18_missing_required_file",
    binary,
    dict(members, **{"missing.py": b"missing_release_member"}),
)
rejected(
    "19_changed_required_source",
    binary,
    dict(members, **{"payload/Facility_Studio_V5_5.py": b"changed"}),
)
rejected(
    "20_unsafe_extraction_path",
    binary,
    {"../outside.py": members["payload/Facility_Studio_V5_5.py"]},
)
rejected("21_empty_expected_manifest", binary, {})

(ROOT / "evidence/Installer_Integrity_Checks.json").write_text(
    json.dumps(dict(installer=result, checks=checks), ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(
    f"{len(checks)} installer integrity checks passed; all {len(members)} embedded files extracted and compared"
)
