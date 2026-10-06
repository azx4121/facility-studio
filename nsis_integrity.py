"""Verify this unsigned NSIS solid-LZMA installer before it is delivered.

The first-header length and CRC convention follow NSIS Source/build.cpp:
https://github.com/kichik/nsis/blob/master/Source/build.cpp
This verifies archive bytes and their contents, not Windows execution.
"""

from pathlib import Path
import hashlib
import lzma
import struct
import zlib

MAGIC = b"\xef\xbe\xad\xdeNullsoftInst"
MAX_DECODED = 64 * 1024 * 1024


class InstallerIntegrityError(RuntimeError):
    pass


def expected_members(directory):
    root = Path(directory)
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def verify_setup(binary, members, *, extract_to=None):
    """Reject missing CRC/data, corruption, truncation or omitted source files."""
    data = binary if isinstance(binary, bytes) else Path(binary).read_bytes()
    if len(data) < 544 or data[:2] != b"MZ":
        raise InstallerIntegrityError("Missing Windows executable header.")
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    if pe+4 > len(data) or data[pe:pe+4] != b"PE\0\0":
        raise InstallerIntegrityError("Invalid Windows PE signature.")
    offset = next((pos for pos in range(512, len(data)-31, 512)
                   if data[pos+4:pos+20] == MAGIC), None)
    if offset is None:
        raise InstallerIntegrityError("Missing NSIS first header.")
    flags, _, _, _, _, header_length, following = struct.unpack_from("<7I", data, offset)
    if following <= 36 or offset+following != len(data):
        raise InstallerIntegrityError("NSIS archive length is zero, truncated or has unexpected trailing data.")
    if flags & 4 or not flags & 8:
        raise InstallerIntegrityError("This release requires CRCCheck force; CRC checking may not be disabled.")
    if not 0 < header_length <= MAX_DECODED:
        raise InstallerIntegrityError("Invalid NSIS instruction-header length.")
    stored_crc = struct.unpack_from("<I", data, len(data)-4)[0]
    actual_crc = zlib.crc32(data[512:-4]) & 0xffffffff
    if stored_crc != actual_crc:
        raise InstallerIntegrityError("NSIS CRC32 mismatch.")
    compressed = data[offset+28:-4]
    prop = compressed[0]
    lc, lp, pb = prop % 9, (prop//9) % 5, prop//45
    dictionary = struct.unpack_from("<I", compressed, 1)[0]
    if prop >= 225 or lc+lp > 4 or not 4096 <= dictionary <= MAX_DECODED:
        raise InstallerIntegrityError("Unsupported or unsafe LZMA properties.")
    try:
        decoder = lzma.LZMADecompressor(
            format=lzma.FORMAT_RAW,
            filters=[dict(id=lzma.FILTER_LZMA1, dict_size=dictionary, lc=lc, lp=lp, pb=pb)],
        )
        stream = decoder.decompress(compressed[5:], max_length=MAX_DECODED+1)
    except lzma.LZMAError as error:
        raise InstallerIntegrityError("NSIS compressed data cannot be decoded.") from error
    if not decoder.eof or decoder.unused_data or len(stream) > MAX_DECODED:
        raise InstallerIntegrityError("NSIS compressed stream is incomplete or exceeds the release limit.")
    if len(stream) < header_length+4 or struct.unpack_from("<I", stream)[0] != header_length:
        raise InstallerIntegrityError("Decoded instruction-header length differs from the first header.")
    instructions = stream[4:4+header_length]
    records = {}
    position = header_length+4
    count = 0
    while position < len(stream):
        if len(stream)-position < 4:
            raise InstallerIntegrityError("Truncated NSIS data-block length.")
        size = struct.unpack_from("<I", stream, position)[0]
        position += 4
        if size & 0x80000000 or size > len(stream)-position:
            raise InstallerIntegrityError("Invalid solid NSIS data-block boundary.")
        body = stream[position:position+size]
        digest = hashlib.sha256(body).hexdigest()
        records[(size, digest)] = body
        position += size
        count += 1
    if not members:
        raise InstallerIntegrityError("Expected installer content cannot be empty.")
    checked = {}
    for name, expected in members.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise InstallerIntegrityError("Unsafe expected installer path.")
        digest = hashlib.sha256(expected).hexdigest()
        extracted = records.get((len(expected), digest))
        if extracted is None or extracted != expected:
            raise InstallerIntegrityError("Installer omits or changes file: " + name)
        parent = relative.parent.as_posix()
        paths = (parent, parent.replace("/", "\\"))
        if relative.name.encode("utf-16-le") not in instructions or (
            parent != "." and not any(path.encode("utf-16-le") in instructions for path in paths)
        ):
            raise InstallerIntegrityError("Missing installer path instruction: " + name)
        checked[name] = digest
        if extract_to is not None:
            destination = Path(extract_to) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(extracted)
    return dict(
        passed=True, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
        header_offset=offset, header_length=header_length, archive_length=following,
        forced_crc=True, crc32=f"{stored_crc:08X}", decoded_bytes=len(stream),
        data_blocks=count, embedded_files=len(checked), member_sha256=checked,
        windows_execution_tested=False,
    )
