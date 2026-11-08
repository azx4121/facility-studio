"""Scope/mode selector bounds; real-font check requires an available Tk display.
These tests do not substitute for native final-EXE screenshot approval.
"""
import ast
from pathlib import Path
import tkinter as tk
from tkinter import font, ttk

import pytest

ROOT = Path(__file__).resolve().parents[1]


def selector_specs():
    tree = ast.parse((ROOT / 'windows/facility_studio/desktop.py').read_text(encoding='utf-8'))
    result = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'Combobox':
            continue
        kw = {k.arg: k.value for k in node.keywords}
        var = kw.get('textvariable')
        if isinstance(var, ast.Attribute) and var.attr in ('task_scope', 'view_mode'):
            result[var.attr] = {k: ast.literal_eval(kw[k]) for k in ('values', 'width', 'state')}
    return result


def test_bounded_selector_reservations_cover_both_languages():
    specs = selector_specs()
    assert specs['task_scope']['width'] == 26
    assert specs['view_mode']['width'] == 16
    assert specs['task_scope']['values'] == ('空調與熱負荷', '全部工程分頁')
    assert specs['view_mode']['values'] == ['基本模式', '進階模式']
    assert all(s['state'] == 'readonly' for s in specs.values())
    # Keep canonical engineering enum values and avoid any global window resize.
    assert specs['task_scope']['width'] < 30


def test_selector_labels_fit_actual_theme_font():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip('Native Tk display unavailable: ' + str(exc))
    try:
        import sys
        sys.path.insert(0, str(ROOT / 'windows'))
        from facility_studio import i18n
        for spec in selector_specs().values():
            box = ttk.Combobox(root, width=spec['width'], state='readonly')
            box.pack()
            root.update_idletasks()
            measured = font.Font(root=root, font=box.cget('font'))
            # Tk width expresses the editable text region in average zero widths;
            # reserve one extra character rather than counting arrow area as text.
            available = (spec['width'] - 1) * measured.measure('0')
            for lang in ('en', 'zh-Hant'):
                for value in spec['values']:
                    assert measured.measure(i18n.translate(value, lang)) <= available
    finally:
        root.destroy()
