"""Apply a documented, minimal patch to the pinned Matplotlib font discovery.

The original wheel and license remain attributed to Matplotlib. This only
bounds external discovery commands; directory-based font discovery remains.
"""

import base64
import csv
import hashlib
from pathlib import Path


def patch_font_discovery(packages):
    packages = Path(packages)
    path = packages / "matplotlib/font_manager.py"
    original = path.read_text(encoding="utf-8")
    substitutions = (
        ("subprocess.check_output(['fc-list', '--help'])",
         "subprocess.check_output(['fc-list', '--help'], timeout=5)"),
        ("subprocess.check_output(['fc-list', '--format=%{file}\\\\n'])",
         "subprocess.check_output(['fc-list', '--format=%{file}\\\\n'], timeout=5)"),
        ('subprocess.check_output(["system_profiler", "-xml", "SPFontsDataType"])',
         'subprocess.check_output(["system_profiler", "-xml", "SPFontsDataType"], timeout=5)'),
        ("except (OSError, subprocess.CalledProcessError):\n        return []",
         "except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):\n        return []"),
        ("except (OSError, subprocess.CalledProcessError, plistlib.InvalidFileException):",
         "except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, plistlib.InvalidFileException):"),
    )
    patched = original
    for old, new in substitutions:
        if patched.count(old) != 1:
            raise ValueError("Pinned Matplotlib font-discovery source changed: " + old)
        patched = patched.replace(old, new)
    path.write_text(patched, encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).digest()
    records = list(packages.glob("matplotlib-*.dist-info/RECORD"))
    if len(records) != 1:
        raise ValueError("Expected exactly one pinned Matplotlib RECORD")
    with records[0].open(newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))
    found = 0
    for row in rows:
        if row[0] == "matplotlib/font_manager.py":
            row[1] = "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
            row[2] = str(path.stat().st_size)
            found += 1
    if found != 1:
        raise ValueError("Matplotlib RECORD did not describe font_manager.py")
    with records[0].open("w", newline="", encoding="utf-8") as file:
        csv.writer(file).writerows(rows)
    return dict(file="matplotlib/font_manager.py", timeout_seconds=5,
                original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                patched_sha256=hashlib.sha256(patched.encode()).hexdigest(),
                record_updated=True)
