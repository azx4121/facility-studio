"""Copy only regular cold JSON traces, never traverse pytest current symlinks."""
import argparse
import os
from pathlib import Path
import shutil
import stat


def preserve(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError('Trace output must be new')
    if not source.exists():
        return 0
    if source.is_symlink() or not source.is_dir() or getattr(source, 'is_junction', lambda: False)():
        raise ValueError('Invalid trace source')
    output.mkdir(parents=True)
    count = 0
    for root, dirs, files in os.walk(source, followlinks=False):
        base = Path(root)
        dirs[:] = [name for name in dirs if not (base / name).is_symlink()
                   and not getattr(base / name, 'is_junction', lambda: False)()]
        if 'Cold_Startup_Trace.json' not in files:
            continue
        path = base / 'Cold_Startup_Trace.json'
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink() or getattr(metadata, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Cold trace is not a regular file')
        target = output / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print('Preserved cold startup traces:', preserve(args.source, args.output))
