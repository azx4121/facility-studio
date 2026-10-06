"""Recreate the verified CPython framework and architecture-specific wheel sets."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
from urllib.request import urlopen
import xml.etree.ElementTree as ET
import zlib

PYTHON_URL = "https://www.python.org/ftp/python/3.13.15/python-3.13.15-macos11.pkg"
PYTHON_SHA256 = "3b7eaf7f29825f796e8267024435540ddf1f17fc9a97ad58095daa7a75bfdcd3"


def download_verified(url, digest, destination):
    with urlopen(url, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"SHA256 mismatch: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def framework_payload(pkg):
    data = pkg.read_bytes()
    magic, header_size, version, compressed, expanded, algorithm = struct.unpack_from(
        ">IHHQQI", data
    )
    if magic != 0x78617221 or version != 1:
        raise ValueError("Invalid XAR package")
    toc = ET.fromstring(zlib.decompress(data[header_size : header_size + compressed]))
    for package in toc.iter("file"):
        if package.findtext("name") == "Python_Framework.pkg":
            for item in package.findall("file"):
                if item.findtext("name") == "Payload":
                    node = item.find("data")
                    start = header_size + compressed + int(node.findtext("offset"))
                    end = start + int(node.findtext("length"))
                    payload = data[start:end]
                    if node.find("encoding").get("style") == "application/x-gzip":
                        payload = zlib.decompress(payload)
                    return gzip.decompress(payload)
    raise ValueError("Python framework payload not found")


def extract_cpio(data, destination):
    """Decode the official installer's ODC CPIO without running its scripts."""
    position = 0
    while position < len(data):
        header = data[position : position + 76]
        if header[:6] != b"070707":
            raise ValueError("Unsupported CPIO format")
        mode = int(header[18:24], 8)
        namesize = int(header[59:65], 8)
        size = int(header[65:76], 8)
        links = int(header[36:42], 8)
        position += 76
        name = data[position : position + namesize - 1].decode()
        position += namesize
        content = data[position : position + size]
        position += size
        if name == "TRAILER!!!":
            return
        target = destination / name
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError("CPIO path escapes framework")
        target.parent.mkdir(parents=True, exist_ok=True)
        if stat.S_ISDIR(mode):
            target.mkdir(exist_ok=True)
        elif stat.S_ISLNK(mode):
            if target.is_symlink():
                target.unlink()
            target.symlink_to(content.decode())
        elif stat.S_ISREG(mode):
            if links > 1:
                raise ValueError("Unexpected CPIO hard links")
            target.write_bytes(content)
            target.chmod(stat.S_IMODE(mode))
        else:
            raise ValueError("Unsupported CPIO entry")
    raise ValueError("CPIO trailer missing")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    runtime = args.destination.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    package = runtime / "python-3.13.15-macos11.pkg"
    if (
        not package.is_file()
        or hashlib.sha256(package.read_bytes()).hexdigest() != PYTHON_SHA256
    ):
        download_verified(PYTHON_URL, PYTHON_SHA256, package)
    framework = runtime / "Python.framework"
    if framework.exists():
        raise SystemExit("Framework already exists. Use a fresh destination.")
    framework.mkdir()
    extract_cpio(framework_payload(package), framework)
    records = json.loads(
        Path(__file__).with_name("Wheel_Integrity.json").read_text(encoding="utf-8")
    )
    for record in records:
        info = json.load(
            urlopen(
                f"https://pypi.org/pypi/{record['package']}/{record['version']}/json",
                timeout=60,
            )
        )
        filename = Path(record["path"]).name
        remote = next(item for item in info["urls"] if item["filename"] == filename)
        if remote["digests"]["sha256"] != record["sha256"]:
            raise ValueError("PyPI checksum changed")
        download_verified(remote["url"], record["sha256"], runtime / record["path"])
    import ziglang

    zig = Path(ziglang.__file__).with_name("zig")
    source = Path(__file__).with_name("launcher.c")
    for architecture, target in (
        ("arm64", "aarch64-macos.11.0"),
        ("x86_64", "x86_64-macos.11.0"),
    ):
        subprocess.run(
            [
                str(zig),
                "cc",
                "-target",
                target,
                "-O2",
                "-Wl,-headerpad,0x1000",
                str(source),
                "-o",
                str(runtime / f"launcher_{architecture}"),
            ],
            check=True,
        )
    from PIL import Image
    import zipfile

    with Image.open(
        Path(__file__).resolve().parents[1] / "facility_studio/resources/app.png"
    ) as icon:
        icon.save(runtime / "FacilityStudio.icns", format="ICNS")
    with zipfile.ZipFile(runtime / "icon.icns.zip", "w") as archive:
        archive.write(runtime / "FacilityStudio.icns", "FacilityStudio.icns")
    print(
        "Runtime and wheels prepared; use build_bundle.py and a verified rcodesign executable."
    )


if __name__ == "__main__":
    main()
