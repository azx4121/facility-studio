import struct
import sys

try:
    import tkinter
    import venv

    assert sys.version_info[:2] == (3, 13)
    assert struct.calcsize("P") == 8
except (ImportError, AssertionError):
    raise SystemExit(1)
print(sys.executable)
