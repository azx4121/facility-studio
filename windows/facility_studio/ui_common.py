import sys
from pathlib import Path

try:
    import tkinter as tk
except ImportError:
    tk = None

# Tk's EXTENDED_MASK (AnyModifier << 3) carries the Windows extended-key bit.
# The dedicated Delete key is extended; the keypad Del/decimal key is not.
WINDOWS_EXTENDED_KEY = 0x40000


def is_keypad_decimal(event, platform=None):
    """Recognize a numeric keypad separator without changing ordinary Delete."""
    platform = sys.platform if platform is None else platform
    return getattr(event, "keysym", "") in (
        "KP_Decimal",
        "KP_Separator",
        "KP_Delete",
        "decimal",
        "separator",
    ) or (
        platform == "win32"
        and (
            getattr(event, "keycode", None) == 110
            or (
                getattr(event, "keycode", None) == 46
                and getattr(event, "keysym", "") == "Delete"
                and isinstance(getattr(event, "state", None), int)
                and not event.state & WINDOWS_EXTENDED_KEY
            )
        )
    )


def insert_keypad_decimal(event):
    widget = event.widget
    if not is_keypad_decimal(event):
        return None
    # Keep editing shortcuts intact. Num Lock uses different modifier bits
    # on Windows, Aqua and X11, so a shared Alt/Command mask is incorrect.
    shortcut_mask = {"win32": 0x4 | 0x20 | 0x20000,
                     "darwin": 0x4 | 0x8 | 0x10}.get(sys.platform, 0x4 | 0x8 | 0x40)
    if getattr(event, "state", 0) & shortcut_mask:
        return None
    if str(widget.cget("state")) != "normal":
        return "break"
    if hasattr(widget, "instate") and (
        widget.instate(["disabled"]) or widget.instate(["readonly"])
    ):
        return "break"
    try:
        if widget.selection_present():
            widget.icursor("sel.first")
            widget.delete("sel.first", "sel.last")
    except tk.TclError:
        pass
    widget.insert("insert", ".")
    return "break"


def install_numeric_keyboard(window):
    """Put the keypad handler before Tk's Entry class bindings in every window."""
    tag = "FacilityNumericInput"
    def attach(event=None, widget=None):
        current = widget if widget is not None else event.widget
        # Tcl-created combobox popdowns have a widget path but no Python wrapper.
        if not hasattr(current, "winfo_class"):
            return
        if current.winfo_class() in ("Entry", "TEntry", "Spinbox", "TSpinbox"):
            tags = current.bindtags()
            if tag not in tags:
                current.bindtags((tags[0], tag, *tags[1:]))
        if widget is not None:
            for child in current.winfo_children():
                attach(widget=child)

    # Tcl interpreters are shared by Toplevels. Install listeners once, but
    # always attach existing entries when another application window opens.
    if not window.bind_class(tag, "<KeyPress>"):
        window.bind_class(tag, "<KeyPress>", insert_keypad_decimal)
        window.bind_all("<Map>", attach, add="+")
        window.bind_all("<FocusIn>", attach, add="+")
    attach(widget=window)



def install_combobox_wheel_guard(window):
    """Keep wheel events for the page, while retaining native choice controls.

    An application-only class tag copies Tk's actual platform bindings except
    wheel gestures. Unlike returning "break", omitting these bindings lets the
    event reach the enclosing scroll frame/window. Focus does not change this
    policy. Tk 9 precision gestures relay their vertical component through the
    same wheel path. Popup lists retain native scrolling and selection.
    """
    tag = "FacilityCombobox"
    root = window._root()

    def attach(event=None, widget=None):
        current = widget if widget is not None else event.widget
        # A Tk-created popup may arrive as a path, not a Python widget.
        if not hasattr(current, "winfo_class"):
            return
        if current.winfo_class() == "TCombobox":
            current.bindtags(tuple(tag if item == "TCombobox" else item
                                   for item in current.bindtags()))
        if widget is not None:
            for child in current.winfo_children():
                attach(widget=child)

    # Keep Tk's global TCombobox bindings intact. Each interpreter receives its
    # own copy, including its platform-specific keyboard and pointer bindings.
    if not getattr(root, "_facility_combobox_wheel_guard", False):
        for sequence in root.bind_class("TCombobox"):
            if "TouchpadScroll" in sequence:
                # Tk 9 encodes both trackpad axes in %D. Relay only the
                # vertical component through the existing page wheel path;
                # never call Tk's combobox selection-scrolling procedure.
                root.bind_class(tag, sequence, """
                    if {[lindex [tk::PreciseScrollDeltas %D] 1] != 0} {
                        event generate %W <MouseWheel> \
                            -delta [lindex [tk::PreciseScrollDeltas %D] 1] \
                            -x %x -y %y
                    }
                    break
                """)
                continue
            if any(wheel in sequence for wheel in (
                "MouseWheel", "TouchpadScroll", "Button-4>", "Button-5>",
                "Button-6>", "Button-7>",
            )):
                continue
            root.bind_class(tag, sequence, root.bind_class("TCombobox", sequence))
        root.bind_all("<Map>", attach, add="+")
        root.bind_all("<FocusIn>", attach, add="+")
        root._facility_combobox_wheel_guard = True
    attach(widget=window)


def app_icon(window):
    from .localized_tk import attach_window

    attach_window(window)
    install_numeric_keyboard(window)
    install_combobox_wheel_guard(window)
    from .native_redraw import install_native_redraw

    install_native_redraw(window)
    base = Path(__file__).with_name("resources")
    try:
        window._app_icon = tk.PhotoImage(file=str(base / "app.png"))
        window.iconphoto(True, window._app_icon)
        if sys.platform == "win32":
            window.iconbitmap(str(base / "app.ico"))
    except (tk.TclError, OSError):
        pass


def quality_style(q):
    return (
        "Error.TLabel"
        if q["failed"]
        else "Warn.TLabel" if q["pending"] or q.get("deferred", 0) else "Good.TLabel"
    )


def quality_text(q):
    rows = [x["name"] + "：" + x["detail"] for state in ("未達", "待資料", "待後續")
            for x in q["items"] if x["status"] == state]
    return (
        q["status"]
        + f"｜未達 {q['failed']} 項／待資料 {q['pending']} 項／待後續階段 {q.get('deferred', 0)} 項\n"
        + "\n".join(rows[:1])
        + ("\n其餘明細請查看報告。" if len(rows) > 1 else "")
    )
