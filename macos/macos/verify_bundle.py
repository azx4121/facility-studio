"""Independent byte, relocation, CPU and ad-hoc seal checks on any build host.

These checks deliberately do not claim macOS Gatekeeper or native execution.
The optional Mac self-test runs Apple's codesign and the actual GUI on a Mac.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct

from macho import commands, inspect, slices


def signature_blobs(data, offset):
    command = next(value for code, value in commands(data, offset) if code == 0x1D)
    position, length = struct.unpack_from("<II", command, 8)
    signature = data[offset + position : offset + position + length]
    magic, size, count = struct.unpack_from(">III", signature)
    if magic != 0xFADE0CC0 or size > length:
        raise ValueError("Invalid code signature superblob")
    blobs = {}
    for index in range(count):
        kind, start = struct.unpack_from(">II", signature, 12 + index * 8)
        blob_size = struct.unpack_from(">I", signature, start + 4)[0]
        if start + blob_size > size:
            raise ValueError("Invalid code signature blob boundary")
        blobs[kind] = signature[start : start + blob_size]
    return position, blobs


def code_directories(path):
    data = Path(path).read_bytes()
    result = []
    for cpu, subtype, offset, size in slices(data):
        position, blobs = signature_blobs(data, offset)
        result.extend(
            value for value in blobs.values() if value[:4] == b"\xfa\xde\x0c\x02"
        )
    return result


def directory_digest(directory, data):
    kind, size = directory[37], directory[36]
    constructors = {
        1: hashlib.sha1,
        2: hashlib.sha256,
        3: hashlib.sha256,
        4: hashlib.sha384,
    }
    if kind not in constructors:
        raise ValueError("Unsupported code signature digest")
    return constructors[kind](data).digest()[:size]


def verify_python_api(path):
    data = path.read_bytes()
    records = []
    for cpu, subtype, offset, size in slices(data):
        table = next(value for code, value in commands(data, offset) if code == 2)
        symbol_offset, count, string_offset, string_size = struct.unpack_from(
            "<IIII", table, 8
        )
        found = False
        for index in range(count):
            name_offset, kind, section, descriptor, value = struct.unpack_from(
                "<IBBHQ", data, offset + symbol_offset + index * 16
            )
            if kind & 0xE0 or not kind & 1 or not section or not value:
                continue
            name = data[
                offset
                + string_offset
                + name_offset : offset
                + string_offset
                + string_size
            ].split(b"\0", 1)[0]
            if name == b"_Py_BytesMain":
                found = True
                break
        if not found:
            raise ValueError("CPython does not export the required embedding API")
        records.append({"cpu": hex(cpu), "Py_BytesMain_exported": True})
    return records


def verify_binary(path):
    data = path.read_bytes()
    results = []
    for cpu, subtype, offset, size in slices(data):
        position, blobs = signature_blobs(data, offset)
        directories = [
            value for value in blobs.values() if value[:4] == b"\xfa\xde\x0c\x02"
        ]
        if not any(directory[37] == 2 for directory in directories):
            raise ValueError("Missing SHA256 code directory")
        for directory in directories:
            (
                magic,
                length,
                version,
                flags,
                hash_offset,
                identifier_offset,
                special_count,
                slots,
                limit,
                hash_size,
                hash_type,
                platform,
                page_power,
            ) = struct.unpack_from(">9I4B", directory)
            if not flags & 2:
                raise ValueError("Expected an ad-hoc signature")
            if version >= 0x20300 and limit == 0xFFFFFFFF:
                limit = struct.unpack_from(">Q", directory, 56)[0]
            if limit > position or limit > size:
                raise ValueError("Code hash boundary exceeds binary")
            page_size = (1 << page_power) if page_power else limit
            if slots != (limit + page_size - 1) // page_size:
                raise ValueError("Invalid signature page count")
            for index in range(slots):
                start = offset + index * page_size
                end = min(start + page_size, offset + limit)
                digest = directory_digest(directory, data[start:end])
                if (
                    digest
                    != directory[
                        hash_offset
                        + index * hash_size : hash_offset
                        + (index + 1) * hash_size
                    ]
                ):
                    raise ValueError(f"Code page digest mismatch: {index}")
            for kind in (2, 5, 7):
                if kind in blobs:
                    digest = directory_digest(directory, blobs[kind])
                    expected = directory[
                        hash_offset
                        - kind * hash_size : hash_offset
                        - (kind - 1) * hash_size
                    ]
                    if digest != expected:
                        raise ValueError(
                            "Embedded requirement/entitlement hash mismatch"
                        )
            results.append(
                {
                    "cpu": hex(cpu),
                    "hash_type": hash_type,
                    "pages": slots,
                    "code_limit": limit,
                    "passed": True,
                }
            )
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    content = app / "Contents"
    info = plistlib.load((content / "Info.plist").open("rb"))
    records = []
    executable = content / "MacOS" / info["CFBundleExecutable"]
    assert info["LSMinimumSystemVersion"] == "11.0"
    assert {x["architecture"] for x in inspect(executable)} == {"arm64", "x86_64"}
    assert executable.stat().st_mode & 0o111
    python_api = verify_python_api(
        content / "Frameworks/Python.framework/Versions/3.13/Python"
    )
    count = 0
    for path in sorted(app.rglob("*")):
        if path.is_symlink():
            assert path.exists() and path.resolve().is_relative_to(
                app
            ), f"Broken or external symlink: {path}"
            continue
        if not path.is_file():
            continue
        with path.open("rb") as file:
            magic = file.read(4)
        if magic not in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
            continue
        count += 1
        states = inspect(path)
        relative = str(path.relative_to(app))
        for architecture in ("arm64", "x86_64"):
            if f"python-packages/{architecture}/" in relative:
                assert architecture in {state["architecture"] for state in states}
        if "/Frameworks/" in relative:
            assert {state["architecture"] for state in states} == {"arm64", "x86_64"}
        for state in states:
            minimum = state["minimum_macos"]
            if minimum:
                assert tuple(map(int, minimum.split("."))) <= (11, 0, 0)
            for dependency in state["dependencies"]:
                if dependency.startswith(("/usr/lib/", "/System/Library/")):
                    continue
                if dependency.startswith("@loader_path/"):
                    candidates = [path.parent / dependency[len("@loader_path/") :]]
                elif dependency.startswith("@executable_path/"):
                    candidates = [
                        executable.parent / dependency[len("@executable_path/") :]
                    ]
                elif dependency.startswith("@rpath/"):
                    candidates = [
                        Path(
                            rpath.replace("@loader_path", str(path.parent)).replace(
                                "@executable_path", str(executable.parent)
                            )
                        )
                        / dependency[len("@rpath/") :]
                        for rpath in state["rpaths"]
                    ]
                else:
                    raise ValueError(f"External non-system dependency: {dependency}")
                candidates = [
                    candidate
                    for candidate in candidates
                    if candidate.is_file() and candidate.resolve().is_relative_to(app)
                ]
                assert candidates, f"Unresolved library: {dependency}"
                assert any(
                    state["architecture"]
                    in {item["architecture"] for item in inspect(candidate)}
                    for candidate in candidates
                ), "Wrong dependency architecture"
        records.append(
            {"path": relative, "slices": states, "code_hashes": verify_binary(path)}
        )
    seals = []
    for signature in sorted(app.rglob("CodeResources")):
        base = signature.parent.parent
        document = plistlib.load(signature.open("rb"))
        files = document["files2"]
        for name, details in files.items():
            path = base / name
            if "symlink" in details:
                assert path.is_symlink() and os.readlink(path) == details["symlink"]
            elif "hash2" in details:
                assert (
                    path.is_file()
                    and hashlib.sha256(path.read_bytes()).digest() == details["hash2"]
                ), f"Resource digest mismatch: {path}"
            elif "cdhash" in details:
                target = path
                if path.suffix == ".framework":
                    target = path / path.stem
                hashes = [
                    directory_digest(directory, directory)[:20]
                    for directory in code_directories(target)
                ]
                assert (
                    details["cdhash"] in hashes
                ), f"Nested signature digest mismatch: {path}"
            else:
                raise ValueError(f"Unknown resource seal entry: {details}")
        seals.append(
            {
                "path": str(signature.relative_to(app)),
                "entries": len(files),
                "passed": True,
            }
        )
        # Tie the seal and its Info.plist to every architecture's main binary.
        if base == content:
            binary, plist = executable, base / "Info.plist"
        else:
            framework = next(
                parent for parent in base.parents if parent.suffix == ".framework"
            )
            binary, plist = base / framework.stem, base / "Resources/Info.plist"
        for directory in code_directories(binary):
            offset, special, hash_size = (
                struct.unpack_from(">I", directory, 16)[0],
                struct.unpack_from(">I", directory, 24)[0],
                directory[36],
            )
            for slot, path in ((1, plist), (3, signature)):
                assert special >= slot
                expected = directory[
                    offset - slot * hash_size : offset - (slot - 1) * hash_size
                ]
                assert (
                    directory_digest(directory, path.read_bytes()) == expected
                ), "Bundle seal is not linked to code signature"
    report = {
        "version": "5.5.4-mac.1",
        "passed": True,
        "embedding_api": python_api,
        "macho_files": count,
        "macho_slices": sum(len(record["slices"]) for record in records),
        "hashed_code_pages": sum(
            item["pages"] for record in records for item in record["code_hashes"]
        ),
        "sealed_resources": sum(seal["entries"] for seal in seals),
        "seals": seals,
        "binaries": records,
        "mac_hardware_execution": False,
        "apple_native_codesign_verification": "pending Mac self-test",
        "developer_id_and_notarization": False,
        "rcodesign_verify_note": "rcodesign 0.29.0 verify cannot parse empty CMS wrappers in ad-hoc signatures and warns that it is buggy. Page and resource digests were independently reconstructed; this does not replace Apple's native verification.",
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"{count} Mach-O files / {report['macho_slices']} CPU slices / {report['hashed_code_pages']} code pages / {report['sealed_resources']} sealed resources passed independent integrity checks; native Mac verification pending."
    )


if __name__ == "__main__":
    main()
