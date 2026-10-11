"""Keypad decimal regressions and delivered native-widget acceptance."""
import copy
import sys
from types import SimpleNamespace
from unittest.mock import patch

from .ui_common import WINDOWS_EXTENDED_KEY, insert_keypad_decimal, is_keypad_decimal
from .version import VERSION


def run_checks():
    checks = []

    def record(name, action):
        assert action(), name
        checks.append({"name": name, "passed": True})

    cases = [
        ("win32", "Delete", 46, 0, True),
        ("win32", "Delete", 46, 8, True),
        ("win32", "Delete", 46, WINDOWS_EXTENDED_KEY, False),
        ("win32", "Delete", 46, WINDOWS_EXTENDED_KEY | 8, False),
        ("win32", "period", 110, 8, True),
        ("win32", "comma", 110, 8, True),
        ("win32", "period", 190, 0, False),
        ("darwin", "period", 47, 0, False),
    ]
    for platform in ("win32", "darwin", "linux"):
        for sym in ("KP_Decimal", "KP_Separator", "KP_Delete", "decimal", "separator"):
            cases.append((platform, sym, 91, 0, True))
    for platform, sym, code, state, expected in cases:
        event = SimpleNamespace(keysym=sym, keycode=code, state=state)
        record("Key identity %s/%s/%s/%s" % (platform, sym, code, state),
               lambda e=event, p=platform, want=expected: is_keypad_decimal(e, p) == want)
    record("Missing Windows extended metadata preserves ambiguous Delete",
           lambda: not is_keypad_decimal(SimpleNamespace(keysym="Delete", keycode=46), "win32"))

    class Entry:
        def __init__(self, text="1234", cursor=4, selection=None, state="normal", ttk_state=()):
            self.text, self.cursor, self.selection = text, cursor, selection
            self.state, self.ttk_state = state, ttk_state
        def cget(self, name):
            return self.state
        def instate(self, flags):
            return all(flag in self.ttk_state for flag in flags)
        def selection_present(self):
            return self.selection is not None
        def icursor(self, position):
            self.cursor = self.selection[0] if position == "sel.first" else position
        def delete(self, first, last):
            start, end = self.selection
            self.text = self.text[:start] + self.text[end:]
            self.cursor = start if start <= self.cursor < end else self.cursor - (end-start) if self.cursor >= end else self.cursor
            self.selection = None
        def insert(self, position, text):
            self.text = self.text[:self.cursor] + text + self.text[self.cursor:]
            self.cursor += len(text)

    for platform, sym, code, state, expected in cases:
        widget = Entry(text="12", cursor=2)
        event = SimpleNamespace(widget=widget, keysym=sym, keycode=code, state=state)
        with patch.object(sys, "platform", platform):
            result = insert_keypad_decimal(event)
        record("Actual handler %s/%s/%s/%s" % (platform, sym, code, state),
               lambda w=widget, r=result, want=expected: w.text == ("12." if want else "12")
               and r == ("break" if want else None))
    for cursor in (0, 1, 3, 4):
        widget = Entry(cursor=cursor, selection=(1, 3))
        insert_keypad_decimal(SimpleNamespace(widget=widget, keysym="KP_Decimal", keycode=91, state=0))
        record("Selection replacement at its start, original cursor %d" % cursor,
               lambda w=widget: w.text == "1.4" and w.cursor == 2)
    for state, ttk_state in (("disabled", ()), ("readonly", ()), ("normal", ("disabled",)), ("normal", ("readonly",))):
        widget = Entry(state=state, ttk_state=ttk_state)
        response = insert_keypad_decimal(SimpleNamespace(widget=widget, keysym="KP_Decimal", keycode=91, state=0))
        record("Inactive entry %s/%s" % (state, ttk_state),
               lambda w=widget, r=response: w.text == "1234" and r == "break")
    for platform, states in (("win32", (4, 32, 0x20000)), ("darwin", (4, 8, 16)), ("linux", (4, 8, 64))):
        for state in states:
            widget = Entry()
            with patch.object(sys, "platform", platform):
                result = insert_keypad_decimal(SimpleNamespace(widget=widget, keysym="KP_Decimal", keycode=91, state=state))
            record("Shortcut remains native %s/%d" % (platform, state),
                   lambda w=widget, r=result: w.text == "1234" and r is None)
    return {"version": VERSION, "passed": True, "checks": checks,
            "physical_keyboard_tested": False}


