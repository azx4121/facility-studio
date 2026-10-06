"""Seal copied frameworks with Apple's own signer, deepest objects first."""

from pathlib import Path
import shutil
import subprocess
import sys

MACHO_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"}


def relocate_framework_build_configuration(app):
    """Retain Tcl/Tk build-only scripts in Resources, not nested-code slots.

    These files configure extension compilation; the shipped runtime does not
    compile extensions. Apple treats files at a framework's version root as
    nested code, while Resources seals plain scripts as data (TN2206).
    """
    relocated = []
    for framework, names in (
        ("Tcl.framework", ("tclConfig.sh", "tclooConfig.sh")),
        ("Tk.framework", ("tkConfig.sh",)),
    ):
        root = (Path(app) / "Contents/Frameworks/Python.framework/Versions/3.13/Frameworks"
                / framework)
        version = root / "Versions/8.6"
        resources = version / "Resources/BuildConfiguration"
        resources.mkdir(parents=True)
        for name in names:
            original = version / name
            target = resources / name
            if not original.is_file() or original.is_symlink() or target.exists():
                raise ValueError("Unexpected pinned framework configuration: " + str(original))
            shutil.move(str(original), target)
            alias = root / name
            if alias.is_symlink():
                alias.unlink()
            elif alias.exists():
                raise ValueError("Unexpected framework build-config alias: " + str(alias))
            relocated.append(str(target.relative_to(app)))
    return relocated


def sign_app(app, log_path):
    if sys.platform != "darwin":
        raise RuntimeError("Apple native signing requires macOS.")
    app = Path(app).resolve()
    relocated = relocate_framework_build_configuration(app)
    binaries = []
    for path in app.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as file:
                if file.read(4) in MACHO_MAGIC:
                    binaries.append(path)
    for signature in sorted(app.rglob("_CodeSignature"), key=lambda p: len(p.parts), reverse=True):
        if signature.is_dir() and not signature.is_symlink():
            shutil.rmtree(signature)
    frameworks = sorted(
        (p for p in app.rglob("*.framework") if p.is_dir() and not p.is_symlink()),
        key=lambda p: len(p.parts), reverse=True,
    )
    with Path(log_path).open("w", encoding="utf-8") as log:
        for target in [*sorted(binaries), *frameworks, app]:
            subprocess.run(
                ["/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none", str(target)],
                stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60,
            )
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=4", str(app)],
            stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60,
        )
    return dict(macho_files=len(binaries), frameworks=len(frameworks),
                build_configuration_resources=relocated,
                apple_native_signature_verified=True, developer_id=False, notarized=False)
