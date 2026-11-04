"""Choice safety and wheel routing. Real Tk cases require a display.

Run each source tree in a fresh process with FACILITY_TEST_PLATFORM=windows|macos.
Set FACILITY_REQUIRE_DISPLAY=1 for acceptance: missing displays then fail, not skip.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       os.environ.get("FACILITY_TEST_PLATFORM", "windows")))
from facility_studio import platform_support
from facility_studio.ui_common import install_combobox_wheel_guard


class Widget:
    def __init__(self, kind="TCombobox", children=()):
        self.kind = kind
        self.tags = (".widget", kind, ".", "all")
        self.children = children

    def winfo_class(self):
        return self.kind

    def bindtags(self, tags=None):
        if tags is not None:
            self.tags = tags
        return self.tags

    def winfo_children(self):
        return self.children


class Window(Widget):
    def __init__(self, children=()):
        super().__init__("Tk", children)
        self.bindings = {"TCombobox": {
            "<Key-Down>": "ttk::combobox::Post %W",
            "<Button-1>": 'ttk::combobox::Press "" %W %x %y',
            "<<Paste>>": "ttk::entry::Paste %W",
            "<Key-Left>": "native platform-specific cursor binding",
            **{sequence: "ttk::combobox::Scroll %W ..." for sequence in (
                "<MouseWheel>", "<Shift-MouseWheel>", "<Option-MouseWheel>",
                "<TouchpadScroll>", "<Button-4>", "<Button-5>",
                "<Shift-Button-4>", "<Button-6>", "<Button-7>",
            )},
        }}
        self.listeners = {}

    def _root(self):
        return self

    def bind_class(self, tag, sequence=None, command=None):
        bindings = self.bindings.setdefault(tag, {})
        if sequence is None:
            return tuple(bindings)
        if command is not None:
            bindings[sequence] = command
        return bindings.get(sequence, "")

    def bind_all(self, sequence, callback, add=None):
        assert add == "+"
        self.listeners.setdefault(sequence, []).append(callback)


def test_install_preserves_native_bindings_and_removes_only_wheel_from_app_tag():
    combo, entry = Widget(), Widget("TEntry")
    root = Window((combo, entry))
    original = root.bindings["TCombobox"].copy()
    install_combobox_wheel_guard(root)
    assert root.bindings["TCombobox"] == original
    safe = root.bindings["FacilityCombobox"].copy()
    touchpad = safe.pop("<TouchpadScroll>")
    assert "event generate %W <MouseWheel>" in touchpad
    assert "ttk::combobox::Scroll" not in touchpad
    assert safe == {sequence: original[sequence] for sequence in
                    ("<Key-Down>", "<Button-1>", "<<Paste>>", "<Key-Left>")}
    assert combo.tags == (".widget", "FacilityCombobox", ".", "all")
    assert entry.tags == (".widget", "TEntry", ".", "all")


def test_install_is_idempotent_and_covers_dynamic_native_controls():
    root = Window()
    install_combobox_wheel_guard(root)
    install_combobox_wheel_guard(root)
    assert all(len(listeners) == 1 for listeners in root.listeners.values())
    for event in ("<Map>", "<FocusIn>"):
        combo = Widget()
        combo.tags = (".later", "FacilityScroll_local", "TCombobox", ".dialog", "all")
        callback = root.listeners[event][0]
        callback(SimpleNamespace(widget=combo))
        assert combo.tags == (".later", "FacilityScroll_local", "FacilityCombobox", ".dialog", "all")
        callback(SimpleNamespace(widget=".later.popdown.f.l"))  # Tcl popup has no Python wrapper.


WHEELS = [("<MouseWheel>", 120), ("<MouseWheel>", -120),
          ("<MouseWheel>", 240), ("<MouseWheel>", -240),
          ("<MouseWheel>", 1), ("<MouseWheel>", -1),
          ("<MouseWheel>", 2), ("<MouseWheel>", -2),
          ("<MouseWheel>", 0), ("<Button-4>", 0), ("<Button-5>", 0)]


class Canvas:
    def __init__(self):
        self.steps = []

    def __str__(self):
        return ".input"

    def yview_scroll(self, step, mode):
        self.steps.append((step, mode))

    def yview(self):
        return (.3, .7)


@pytest.mark.parametrize("platform", ["win32", "darwin"])
@pytest.mark.parametrize("sequence,delta", WHEELS)
def test_workbench_and_ahu_route_combobox_wheel_once(platform, sequence, delta, monkeypatch):
    from facility_studio.ahu_view import AHUView
    from facility_studio.localized_tk import Combobox
    from facility_studio.main_view import MainView
    from facility_studio.simple_desktop import SimpleToolsApp

    monkeypatch.setattr(platform_support, "sys", SimpleNamespace(platform=platform))
    root = object()
    # A real Combobox subclass identity exercises the previous isinstance guard,
    # without needing a display for these routing-unit checks.
    class Choice(Combobox):
        def __init__(self):
            self._w = ".input.choice"

        def winfo_toplevel(self):
            return root
    choice = Choice()
    event = SimpleNamespace(widget=choice, delta=delta,
                            num=int(sequence[-2]) if "Button" in sequence else 0)
    step = platform_support.scroll_units(event, platform)
    expected = [(step, "units")] if step else []
    main_canvas, ahu_canvas = Canvas(), Canvas()
    main = SimpleNamespace(root=root, current=1, pages={1: SimpleNamespace(canvas=main_canvas)})
    assert MainView.wheel(main, event) == ("break" if step else None)
    assert main_canvas.steps == expected
    ahu = SimpleNamespace(input_canvas=ahu_canvas, nb=SimpleNamespace(
        select=lambda: "design", index=lambda selected: 0, nametowidget=lambda selected: object()))
    assert AHUView.wheel(ahu, event) == ("break" if step else None)
    assert ahu_canvas.steps == expected
    simple_canvas = Canvas()
    page = SimpleNamespace(canvas=simple_canvas)
    choice.master = page
    simple = SimpleNamespace(root=root, active_page=lambda: page)
    assert SimpleToolsApp.wheel(simple, event) == ("break" if step else None)
    assert simple_canvas.steps == expected


def test_scrollable_frame_attaches_combobox_but_leaves_text_and_trees_native():
    from facility_studio.industrial_theme import ScrollableFrame
    frame = SimpleNamespace(_wheel_tag="FacilityScroll_test")
    for kind in ("TCombobox", "TEntry", "Text", "Treeview"):
        widget = Widget(kind)
        ScrollableFrame._attach_widget(frame, widget)
        assert (frame._wheel_tag in widget.tags) == (kind not in ("Text", "Treeview"))


@pytest.fixture
def real_root(tmp_path, monkeypatch):
    import tkinter as tk
    monkeypatch.setenv("FACILITY_STUDIO_PREFERENCES", str(tmp_path / "preferences.json"))
    try:
        root = tk.Tk()
    except tk.TclError as error:
        if os.environ.get("FACILITY_REQUIRE_DISPLAY") == "1":
            raise
        pytest.skip("Real Tk display unavailable: " + str(error))
    root.geometry("480x320+0+0")
    errors = []
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
    install_combobox_wheel_guard(root)
    try:
        yield root
        assert not errors
    finally:
        for token in root.tk.splitlist(root.tk.call("after", "info")):
            root.tk.call("after", "cancel", token)
        root.destroy()


@pytest.mark.parametrize("focused", [False, True])
@pytest.mark.parametrize("state", ["readonly", "normal", "disabled"])
@pytest.mark.parametrize("localized", [False, True])
def test_real_combo_wheel_does_not_select_or_emit_change(real_root, focused, state, localized):
    import tkinter as tk
    from tkinter import ttk

    from facility_studio.localized_tk import Combobox
    root = real_root
    entry = ttk.Entry(root)
    entry.pack()
    canvas = tk.Canvas(root, width=400, height=200, scrollregion=(0, 0, 400, 2000))
    canvas.pack()
    body = ttk.Frame(canvas)
    canvas.create_window(0, 0, window=body, anchor="nw")
    source = tk.StringVar(root, "second")
    widget = (Combobox if localized else ttk.Combobox)(
        body, textvariable=source, values=("first", "second", "third"), state=state)
    widget.pack()
    changes, selections, scrolls = [], [], []
    source.trace_add("write", lambda *args: changes.append(source.get()))
    widget.bind("<<ComboboxSelected>>", lambda event: selections.append(source.get()))
    def scroll(event):
        step = platform_support.scroll_units(event)
        if step:
            scrolls.append(step)
            canvas.yview_scroll(step, "units")
            return "break"
    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        root.bind(sequence, scroll)
    root.update()
    (widget if focused else entry).focus_force()
    root.update()
    assert "FacilityCombobox" in widget.bindtags()
    for sequence, delta in WHEELS:
        # Button-4/5 are X11 input. Windows/Aqua wheel input uses MouseWheel.
        if "Button" in sequence and root.tk.call("tk", "windowingsystem") != "x11":
            continue
        canvas.yview_moveto(.5)
        before = canvas.yview()[0]
        before_events = len(scrolls)
        widget.event_generate(sequence, **({"delta": delta} if "MouseWheel" in sequence else {}))
        root.update()
        after = canvas.yview()[0]
        direction = -1 if sequence == "<Button-4>" or delta > 0 else 1
        if delta or "Button" in sequence:
            assert (after - before) * direction > 0
            assert len(scrolls) == before_events + 1
        else:
            assert after == before and len(scrolls) == before_events
        assert source.get() == "second"
        assert not changes and not selections


def test_real_native_binding_copy_preserves_keyboard_click_and_popup(real_root):
    from tkinter import ttk
    root = real_root
    widget = ttk.Combobox(root, values=("first", "second", "third"), state="readonly")
    widget.pack()
    root.update()
    for sequence in root.bind_class("TCombobox"):
        if "TouchpadScroll" in sequence:
            assert "event generate %W <MouseWheel>" in root.bind_class("FacilityCombobox", sequence)
        elif any(token in sequence for token in ("MouseWheel", "Button-4>",
                                                "Button-5>", "Button-6>", "Button-7>")):
            assert not root.bind_class("FacilityCombobox", sequence)
        else:
            assert root.bind_class("FacilityCombobox", sequence) == root.bind_class("TCombobox", sequence)
    # The open popup remains native: intentionally browsing its list must still
    # work. Aqua Tk versions may implement this as a native menu instead.
    if root.tk.call("tk", "windowingsystem") == "aqua":
        return  # Native menu click / key acceptance is also in the manual checklist.
    widget.current(0)
    widget.focus_force()
    root.update()
    widget.event_generate("<KeyPress-Down>")
    root.update()
    popdown = str(root.tk.call("ttk::combobox::PopdownWindow", str(widget)))
    assert root.tk.call("winfo", "ismapped", popdown)
    listbox = popdown + ".f.l"
    root.tk.call("event", "generate", listbox, "<KeyPress-Down>")
    root.tk.call("event", "generate", listbox, "<KeyPress-Return>")
    root.update()
    assert widget.current() == 1
    widget.event_generate("<ButtonPress-1>", x=widget.winfo_width()-5, y=widget.winfo_height()//2)
    widget.event_generate("<ButtonRelease-1>", x=widget.winfo_width()-5, y=widget.winfo_height()//2)
    root.update()
    assert root.tk.call("winfo", "ismapped", popdown)
    box = root.tk.call(listbox, "bbox", 2)
    x, y = int(box[0])+2, int(box[1])+2
    root.tk.call("event", "generate", listbox, "<ButtonPress-1>", "-x", x, "-y", y)
    root.tk.call("event", "generate", listbox, "<ButtonRelease-1>", "-x", x, "-y", y)
    root.update()
    assert widget.current() == 2


@pytest.mark.parametrize("dx,dy", [(0, 1), (0, -1), (0, 120), (0, -120), (1, 0), (-1, 0), (12, -5), (0, 0)])
def test_tk9_touchpad_binding_relays_vertical_axis_only(dx, dy):
    import tkinter as tk
    root = Window()
    install_combobox_wheel_guard(root)
    script = root.bindings["FacilityCombobox"]["<TouchpadScroll>"]
    # The Tcl interpreter needs no display. Use Tk 9's actual packing contract
    # to test the relay body, without pretending this is a native input event.
    interp = tk.Tcl()
    interp.eval("""
        namespace eval tk {}
        proc tk::PreciseScrollDeltas {dxdy} {
            set dx [expr {$dxdy >> 16}]
            set low [expr {$dxdy & 0xffff}]
            return [list $dx [expr {$low < 0x8000 ? $low : $low - 0x10000}]]
        }
        set generated {}
        proc event {args} { lappend ::generated $args }
    """)
    delta = (dx << 16) | (dy & 0xffff)
    script = script.replace("%D", str(delta)).replace("%W", ".combo").replace("%x", "10").replace("%y", "20")
    assert int(interp.call("catch", script)) == 3  # Tcl break: original event stops here.
    generated = interp.splitlist(interp.eval("set generated"))
    assert len(generated) == (1 if dy else 0)
    if dy:
        assert interp.splitlist(generated[0]) == (
            "generate", ".combo", "<MouseWheel>", "-delta", str(dy), "-x", "10", "-y", "20")


def test_real_scrollable_frame_routes_late_combo_without_global_fallback(real_root):
    from tkinter import ttk

    from facility_studio.industrial_theme import ScrollableFrame
    root = real_root
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    root.update()
    # Create the native choice after the frame mapped, like a rebuilt form.
    widget = ttk.Combobox(frame.body, values=("first", "second", "third"), state="readonly")
    widget.pack()
    widget.current(1)
    ttk.Frame(frame.body, height=1800).pack()
    selections, fallback = [], []
    widget.bind("<<ComboboxSelected>>", lambda event: selections.append(widget.get()))
    root.bind("<MouseWheel>", lambda event: fallback.append(event))
    install_combobox_wheel_guard(root)
    root.update()
    tags = widget.bindtags()
    assert tags.index(frame._wheel_tag) < tags.index("FacilityCombobox")
    frame.canvas.yview_moveto(.5)
    before = frame.canvas.yview()[0]
    widget.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert frame.canvas.yview()[0] > before
    assert widget.current() == 1 and not selections and not fallback
    frame.destroy()
    root.update()


def test_real_simple_tool_keeps_values_and_scrolls_input_page(real_root):
    from tkinter import ttk

    from facility_studio.simple_desktop import SimpleToolsApp
    root = real_root
    app = SimpleToolsApp(root)
    root.update()
    page = app.active_page()
    ttk.Frame(page.body, height=1800).grid(row=999, column=0)
    root.update()
    widget = next(w for w in page.widgets.values() if w.winfo_class() == "TCombobox"
                  and str(w.cget("state")) == "readonly")
    values = page.data()
    page.canvas.yview_moveto(.5)
    before = page.canvas.yview()[0]
    widget.focus_force()
    widget.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert page.canvas.yview()[0] > before
    assert page.data() == values


def test_real_fusion_settings_routes_to_current_page_and_cancel_keeps_inputs(real_root):
    from facility_studio.fusion_settings import open_settings
    from facility_studio.schema import DEFAULTS
    root = real_root
    inputs = dict(DEFAULTS)
    owner = SimpleNamespace(root=root, project_id="wheel-test", snapshot=lambda: {"inputs": inputs})
    win = open_settings(owner)
    win.geometry("840x500")
    notebook = win.fusion_notebook
    notebook.select(1)
    root.update()
    page = notebook.nametowidget(notebook.select())
    widget = next(w for w in page.body.winfo_children() if w.winfo_class() == "TCombobox")
    values = {key: value.get() for key, value in win.fusion_values.items()}
    page.canvas.yview_moveto(.5)
    before = page.canvas.yview()[0]
    widget.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert page.canvas.yview()[0] > before
    assert {key: value.get() for key, value in win.fusion_values.items()} == values
    win.destroy()
    root.update()
    assert inputs == DEFAULTS
