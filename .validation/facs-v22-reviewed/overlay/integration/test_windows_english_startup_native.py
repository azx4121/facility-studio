"""Native source preflight, to run on BOTH frozen1920 and small1024 desktops.

Set FACILITY_NATIVE_DISPLAY_PROFILE=frozen1920 or small1024 in each CI job.
Use suite1600 on the existing 1600x1200 full-suite job as additional coverage.
The test verifies the actual display, does not emulate/change its resolution,
and never adjusts the application's geometry. This is not final-EXE approval.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import font

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Requires real Windows desktop')


from windows_native_menu_observer import observe_native_menus


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


@pytest.mark.parametrize('initial', ['en', 'zh-Hant'])
@pytest.mark.parametrize('view', ['simple', 'workbench'])
def test_actual_native_menu_and_rendered_selector_fit(tmp_path, monkeypatch, initial, view, record_property):
    monkeypatch.syspath_prepend(str(ROOT / 'windows'))
    from facility_studio import i18n
    from facility_studio.industrial_theme import enable_high_dpi
    from facility_studio.desktop import DesktopApp
    from facility_studio.simple_desktop import SimpleToolsApp
    for name, path in [('LOCALAPPDATA', 'appdata'), ('FACILITY_STUDIO_DATA', 'data'),
                       ('FACILITY_STUDIO_PREFERENCES', 'preferences.json')]:
        monkeypatch.setenv(name, str(tmp_path / path))
    monkeypatch.setenv('FACILITY_STUDIO_NATIVE_MENUS', '1')
    i18n.set_language(initial, persist=False)
    enable_high_dpi()
    root = tk.Tk()  # A missing Windows display is a failure, never a skip.
    errors = []
    root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
    def settle():
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert not errors
    try:
        profile = os.environ.get('FACILITY_NATIVE_DISPLAY_PROFILE')
        assert profile in ('frozen1920', 'small1024', 'suite1600'), 'Set an explicit native display profile; both release profiles remain required'
        screen_size = (root.winfo_screenwidth(), root.winfo_screenheight())
        assert screen_size == {'frozen1920': (1920, 1080), 'small1024': (1024, 768), 'suite1600': (1600, 1200)}[profile]
        app = (SimpleToolsApp if view == 'simple' else DesktopApp)(root)
        settle()
        readouts = []
        for lang in [initial, 'en', 'zh-Hant', 'en']:
            i18n.set_language(lang, persist=False)
            settle()
            top, children, menu_observation = observe_native_menus(root, lang)
            assert top == (['Facility Studio', 'File', 'Edit', 'Window', 'Help'] if lang == 'en'
                           else ['Facility Studio', '檔案', '編輯', '視窗', '說明'])
            assert children == ([['About Facility Studio'], ['Close window'],
                ['Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Select all'], ['Minimize'],
                ['Verification purpose and scope']] if lang == 'en' else
                [['關於 Facility Studio'], ['關閉視窗'], ['復原', '重做', '剪下', '複製', '貼上', '全選'],
                 ['縮到最小'], ['驗證用途與範圍']])
            row = {'profile': profile, 'screen_size': list(screen_size), 'language': lang, 'top': top, 'children': children, 'menu_observation': menu_observation, 'selectors': []}
            if view == 'workbench':
                for variable in (app.task_scope, app.view_mode):
                    matches = [w for w in descendants(root) if getattr(w, '_canonical', None) is variable]
                    assert len(matches) == 1
                    box = matches[0]
                    original = variable.get()
                    for choice in box.cget('values'):
                        variable.set(choice)
                        settle()
                        rendered = box._display.get()
                        assert rendered == i18n.translate(choice, lang)
                        # Inspect the actual theme's textarea, excluding border/padding/arrow.
                        y = box.winfo_height() // 2
                        xs = [x for x in range(box.winfo_width()) if box.identify(x, y) == 'textarea']
                        assert xs, 'Theme exposes no measurable textarea'
                        text_px = font.Font(root=root, font=box.cget('font')).measure(rendered)
                        assert text_px + 2 <= len(xs), (rendered, text_px, len(xs))
                        left = box.winfo_rootx() - root.winfo_rootx()
                        top = box.winfo_rooty() - root.winfo_rooty()
                        bounds = [left, top, left + box.winfo_width(), top + box.winfo_height()]
                        assert box.winfo_viewable() and 0 <= bounds[0] < bounds[2] <= root.winfo_width()
                        assert 0 <= bounds[1] < bounds[3] <= root.winfo_height()
                        row['selectors'].append({'canonical_choice': choice, 'visible': bool(box.winfo_viewable()), 'text': rendered, 'text_px': text_px, 'textarea_px': len(xs), 'widget_px': box.winfo_width(), 'client_bounds': bounds, 'root_client_size': [root.winfo_width(), root.winfo_height()]})
                    variable.set(original)
            readouts.append(row)
        record_property('native_language_fit', json.dumps(readouts, ensure_ascii=False))
    finally:
        root.destroy()