def run_ui(root, app, main, check, pump):
    """Native event dispatch; Windows also receives real WM_KEYDOWN messages.

    These are OS message tests, not an attached physical-keyboard claim.
    """
    import tkinter as tk
    from tkinter import ttk
    from . import i18n
    from .ahu_desktop import AHUWindow
    from .tools_view import QuickToolsWindow
    from .ui_common import install_numeric_keyboard

    original_main = copy.deepcopy(main.snapshot())
    language, current = i18n.language(), app.current
    saved_pages = {name: page.data() for name, page in app.pages.items()}
    child = quick = test_window = None

    def require(value, detail):
        if not value:
            raise AssertionError(detail)
        return True

    def reset(entry, text="12", cursor="end"):
        entry.delete(0, "end")
        entry.insert(0, text)
        entry.selection_clear()
        entry.icursor(cursor)
        # Tool changes can map the new page after this callback returns.
        # A native focus request made before Map is discarded on Windows.
        pump()
        entry.winfo_toplevel().lift()
        entry.focus_force()
        pump()
        require(root.focus_get() is entry,
                "Test entry did not receive focus: mapped=%s focus=%s target=%s" %
                (entry.winfo_ismapped(), root.focus_get(), entry))

    def event(entry, kind="keypad"):
        if sys.platform == "win32":
            if kind == "keypad":
                entry.event_generate("<KeyPress>", keycode=46, state=0)
            elif kind == "delete":
                entry.event_generate("<KeyPress>", keycode=46, state=WINDOWS_EXTENDED_KEY)
            elif kind == "numlock":
                entry.event_generate("<KeyPress>", keycode=110, state=8)
            else:
                entry.event_generate("<KeyPress-period>", state=0)
        else:
            # Aqua does not expose every X11 KP symbol through event_generate;
            # KP_Decimal is translated by its key map before native dispatch.
            entry.event_generate("<KeyPress>", keysym="KP_Decimal" if kind in ("keypad", "numlock") else "Delete" if kind == "delete" else "period", state=0)
        pump()

    try:
        for lang in ("zh-Hant", "en"):
            i18n.set_language(lang, persist=False)
            for name, key in (("electrical", "power"), ("duct", "flow"), ("gas", "flow"),
                              ("lighting", "area"), ("water", "flow"),
                              ("air", "temperature"), ("units", "value")):
                def form(tool=name, field=key):
                    app.show_tool(tool)
                    root.deiconify()
                    root.lift()
                    page = app.active_page()
                    page.reset()
                    entry = page.widgets[field]
                    reset(entry)
                    event(entry)
                    entry.event_generate("<KeyPress-5>", state=0)
                    page.calculate()
                    pump()
                    return require(entry.get() == "12.5" and page.result is not None,
                                   "%s/%s decimal missing: %r" % (tool, field, entry.get()))
                check("V5510 native keypad live form %s/%s" % (lang, name), form)

        app.show_tool("electrical")
        page = app.active_page()
        entry = page.widgets["power"]
        for kind in ("keypad", "numlock", "period"):
            def insertion(method=kind):
                reset(entry)
                event(entry, method)
                return require(entry.get() == "12.", method + " inserted incorrectly: " + entry.get())
            check("V5510 native single insertion " + kind, insertion)
        def selected():
            reset(entry, "1234", 4)
            entry.selection_range(1, 3)
            event(entry)
            return require(entry.get() == "1.4", "Selection inserted at wrong location: " + entry.get())
        check("V5510 native partial selection replacement", selected)
        def regular_delete():
            reset(entry, "123", 1)
            event(entry, "delete")
            return require(entry.get() == "13", "Ordinary Delete intercepted: " + entry.get())
        check("V5510 native dedicated Delete unchanged", regular_delete)
        for state in ("disabled", "readonly"):
            def inactive(flag=state):
                reset(entry)
                entry.state([flag])
                try:
                    event(entry)
                    return require(entry.get() == "12", "Inactive entry changed")
                finally:
                    entry.state(["!" + flag])
            check("V5510 native ttk state prevents input " + state, inactive)
        def partial_decimal():
            reset(entry, "123")
            entry.selection_range(0, "end")
            event(entry)
            page.calculate()
            return require(entry.get() == "." and page.result is None
                           and app.export_button.instate(["disabled"]), "Incomplete draft resurrected output")
        check("V5510 native incomplete decimal retains draft and blocks export", partial_decimal)

        main.root.deiconify()
        main.root.lift()
        main.show_page(0)
        pump()
        def workbench():
            entry = main.widgets["oa_t"]
            reset(entry)
            event(entry)
            return require(entry.get() == "12.", "Workbench did not accept keypad decimal")
        check("V5510 native workbench keypad", workbench)

        child = AHUWindow(main.root)
        pump()
        def ahu():
            child.reveal("summer_t")
            entry = child.widgets["summer_t"]
            reset(entry)
            event(entry)
            return require(entry.get() == "12.", "AHU did not accept keypad decimal")
        check("V5510 native standalone AHU keypad", ahu)
        quick = QuickToolsWindow(main.root, main)
        pump()
        def quick_form():
            quick.tool.set("濕空氣計算")
            quick.build()
            entry = quick.widgets["first"]
            reset(entry)
            event(entry)
            return require(entry.get() == "12.", "Quick tool did not accept keypad decimal")
        check("V5510 native engineering quick tool keypad", quick_form)

        test_window = tk.Toplevel(root)
        extra = ttk.Entry(test_window)
        extra.pack()
        install_numeric_keyboard(test_window)
        pump()
        def dynamic():
            reset(extra)
            event(extra)
            tags = extra.bindtags()
            return require(extra.get() == "12." and tags.count("FacilityNumericInput") == 1
                           and tags.index("FacilityNumericInput") < tags.index("TEntry"),
                           "New-window input binding missing or duplicated")
        check("V5510 native newly created window entry", dynamic)
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            post = ctypes.WinDLL("user32", use_last_error=True).PostMessageW
            post.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
            post.restype = wintypes.BOOL

            def windows_message(vk, extended=False):
                bits = 1 | (0x53 << 16) | (0x1000000 if extended else 0)
                if not post(extra.winfo_id(), 0x100, vk, bits):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not post(extra.winfo_id(), 0x101, vk, bits | 0xC0000000):
                    raise ctypes.WinError(ctypes.get_last_error())
                pump()

            def original_failure():
                reset(extra)
                tags = extra.bindtags()
                extra.bindtags(tuple(tag for tag in tags if tag != "FacilityNumericInput"))
                try:
                    windows_message(46)
                    return require(extra.get() == "12", "Expected original missing-decimal path")
                finally:
                    extra.bindtags(tags)
            check("V5510 native Windows reproduces unhandled keypad Del", original_failure)
            for vk, extended, initial, cursor, expected in ((46, False, "12", "end", "12."),
                                                           (110, False, "12", "end", "12."),
                                                           (46, True, "123", 1, "13")):
                def message(code=vk, ext=extended, text=initial, pos=cursor, want=expected):
                    reset(extra, text, pos)
                    windows_message(code, ext)
                    return require(extra.get() == want, "Windows message produced: " + extra.get())
                check("V5510 native Windows OS message %d/extended=%s" % (vk, extended), message)
    finally:
        for window in (test_window, getattr(quick, "win", None), getattr(child, "win", None)):
            if window is not None and window.winfo_exists():
                window.destroy()
        if quick is not None and quick in main.children:
            main.children.remove(quick)
        for name, values in saved_pages.items():
            page = app.pages[name]
            page.suspended = True
            try:
                for key, value in values.items():
                    page.variables[key].set(value)
                page.previous = page.data()
            finally:
                page.suspended = False
            page.update_visibility()
            page.calculate()
        main.apply_project(original_main)
        i18n.set_language(language, persist=False)
        app.show_tool(current)
        pump()
