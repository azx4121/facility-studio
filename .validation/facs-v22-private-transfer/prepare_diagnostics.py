"""Copy only non-executable diagnostics to an isolated Actions artifact root.

All sources are known validation evidence directories, not candidate download or
build-output roots. ZIP inputs and executable suffixes are never eligible.
"""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from private_draft_transfer import GateError, regular_file, require, sha256

ALLOWED = {'.json', '.jsonl', '.log', '.txt', '.png', '.xml', '.csv', '.xlsx'}
BINARY_SUFFIXES = {'.exe', '.dll', '.pyd', '.so', '.dylib', '.com', '.msi', '.bat', '.cmd', '.ps1'}
MAGICS = (b'MZ', b'\x7fELF', b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
          b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe')


def safe_diagnostic(path):
    require(path.suffix.lower() in ALLOWED, 'Unsupported diagnostic suffix.')
    with path.open('rb') as stream:
        start = stream.read(8)
    require(not any(start.startswith(magic) for magic in MAGICS), 'Executable bytes disguised as diagnostics.')
    if path.suffix.lower() == '.xlsx':
        with zipfile.ZipFile(path) as archive:
            require(archive.testzip() is None, 'Corrupt diagnostic XLSX.')
            require('[Content_Types].xml' in archive.namelist() and 'xl/workbook.xml' in archive.namelist(),
                    'Unexpected diagnostic archive.')
            for info in archive.infolist():
                require(Path(info.filename).suffix.lower() not in BINARY_SUFFIXES,
                        'Executable member inside diagnostic XLSX.')
                if not info.is_dir():
                    with archive.open(info) as member:
                        prefix = member.read(8)
                    require(not any(prefix.startswith(magic) for magic in MAGICS),
                            'Executable bytes inside diagnostic XLSX.')
    else:
        require(not start.startswith(b'PK\x03\x04'), 'Archive disguised as a non-XLSX diagnostic.')


def prepare(sources, output):
    output = Path(output).absolute()
    require(not output.exists(), 'Diagnostics destination must be new.')
    # Stage separately, then rename atomically. On any validation failure the
    # upload glob still has no destination and cannot publish partial contents.
    staging = output.with_name(output.name + '.staging')
    require(not staging.exists(), 'Uncertain diagnostics staging state; inspect before retry.')
    staging.mkdir(parents=True, exist_ok=False)
    records = []
    for index, root in enumerate(sources):
        root = Path(root).absolute()
        if not root.exists():
            continue
        require(root.is_dir() and root.name in {'facs-v22-evidence', 'evidence', 'facs-v22-independent-2025'},
                'Unexpected diagnostics source directory.')
        for path in sorted(root.rglob('*')):
            if path.is_dir():
                require(not path.is_symlink() and not (hasattr(path, 'is_junction') and path.is_junction()),
                        'Linked diagnostics directory is forbidden.')
                continue
            regular_file(path)
            if path.suffix.lower() not in ALLOWED:
                continue
            safe_diagnostic(path)
            relative = Path(str(index) + '-' + root.name) / path.relative_to(root)
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            # Inspect copied bytes too. Source mutations cannot smuggle a binary
            # after the first check but before artifact staging.
            safe_diagnostic(destination)
            records.append({'path': relative.as_posix(), 'bytes': destination.stat().st_size,
                            'sha256': sha256(destination)})
    require(bool(records), 'No allowlisted diagnostics were produced.')
    (staging / 'DIAGNOSTICS_INVENTORY.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    staging.rename(output)
    print(json.dumps({'diagnostic_files': len(records), 'executable_uploaded': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.source, args.output)
    except GateError as error:
        raise SystemExit('DIAGNOSTICS STOPPED: ' + str(error))
