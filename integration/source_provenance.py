"""Independent checkout identity for native builds and second-host verification."""
import hashlib
import importlib.util
import io
import json
import marshal
from pathlib import Path
import re
import subprocess
import sys
from types import CodeType

EXPECTED_VERSION = "5.7.3"
PROVENANCE_FIELDS = ("provenance_schema", "commit", "version", "source_platform",
                     "build_channel", "source_clean", "build_inputs_sha256",
                     "product_source_sha256")


def _git(root, *args):
    try:
        return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Cannot establish source identity from Git.") from exc


def _paths(raw):
    return [item.decode("utf-8") for item in raw.split(b"\0") if item]


def _normalized_code(code):
    """Compare bytecode content without machine-dependent compiler filenames."""
    return code.replace(co_filename="<build-input>", co_consts=tuple(
        _normalized_code(value) if isinstance(value, CodeType) else value
        for value in code.co_consts))


def _generated_cache(path, root):
    # PyInstaller copies resources recursively. Nothing under that directory,
    # including genuine bytecode, may be omitted from its complete inventory.
    if "resources" in path.relative_to(root).parts or path.parent.name != "__pycache__":
        return False
    tag = re.escape(sys.implementation.cache_tag)
    match = re.fullmatch(r"(.+)\." + tag + r"(?:\.opt-([12]))?\.pyc", path.name)
    if not match:
        return False
    source = path.parent.parent / (match.group(1) + ".py")
    if not source.is_file() or source.is_symlink():
        return False
    try:
        data = path.read_bytes()
        if (len(data) < 16 or data[:4] != importlib.util.MAGIC_NUMBER
                or int.from_bytes(data[4:8], "little") not in (0, 1, 3)):
            return False
        stream = io.BytesIO(data[16:])
        cached = marshal.load(stream)
        if not isinstance(cached, CodeType) or stream.read():
            return False
        expected = compile(source.read_bytes(), "<build-input>", "exec", dont_inherit=True,
                           optimize=int(match.group(2) or 0))
        # A filename resembling a cache is insufficient: require bytecode for
        # the actual neighboring source, never execute the cached code.
        return _normalized_code(cached) == expected
    except (OSError, EOFError, ValueError, TypeError, SyntaxError):
        return False


def _files(root, relative):
    base = root / relative
    if any((root / Path(*base.relative_to(root).parts[:n])).is_symlink()
           for n in range(1, len(base.relative_to(root).parts) + 1)):
        raise RuntimeError(f"Symlink is not a reproducible build input: {base}")
    if not base.exists():
        raise RuntimeError(f"Missing build input: {relative}")
    paths = [base] if base.is_file() else base.rglob("*")
    result = {}
    for path in paths:
        if path.is_symlink():
            raise RuntimeError(f"Symlink is not a reproducible build input: {path}")
        if path.is_file() and not _generated_cache(path, root):
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _head_hashes(root, commit, paths):
    entries = _git(root, "ls-tree", "-rz", commit, "--", *paths).split(b"\0")
    files = []
    for entry in entries:
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, object_id = metadata.split()
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise RuntimeError(f"Unsupported Git build input: {name!r}")
        files.append((name.decode("utf-8"), object_id))
    # Read committed blobs, not index hashes: staged edits must not claim HEAD.
    try:
        result = subprocess.run(["git", "cat-file", "--batch"], cwd=root,
                                input=b"".join(oid + b"\n" for _, oid in files),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Cannot read committed build inputs.") from exc
    remaining = result.stdout
    hashes = {}
    for name, object_id in files:
        header, remaining = remaining.split(b"\n", 1)
        oid, kind, size = header.split()
        if oid != object_id or kind != b"blob":
            raise RuntimeError("Git returned unexpected build input identity.")
        length = int(size)
        hashes[name] = hashlib.sha256(remaining[:length]).hexdigest()
        remaining = remaining[length + 1:]
    return hashes


def provenance_digest(manifest):
    selected = {key: manifest[key] for key in PROVENANCE_FIELDS}
    return hashlib.sha256(json.dumps(selected, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def expected_source_manifest(root, source_platform, *, expected_commit=None, allow_dirty=False):
    """Fingerprint this checkout independently of the bundle being inspected.

    Known source-suite evidence may change; product, resources, packaging inputs,
    and all other tracked files may not. Ignored/untracked product inputs are
    enumerated too, so .gitignore and assume-unchanged cannot hide shipped code.
    Dirty development builds require an explicit opt-in and cannot claim a clean
    stable/release identity. Only verified non-resource Python bytecode caches are omitted.
    """
    root = Path(root).resolve()
    if source_platform not in ("macos", "windows"):
        raise RuntimeError("Unsupported source platform.")
    commit = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("A full lowercase Git commit is required.")
    if expected_commit is not None and commit != expected_commit:
        raise RuntimeError("Checkout does not match the expected build commit.")
    product_prefix = source_platform + "/facility_studio"
    build_paths = ("integration", "windows/winrelease/hooks", "LICENSE", "LICENSE_LEGACY_MIT",
                   "THIRD_PARTY_NOTICES.md", "macos/macos/PsychroLib-LICENSE.txt")
    build = {}
    for relative in build_paths:
        build.update(_files(root, relative))
    product = _files(root, product_prefix)
    if not build or not product:
        raise RuntimeError("Build input and product source inventories must not be empty.")
    actual = dict(build, **product)
    committed = _head_hashes(root, commit, (*build_paths, product_prefix))
    differences = {name for name in set(actual) | set(committed) if actual.get(name) != committed.get(name)}
    changed = set(_paths(_git(root, "diff", "--name-only", "-z", "HEAD")))
    changed.update(_paths(_git(root, "ls-files", "--others", "--exclude-standard", "-z")))
    evidence_prefixes = ("windows/evidence/", "macos/evidence/")
    changes = sorted(differences | {name for name in changed if not name.startswith(evidence_prefixes)})
    if changes and not allow_dirty:
        raise RuntimeError("Dirty source tree cannot identify a release build: " + ", ".join(changes[:12])
                           + ". Commit reviewed inputs, or use --allow-dirty for non-release development only.")
    return dict(provenance_schema=1, commit=commit, version=EXPECTED_VERSION,
                source_platform=source_platform, build_channel="non-release" if changes else "stable",
                source_clean=not bool(changes),
                build_inputs_sha256=dict(sorted(build.items())),
                product_source_sha256={name[len(source_platform) + 1:]: digest
                                       for name, digest in sorted(product.items())})


def verify_source_unchanged(root, source_platform, expected_manifest):
    """Reject mid-build changes; generated packaging output is not a source input."""
    current = expected_source_manifest(root, source_platform, allow_dirty=True)
    if any(current[key] != expected_manifest[key] for key in
           ("commit", "version", "source_platform", "build_inputs_sha256", "product_source_sha256")):
        raise RuntimeError("Build inputs changed while freezing the application.")
