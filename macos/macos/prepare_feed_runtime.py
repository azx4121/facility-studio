"""Install only SHA-256-pinned official PyPI artifacts into both bundle targets."""

import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile


def prepare(app, cache):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(
        Path(__file__).with_name("feed_runtime_manifest.json").read_text()
    )
    for item in manifest["artifacts"]:
        archive = cache / item["filename"]
        if not archive.exists():
            request = urllib.request.Request(
                item["url"], headers={"User-Agent": "FacilityStudio-sandbox-builder"}
            )
            with (
                urllib.request.urlopen(request, timeout=90) as src,
                archive.open("xb") as dst,
            ):
                while block := src.read(1024 * 1024):
                    dst.write(block)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("套件 SHA-256 不符：" + item["filename"])
        targets = (
            ("arm64", "x86_64")
            if item["architecture"] == "any"
            else (item["architecture"],)
        )
        for arch in targets:
            target = Path(app) / "Contents/Resources/python-packages" / arch
            if archive.suffix == ".whl":
                with zipfile.ZipFile(archive) as z:
                    for name in z.namelist():
                        if (
                            not (target / name)
                            .resolve()
                            .is_relative_to(target.resolve())
                        ):
                            raise ValueError("不安全的套件路徑")
                    z.extractall(target)
            else:
                with zipfile.ZipFile(archive) as z:
                    module = next(
                        n for n in z.namelist() if n.endswith("/psychrolib.py")
                    )
                    meta = next(n for n in z.namelist() if n.endswith("/PKG-INFO"))
                    (target / "psychrolib.py").write_bytes(z.read(module))
                    info = target / "PsychroLib-2.5.0.dist-info"
                    info.mkdir(exist_ok=True)
                    (info / "METADATA").write_bytes(z.read(meta))
                    (info / "LICENSE.txt").write_bytes(
                        Path(__file__).with_name("PsychroLib-LICENSE.txt").read_bytes()
                    )
    return manifest
