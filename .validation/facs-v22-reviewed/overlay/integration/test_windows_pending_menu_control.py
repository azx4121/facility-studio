"""Diagnostic negative control, separate from unchanged warm native cases."""
from test_windows_startup_placement import Window, geometry, win32


def test_transitional_menu_handle_is_not_evidence_of_settled_frame(win32, monkeypatch):
    """Negative diagnostic control: R4 prediction retains a known assumption.

    This intentionally demonstrates a NOT-contained outcome, not a release pass.
    The R5 constructor ordering fix must eliminate this state in native traces.
    It does not change the helper based on an unverified frozen API hypothesis.
    """
    monkeypatch.setenv("FACILITY_STUDIO_NATIVE_MENUS", "1")
    win32.menu = 0x3456789AB
    win32.rect = (208, 208, 1664, 1077)  # 869 high, menu handle already nonzero.
    geometry._place_initial_windows_window(Window())
    assert win32.moves == [(win32.outer, None, 208, 171, 0, 0, 0x0015)]
    assert win32.adjustments == []  # GetMenu shortcut bypasses the projection.
    left, top, right, bottom = win32.rect
    settled = (left, top, right, bottom + 20)
    assert settled == (208, 171, 1664, 1060)
    assert settled[3] > win32.work[3]  # Same outer overflow as the failed EXE.
