"""Native menus shared by the formal application and isolated test sessions."""

import os
import sys
import weakref


def _localize_top_menus(root, language):
    """Translate only this menu's authored cascades, identified by submenu.

    Menu context matters: the general catalog uses 說明 for Description, while
    this cascade is Help. Keep these labels local and never translate a custom
    action or application name merely because it shares an authored label.
    """
    if sys.platform not in ("darwin", "win32"):
        return
    menu = root._sandbox_menu
    if not menu.winfo_exists():
        return
    end = menu.index("end")
    for index in range(end + 1 if end is not None else 0):
        if menu.type(index) != "cascade":
            continue
        labels = menu._sandbox_top_labels.get(str(menu.entrycget(index, "menu")))
        if labels is not None:
            label = labels[1] if language == "en" else labels[0]
            if menu.entrycget(index, "label") != label:
                menu.entryconfigure(index, label=label)

    # Windows owns these Tk commands directly. Match registered command IDs,
    # not positions/text, so custom insertions and disabled states stay intact.
    # Cocoa application-menu handling remains on its existing separate path.
    if sys.platform == "win32":
        for submenu, labels_by_command in menu._sandbox_command_labels.items():
            if not submenu.winfo_exists():
                continue
            end = submenu.index("end")
            for index in range(end + 1 if end is not None else 0):
                if submenu.type(index) != "command":
                    continue
                labels = labels_by_command.get(str(submenu.entrycget(index, "command")))
                if labels is not None:
                    label = labels[1] if language == "en" else labels[0]
                    if submenu.entrycget(index, "label") != label:
                        submenu.entryconfigure(index, label=label)


class _NativeMenuLanguage:
    """Root-owned subscriber; coalesce updates after Tk builds its native menu."""

    def __init__(self, root):
        self.root = weakref.ref(root)

    def winfo_exists(self):
        root = self.root()
        return root is not None and root.winfo_exists()

    def refresh_language(self):
        root = self.root()
        if root is None or not root.winfo_exists():
            return
        pending = getattr(root, "_sandbox_menu_after", None)
        if pending is not None:
            root.after_cancel(pending)

        from . import i18n
        # Tk may queue a native menu rebuild when a cascade label changes.
        # Finish Tk writes before queuing the AppKit title-restoration pass.
        _localize_top_menus(root, i18n.language())

        def localize():
            from .sandbox_native_menu import localize_application_menu
            root._sandbox_menu_after = None
            localize_application_menu(i18n.language())

        root._sandbox_menu_after = root.after_idle(localize)


def install_menus(root):
    if not (os.environ.get("FACILITY_STUDIO_NATIVE_MENUS")
            or os.environ.get("FACILITY_STUDIO_SANDBOX")):
        return
    import tkinter as tk
    from .localized_tk import messagebox
    from .engineering_verification import BUILD

    root.title("Facility Studio " + BUILD)
    menu = tk.Menu(root)
    menu._sandbox_command_labels = {}

    def add_command(submenu, *, label, english, command):
        submenu.add_command(label=label, command=command)
        command_id = str(submenu.entrycget(submenu.index("end"), "command"))
        menu._sandbox_command_labels.setdefault(submenu, {})[command_id] = (label, english)

    apple = tk.Menu(menu, name="apple", tearoff=False)
    add_command(apple,
        english="About Facility Studio",
        label=("About Facility Studio" if sys.platform == "darwin"
               else "關於 Facility Studio"),
        command=lambda: messagebox.showinfo(
            "Facility Studio",
            f"Facility Studio {BUILD}\n廠務工程計算、材料管路及設計報表。\n工程條件與軟體數值測試分別列示。",
            parent=root,
        ),
    )
    menu.add_cascade(label="Facility Studio", menu=apple)
    file_menu = tk.Menu(menu, tearoff=False)

    def close_window():
        focus = root.focus_get()
        win = focus.winfo_toplevel() if focus else root
        callback = win.protocol("WM_DELETE_WINDOW")
        if callback:
            root.tk.call(callback)
        else:
            win.destroy()

    add_command(file_menu, label="關閉視窗", english="Close window", command=close_window)
    menu.add_cascade(label="檔案", menu=file_menu)
    edit = tk.Menu(menu, tearoff=False)

    def edit_event(event):
        widget = root.focus_get()
        if widget:
            widget.event_generate(event)

    for label, english, event in [
        ("復原", "Undo", "<<Undo>>"),
        ("重做", "Redo", "<<Redo>>"),
        ("剪下", "Cut", "<<Cut>>"),
        ("複製", "Copy", "<<Copy>>"),
        ("貼上", "Paste", "<<Paste>>"),
        ("全選", "Select all", "<<SelectAll>>"),
    ]:
        add_command(edit, label=label, english=english, command=lambda e=event: edit_event(e))
    menu.add_cascade(label="編輯", menu=edit)
    window = tk.Menu(menu, tearoff=False)
    add_command(window, label="縮到最小", english="Minimize", command=root.iconify)
    menu.add_cascade(label="視窗", menu=window)
    help_menu = tk.Menu(menu, tearoff=False)
    add_command(help_menu,
        english="Verification purpose and scope",
        label="驗證用途與範圍",
        command=lambda: messagebox.showinfo(
            "驗證用途與範圍",
            "一般設計請用左側簡易工具：PV、液體／純水、單位換算均直接在原頁操作。\nAHU 模型差異核對分析相同條件的模型偏差，不取代負荷設計與工程條件檢核。\n冷熱水頁可估保溫，液體頁可選材料與介質；數據不足或超出模型範圍會明確提示。",
            parent=root,
        ),
    )
    menu.add_cascade(label="說明", menu=help_menu)
    menu._sandbox_top_labels = {
        str(file_menu): ("檔案", "File"),
        str(edit): ("編輯", "Edit"),
        str(window): ("視窗", "Window"),
        str(help_menu): ("說明", "Help"),
    }
    root.configure(menu=menu)
    root._sandbox_menu = menu
    from . import i18n
    if not hasattr(root, "_sandbox_menu_language"):
        root._sandbox_menu_language = _NativeMenuLanguage(root)
        i18n.subscribe(root._sandbox_menu_language)
    root._sandbox_menu_language.refresh_language()

    if not getattr(root, "_sandbox_menu_cleanup", False):
        def cleanup(event):
            pending = getattr(root, "_sandbox_menu_after", None)
            if event.widget is root and pending is not None:
                root.after_cancel(pending)
                root._sandbox_menu_after = None

        root.bind("<Destroy>", cleanup, add="+")
        root._sandbox_menu_cleanup = True
