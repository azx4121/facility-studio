"""A destroyed Tk interpreter must not break later windows' language changes."""
import os
from pathlib import Path
import sys
from tkinter import TclError
import weakref

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / os.environ.get("FACILITY_TEST_PLATFORM", "windows")))
from facility_studio import i18n
from facility_studio.localized_tk import WindowTitle


@pytest.fixture
def listeners(monkeypatch):
    subscribers = weakref.WeakSet()
    monkeypatch.setattr(i18n, "_listeners", subscribers)
    monkeypatch.setattr(i18n, "_language", "zh-Hant")
    monkeypatch.setattr(i18n, "_initialized", True)
    return subscribers


class Listener:
    refreshed = False

    def refresh_language(self):
        self.refreshed = True


@pytest.mark.parametrize("raises", [False, True])
def test_dead_widgets_are_pruned_and_live_listener_is_updated(listeners, raises):
    class Dead(Listener):
        def winfo_exists(self):
            if raises:
                raise TclError('cannot invoke "winfo": application has been destroyed')
            return False
    dead, live = Dead(), Listener()
    i18n.subscribe(dead)
    i18n.subscribe(live)
    i18n.set_language("en", persist=False)
    assert not dead.refreshed and dead not in listeners
    assert live.refreshed and live in listeners


def test_destroyed_window_title_probe_is_safe(listeners):
    class Window:
        def title(self, text=None):
            return "Capacity" if text is None else text

        def winfo_exists(self):
            raise TclError('cannot invoke "winfo": application has been destroyed')
    window = Window()
    title = WindowTitle(window)
    assert not title.winfo_exists()
    title.refresh_language()
    i18n.set_language("en", persist=False)
    assert title not in listeners


def test_real_refresh_failure_is_not_silenced(listeners):
    class Broken(Listener):
        def refresh_language(self):
            raise TclError("Invalid translation widget operation")
    broken = Broken()
    i18n.subscribe(broken)
    with pytest.raises(TclError, match="Invalid translation"):
        i18n.set_language("en", persist=False)


def test_native_destroyed_interpreter_does_not_block_new_window(listeners):
    from facility_studio.localized_tk import tk, attach_window
    try:
        first = tk.Tk()
    except TclError as error:
        if os.environ.get("FACILITY_REQUIRE_DISPLAY") == "1":
            raise
        pytest.skip("Native Tk display unavailable: " + str(error))
    first.withdraw()
    old = tk.Toplevel(first)
    attach_window(old)
    old.title("容量／擴建規劃")
    stale_title = old._language_title
    first.destroy()
    second = tk.Tk()
    try:
        second.withdraw()
        live = tk.Toplevel(second)
        attach_window(live)
        live.title("容量／擴建規劃")
        i18n.set_language("en", persist=False)
        second.update()
        assert live.title() == "Capacity / expansion planning"
        assert stale_title not in listeners
    finally:
        second.destroy()


@pytest.fixture(params=["desktop", "ahu", "quick_tools", "equipment"])
def controller(request):
    """Use production controller types without constructing unrelated form UI."""
    from facility_studio.desktop import DesktopApp
    from facility_studio.ahu_desktop import AHUWindow
    from facility_studio.tools_view import QuickToolsWindow
    from facility_studio.equipment_view import EquipmentWindow
    cls, window_attr = {
        "desktop": (DesktopApp, "root"),
        "ahu": (AHUWindow, "win"),
        "quick_tools": (QuickToolsWindow, "win"),
        "equipment": (EquipmentWindow, "win"),
    }[request.param]
    return cls.__new__(cls), window_attr


@pytest.mark.parametrize("destroyed_interpreter", [False, True])
def test_closed_controllers_are_pruned_without_waiting_for_gc(
        listeners, controller, destroyed_interpreter):
    owner, window_attr = controller
    class ClosedWindow:
        def winfo_exists(self):
            if destroyed_interpreter:
                raise TclError('cannot invoke "winfo": application has been destroyed')
            return False
    setattr(owner, window_attr, ClosedWindow())
    refreshed = []
    owner.refresh_language = lambda: refreshed.append(True)
    live = Listener()
    i18n.subscribe(owner)
    i18n.subscribe(live)
    i18n.set_language("en", persist=False)
    assert owner not in listeners and not refreshed
    assert live.refreshed


def test_live_controller_refresh_errors_still_surface(listeners, controller):
    owner, window_attr = controller
    class LiveWindow:
        def winfo_exists(self):
            return True
    setattr(owner, window_attr, LiveWindow())
    def broken_refresh():
        raise TclError("Invalid live controller translation operation")
    owner.refresh_language = broken_refresh
    i18n.subscribe(owner)
    with pytest.raises(TclError, match="Invalid live controller"):
        i18n.set_language("en", persist=False)
    assert owner in listeners


def test_native_destroyed_controller_does_not_block_new_window(listeners, controller):
    from facility_studio.localized_tk import tk, attach_window
    owner, window_attr = controller
    try:
        first = tk.Tk()
    except TclError as error:
        if os.environ.get("FACILITY_REQUIRE_DISPLAY") == "1":
            raise
        pytest.skip("Native Tk display unavailable: " + str(error))
    first.withdraw()
    window = first if window_attr == "root" else tk.Toplevel(first)
    setattr(owner, window_attr, window)
    # Keep the real controller strongly reachable after its entire interpreter
    # is destroyed, as delayed callbacks/reference cycles can do in production.
    owner.result = None
    i18n.subscribe(owner)
    first.destroy()
    second = tk.Tk()
    try:
        second.withdraw()
        live = tk.Toplevel(second)
        attach_window(live)
        live.title("容量／擴建規劃")
        i18n.set_language("en", persist=False)
        second.update()
        assert owner not in listeners
        assert live.title() == "Capacity / expansion planning"
    finally:
        second.destroy()


def test_uninitialized_controller_is_not_silently_treated_as_closed(listeners, controller):
    owner, window_attr = controller
    # All production constructors set the window before subscribing. If that
    # contract regresses, do not turn an initialization bug into a silent prune.
    i18n.subscribe(owner)
    with pytest.raises(AttributeError, match=window_attr):
        i18n.set_language("en", persist=False)
    assert owner in listeners


def test_live_controller_still_refreshes(listeners, controller):
    owner, window_attr = controller
    class LiveWindow:
        def winfo_exists(self):
            return True
    setattr(owner, window_attr, LiveWindow())
    refreshed = []
    owner.refresh_language = lambda: refreshed.append(True)
    i18n.subscribe(owner)
    i18n.set_language("en", persist=False)
    assert refreshed == [True] and owner in listeners
