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
        label="關於工程驗證沙盒",
        command=lambda: messagebox.showinfo(
            "工程驗證沙盒",
            f"Facility Studio {BUILD}\n合成案例、工程數值對照與單相水管分析。\n工程條件與軟體數值測試分別列示。",
            parent=root,
        ),
    )
    menu.add_cascade(label="工程驗證沙盒", menu=apple)
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
            "主畫面的「設計檢核中心」可直接使用 AHU 核對、水管物性與壓損、九類單位換算。\n冷熱水快算可帶入目前條件；AHU 視窗按「獨立核對與報告」讀取目前輸入。\n\n報告分別列出工程品質、內部數值門檻與採用條件。內部門檻不等於 FEED 設計驗收。",
            parent=root,
        ),
    )
    menu.add_cascade(label="說明", menu=help_menu)
    root.configure(menu=menu)
    root._sandbox_menu = menu
    from .sandbox_native_menu import localize_application_menu

    root.after_idle(localize_application_menu)
