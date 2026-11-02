"""Presentation-only sandbox identity and native menus."""

import os


def install_menus(root):
    if not os.environ.get("FACILITY_STUDIO_SANDBOX"):
        return
    import tkinter as tk
    from tkinter import messagebox
    from .engineering_verification import BUILD

    root.title("Facility Studio 整合測試版 " + BUILD)
    menu = tk.Menu(root)
    apple = tk.Menu(menu, name="apple", tearoff=False)
    apple.add_command(
        label="關於 Facility Studio",
        command=lambda: messagebox.showinfo(
            "Facility Studio",
            f"Facility Studio {BUILD}\n合成案例、工程數值對照與單相水管分析。\n工程條件與軟體數值測試分別列示。",
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

    file_menu.add_command(label="關閉視窗", command=close_window)
    menu.add_cascade(label="檔案", menu=file_menu)
    edit = tk.Menu(menu, tearoff=False)

    def edit_event(event):
        widget = root.focus_get()
        if widget:
            widget.event_generate(event)

    for label, event in [
        ("復原", "<<Undo>>"),
        ("重做", "<<Redo>>"),
        ("剪下", "<<Cut>>"),
        ("複製", "<<Copy>>"),
        ("貼上", "<<Paste>>"),
        ("全選", "<<SelectAll>>"),
    ]:
        edit.add_command(label=label, command=lambda e=event: edit_event(e))
    menu.add_cascade(label="編輯", menu=edit)
    window = tk.Menu(menu, tearoff=False)
    window.add_command(label="縮到最小", command=root.iconify)
    menu.add_cascade(label="視窗", menu=window)
    help_menu = tk.Menu(menu, tearoff=False)
    help_menu.add_command(
        label="驗證用途與範圍",
        command=lambda: messagebox.showinfo(
            "驗證用途與範圍",
            "一般設計請用左側簡易工具：PV、液體／純水、單位換算均直接在原頁操作。\nAHU 模型差異核對用於原條件的 PsychroLib／CoolProp 偏差分析，不是另一份負荷設計，也不代表工程認證。\n冷熱水頁可估保溫，液體頁可選材料與介質；數據不足或超出模型範圍會明確提示。",
            parent=root,
        ),
    )
    menu.add_cascade(label="說明", menu=help_menu)
    root.configure(menu=menu)
    root._sandbox_menu = menu
    from .sandbox_native_menu import localize_application_menu

    pending = getattr(root, "_sandbox_menu_after", None)
    if pending is not None:
        root.after_cancel(pending)

    def localize():
        root._sandbox_menu_after = None
        localize_application_menu()

    root._sandbox_menu_after = root.after_idle(localize)

    if not getattr(root, "_sandbox_menu_cleanup", False):
        def cleanup(event):
            pending = getattr(root, "_sandbox_menu_after", None)
            if event.widget is root and pending is not None:
                root.after_cancel(pending)
                root._sandbox_menu_after = None

        root.bind("<Destroy>", cleanup, add="+")
        root._sandbox_menu_cleanup = True
