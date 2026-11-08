"""Extra native 1024x768 coverage; original large-desktop tests remain unchanged.

Run under windows_display.py --width 1024 --height 768 --exact --client 980x600.
Set NATIVE_DIAGNOSTICS_SOURCE to the original or explicitly named derivative tree.
"""
import os
from pathlib import Path
import sys

import pytest

SOURCE = Path(os.environ["NATIVE_DIAGNOSTICS_SOURCE"]).resolve()
sys.path.insert(0, str(SOURCE / "integration"))
sys.path.insert(0, str(SOURCE / "windows"))

# Reuse the unmodified production-app fixture and strict hit testing helpers.
from test_main_header_layout import (app, assert_header_visible, click_center,
                                     pump, rect, resize_and_measure, review_buttons,
                                     walk)


def on_screen(root, widget):
    from windows_display import NativeDisplay
    x, y, right, bottom = rect(widget)
    left, top, edge, base = NativeDisplay().metrics()["work_area"]
    assert widget.winfo_ismapped() and widget.winfo_viewable(), str(widget)
    assert left <= x < right <= edge and top <= y < bottom <= base, (
        "Control extends beyond real Windows work area", str(widget), rect(widget),
        [left, top, edge, base])
    assert root.winfo_containing((x + right) // 2, (y + bottom) // 2) is widget


def small_desktop(main, record_property):
    assert sys.platform == "win32", "Native Windows required"
    root = main.root
    assert root.tk.call("tk", "windowingsystem") == "win32"
    assert (root.winfo_screenwidth(), root.winfo_screenheight()) == (1024, 768)
    resize_and_measure(root, 980, 600, record_property)
    assert_header_visible(main)
    for toolbar in main.action_toolbars:
        for child in toolbar.winfo_children():
            on_screen(root, child)


@pytest.mark.parametrize("language", ["zh-Hant", "en"])
def test_native_1024_header_hit_targets_and_real_page_wheel(app, language, record_property):
    from facility_studio import i18n
    main, calls = app
    i18n.set_language(language, persist=False)
    small_desktop(main, record_property)
    for button in review_buttons(main):
        click_center(main.root, button)
    assert calls == [("review", main.root), ("settings", main)]
    # Use an actual overflowing product form, not invented spacer content.
    main.view_mode.set("進階模式")
    main.update_visibility()
    main.show_page(1)
    pump(main.root)
    canvas = main.pages[1].canvas
    canvas.yview_moveto(0)
    pump(main.root)
    before = canvas.yview()
    assert before[1] < 1, ("Real form did not overflow at 1024x768", before)
    x, y, right, bottom = rect(canvas)
    target = main.root.winfo_containing(x + 10, y + min(25, (bottom - y) // 2))
    assert target is not None and target.winfo_toplevel() is main.root
    assert target.winfo_class() not in ("Text", "Treeview")
    # Physical hit target precedes Tk-delivered input; no direct wheel() call.
    target.event_generate("<MouseWheel>", delta=-120)
    pump(main.root)
    after = canvas.yview()
    assert after[0] > before[0], (before, after)
    record_property("small_screen_form_scroll", (before, after))
    assert_header_visible(main)
    for button in review_buttons(main):
        on_screen(main.root, button)


@pytest.mark.parametrize("app", ["real_actions"], indirect=True)
def test_native_1024_real_dialog_dismiss_buttons_reachable(app, record_property):
    main, calls = app
    small_desktop(main, record_property)
    snapshot = main.session_snapshot()
    for button, marker, dismiss in zip(review_buttons(main),
                                       ("verification", "fusion_notebook"), ("關閉", "取消")):
        root = main.root
        root.lift()
        pump(root)
        on_screen(root, button)
        before = set(root.winfo_children())
        click_center(root, button)
        opened = [w for w in root.winfo_children()
                  if w not in before and w.winfo_class() == "Toplevel"]
        assert len(opened) == 1
        dialog = opened[0]
        assert hasattr(dialog, marker)
        close = next(w for w in walk(dialog) if w.winfo_class() == "TButton" and
                     (getattr(w, "_source_text", None) or w.cget("text")) == dismiss)
        # Do not reposition/shrink the dialog to manufacture a successful hit.
        on_screen(root, close)
        click_center(root, close)
        assert not dialog.winfo_exists()
        assert set(root.winfo_children()) == before
        assert main.session_snapshot() == snapshot
    assert calls == []
