"""Localize Tk's hardcoded Cocoa app menu using public AppKit properties.

Only this process's application menu titles change. Actions, targets, key
bindings, OS settings and other applications are never changed.
Tk 8.6 source: macosx/tkMacOSXMenus.c (_defaultApplicationMenuItems).
"""

import ctypes
import sys


class NativeApplicationMenu:
    def __init__(self):
        self.lib = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        self.lib.objc_getClass.argtypes = [ctypes.c_char_p]
        self.lib.objc_getClass.restype = ctypes.c_void_p
        self.lib.sel_registerName.argtypes = [ctypes.c_char_p]
        self.lib.sel_registerName.restype = ctypes.c_void_p
        address = ctypes.cast(self.lib.objc_msgSend, ctypes.c_void_p).value

        def signature(result, *args):
            return ctypes.CFUNCTYPE(result, ctypes.c_void_p, ctypes.c_void_p, *args)(
                address
            )

        self.pointer = signature(ctypes.c_void_p)
        self.count = signature(ctypes.c_ulong)
        self.index = signature(ctypes.c_void_p, ctypes.c_ulong)
        self.utf8 = signature(ctypes.c_char_p)
        self.string = signature(ctypes.c_void_p, ctypes.c_char_p)
        self.set_title = signature(None, ctypes.c_void_p)

    def selector(self, name):
        return self.lib.sel_registerName(name.encode("ascii"))

    def items(self):
        app = self.pointer(
            self.lib.objc_getClass(b"NSApplication"), self.selector("sharedApplication")
        )
        menu = self.pointer(app, self.selector("mainMenu"))
        if not menu or not self.count(menu, self.selector("numberOfItems")):
            return []
        first = self.index(menu, self.selector("itemAtIndex:"), 0)
        application_menu = self.pointer(first, self.selector("submenu"))
        if not application_menu:
            return []
        output = []
        for i in range(self.count(application_menu, self.selector("numberOfItems"))):
            item = self.index(application_menu, self.selector("itemAtIndex:"), i)
            title = self.pointer(item, self.selector("title"))
            text = self.utf8(title, self.selector("UTF8String")).decode("utf-8")
            output.append((item, text))
        return output

    def rename(self, item, title):
        string = self.string(
            self.lib.objc_getClass(b"NSString"),
            self.selector("stringWithUTF8String:"),
            title.encode("utf-8"),
        )
        self.set_title(item, self.selector("setTitle:"), string)


def translated_title(title):
    exact = {
        "Preferences…": "偏好設定…",
        "Services": "服務",
        "Hide Others": "隱藏其他程式",
        "Show All": "全部顯示",
    }
    if title in exact:
        return exact[title]
    for prefix, zh in [("Hide ", "隱藏 "), ("Quit ", "結束 "), ("About ", "關於 ")]:
        if title.startswith(prefix):
            return zh + title[len(prefix) :]
    return title


def localize_application_menu():
    if sys.platform != "darwin":
        return
    menu = NativeApplicationMenu()
    for item, title in menu.items():
        localized = translated_title(title)
        if localized != title:
            menu.rename(item, localized)


def application_menu_titles():
    return (
        [text for _, text in NativeApplicationMenu().items()]
        if sys.platform == "darwin"
        else []
    )
