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
