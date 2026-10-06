"""Inspect and relocate Mach-O load commands without executing target code."""

import os
from pathlib import Path
import struct

CPU_NAMES = {0x01000007: "x86_64", 0x0100000C: "arm64"}
DYLIB_COMMANDS = {0xC, 0xD, 0x18, 0x80000018, 0x1F, 0x8000001F, 0x20, 0x23, 0x80000023}


def slices(data):
    if data[:4] in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
        wide = data[:4] == b"\xca\xfe\xba\xbf"
        count = struct.unpack_from(">I", data, 4)[0]
        if count > 16:
            raise ValueError("Invalid universal Mach-O architecture count")
        output = []
        for index in range(count):
            fields = struct.unpack_from(
                ">IIQQII" if wide else ">IIIII", data, 8 + index * (32 if wide else 20)
            )
            cpu, subtype, offset, size = fields[:4]
            if offset + size > len(data):
                raise ValueError("Mach-O slice extends beyond file")
            output.append((cpu, subtype, offset, size))
        return output
    if data[:4] == b"\xcf\xfa\xed\xfe":
        cpu, subtype = struct.unpack_from("<ii", data, 4)
        return [(cpu, subtype, 0, len(data))]
    return []


def commands(data, offset):
    if data[offset : offset + 4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("Only little-endian 64-bit Mach-O is supported")
    count, length = struct.unpack_from("<II", data, offset + 16)
    position = offset + 32
    end = position + length
    result = []
    for _ in range(count):
        code, size = struct.unpack_from("<II", data, position)
        if size < 8 or position + size > end:
            raise ValueError("Invalid Mach-O load command")
        result.append((code, bytes(data[position : position + size])))
        position += size
    if position != end:
        raise ValueError("Mach-O load commands have inconsistent length")
    return result


def string_value(command):
    offset = struct.unpack_from("<I", command, 8)[0]
    if offset >= len(command):
        raise ValueError("Invalid Mach-O command string")
    return command[offset:].split(b"\0", 1)[0].decode("utf-8")


def inspect(path):
    data = Path(path).read_bytes()
    result = []
    for cpu, subtype, offset, size in slices(data):
        loads = commands(data, offset)
        dependencies = [
            string_value(value)
            for code, value in loads
            if code in DYLIB_COMMANDS and code != 0xD
        ]
        rpaths = [string_value(value) for code, value in loads if code == 0x8000001C]
        minimum = None
        for code, value in loads:
            if code == 0x32:  # LC_BUILD_VERSION
                minimum = struct.unpack_from("<I", value, 12)[0]
            elif code == 0x24:  # LC_VERSION_MIN_MACOSX
                minimum = struct.unpack_from("<I", value, 8)[0]
        result.append(
            {
                "architecture": CPU_NAMES.get(cpu, hex(cpu)),
                "dependencies": dependencies,
                "rpaths": rpaths,
                "minimum_macos": (
                    None
                    if minimum is None
                    else f"{minimum >> 16}.{(minimum >> 8) & 255}.{minimum & 255}"
                ),
                "signed": any(code == 0x1D for code, _ in loads),
            }
        )
    return result


def universal(inputs, destination):
    items = []
    for path in inputs:
        data = Path(path).read_bytes()
        for cpu, subtype, offset, size in slices(data):
            items.append((cpu, subtype, data[offset : offset + size]))
    if len({cpu for cpu, _, _ in items}) != len(items):
        raise ValueError("Duplicated CPU architecture")
    alignment = 14
    output = bytearray(
        struct.pack(">II", 0xCAFEBABE, len(items)) + bytes(20 * len(items))
    )
    for index, (cpu, subtype, data) in enumerate(items):
        position = (len(output) + (1 << alignment) - 1) & ~((1 << alignment) - 1)
        output.extend(bytes(position - len(output)))
        struct.pack_into(
            ">IIIII",
            output,
            8 + index * 20,
            cpu,
            subtype,
            position,
            len(data),
            alignment,
        )
        output.extend(data)
    Path(destination).write_bytes(output)
    Path(destination).chmod(0o755)


def relocate(path, app):
    path, app = Path(path), Path(app)
    data = bytearray(path.read_bytes())
    changed = 0
    for cpu, subtype, offset, size in slices(data):
        original = commands(data, offset)
        rewritten = []
        section_offsets = []
        for code, value in original:
            if code == 0x19:  # LC_SEGMENT_64
                count = struct.unpack_from("<I", value, 64)[0]
                for index in range(count):
                    file_offset = struct.unpack_from("<I", value, 72 + 80 * index + 48)[
                        0
                    ]
                    if file_offset:
                        section_offsets.append(file_offset)
            if code in DYLIB_COMMANDS:
                old = string_value(value)
                if old.startswith("/Library/Frameworks/Python.framework/"):
                    target = (
                        app
                        / "Contents"
                        / "Frameworks"
                        / "Python.framework"
                        / old.split("Python.framework/", 1)[1]
                    )
                    if not target.is_file():
                        raise ValueError(f"Missing bundled dependency: {old}")
                    if code == 0xD:
                        new = (
                            "@rpath/Python.framework/"
                            + old.split("Python.framework/", 1)[1]
                        )
                    else:
                        new = "@loader_path/" + os.path.relpath(target, path.parent)
                    position = struct.unpack_from("<I", value, 8)[0]
                    blob = bytearray(value[:position] + new.encode() + b"\0")
                    blob.extend(bytes((-len(blob)) % 8))
                    struct.pack_into("<I", blob, 4, len(blob))
                    value = bytes(blob)
                    changed += 1
            rewritten.append(value)
        old_length = struct.unpack_from("<I", data, offset + 20)[0]
        blob = b"".join(rewritten)
        limit = min(section_offsets) if section_offsets else 32 + old_length
        if 32 + len(blob) > limit:
            raise ValueError(f"Insufficient Mach-O header space: {path}")
        data[offset + 32 : offset + 32 + max(old_length, len(blob))] = blob.ljust(
            max(old_length, len(blob)), b"\0"
        )
        struct.pack_into("<I", data, offset + 20, len(blob))
    if changed:
        path.write_bytes(data)
    return changed
