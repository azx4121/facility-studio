"""Retain the upstream Windows wheel's sibling DLL directory in frozen apps.

https://pyinstaller.org/en/stable/hooks.html#PyInstaller.utils.hooks.collect_delvewheel_libs_directory
"""

from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import collect_delvewheel_libs_directory

if is_win:
    datas, binaries = collect_delvewheel_libs_directory(
        "CoolProp", libdir_name="coolprop.libs"
    )
