"""Prepare the two public delivery assets without changing native-test inputs."""

import hashlib
from pathlib import Path
import re


def parse_checksums(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            raise ValueError("Invalid SHA256SUMS entry")
        name = parts[1].removeprefix("*")
        if name in result:
            raise ValueError("Duplicate checksum filename: " + name)
        result[name] = parts[0]
    return result


def public_checksums(text, names):
    names = tuple(names)
    if not names or len(names) != len(set(names)):
        raise ValueError("Public filenames must be unique and nonempty")
    entries = parse_checksums(text)
    if any(name not in entries for name in names):
        raise ValueError("Missing public-file checksum")
    return "".join(f"{entries[name]}  {name}\n" for name in names).encode("utf-8")


def prepare_public_assets(folder, names):
    """Keep internal ZIPs and their checksums intact; upload EXE/DMG plus sums."""
    folder = Path(folder)
    names = tuple(names)
    if any(Path(name).name != name or name == "SHA256SUMS.txt" for name in names):
        raise ValueError("Invalid public binary filename")
    checksums = (folder / "SHA256SUMS.txt").read_text(encoding="utf-8")
    expected = parse_checksums(checksums)
    assets = {}
    for name in names:
        data = (folder / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected.get(name):
            raise ValueError("Distribution changed after native testing: " + name)
        assets[name] = data
    assets["SHA256SUMS.txt"] = public_checksums(checksums, names)
    return assets
