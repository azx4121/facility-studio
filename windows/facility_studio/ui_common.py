from pathlib import Path
import sys
import tkinter as tk


def is_keypad_decimal(event, platform=None):
    """Recognize a numeric keypad separator without changing ordinary Delete."""
    platform = sys.platform if platform is None else platform
    return getattr(event, "keysym", "") in (
        "KP_Decimal",
        "KP_Separator",
        "decimal",
        "separator",
    ) or (platform == "win32" and getattr(event, "keycode", None) == 110)


def insert_keypad_decimal(event):
    widget = event.widget
    if not is_keypad_decimal(event):
        return None
    if str(widget.cget("state")) != "normal":
        return "break"
    try:
        if widget.selection_present():
            widget.delete("sel.first", "sel.last")
    except tk.TclError:
        pass
    widget.insert("insert", ".")
    return "break"


def install_numeric_keyboard(window):
    """Put the keypad handler before Tk's Entry class bindings in every window."""
    tag = "FacilityNumericInput"
    if getattr(window.tk, "_facility_numeric_installed", False):
        return
    # Tcl interpreters are shared by Toplevels. Inspect the binding itself.
    if window.bind_class(tag, "<KeyPress>"):
        return
    window.bind_class(tag, "<KeyPress>", insert_keypad_decimal)

    def attach(event=None, widget=None):
        current = widget if widget is not None else event.widget
        if current.winfo_class() in ("Entry", "TEntry", "Spinbox", "TSpinbox"):
            tags = current.bindtags()
            if tag not in tags:
                current.bindtags((tags[0], tag, *tags[1:]))
        if widget is not None:
            for child in current.winfo_children():
                attach(widget=child)

    window.bind_all("<Map>", attach, add="+")
    attach(widget=window)


def app_icon(window):
    from .localized_tk import attach_window

    attach_window(window)
    install_numeric_keyboard(window)
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
        else "Warn.TLabel" if q["pending"] else "Good.TLabel"
    )


def quality_text(q):
    rows = [x["name"] + "：" + x["detail"] for x in q["items"] if x["status"] != "通過"]
    return (
        q["status"]
        + f"｜未達 {q['failed']} 項／待資料 {q['pending']} 項\n"
        + "\n".join(rows[:1])
        + ("\n其餘明細請查看報告。" if len(rows) > 1 else "")
    )
