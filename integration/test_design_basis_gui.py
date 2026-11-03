"""Actual Tk widgets and actions; synthetic records only, no desktop unlocking."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "macos"))


def test_native_review_window_roundtrip_and_stale_report(tmp_path):
    from facility_studio.localized_tk import tk
    from facility_studio.design_basis_ui import DesignReviewWindow
    from facility_studio import design_basis as m
    root = tk.Tk()
    root.withdraw()
    ui = DesignReviewWindow(root)
    try:
        ui.install(m.new_dossier(), tmp_path)
        for key, var in ui.variables.items():
            var.set("合成案例－" + key)
        ui.standards.insert("1.0", "合成規範｜R1｜3.1｜單一合成案例｜SYNTHETIC-001")
        ui.win.update()
        assert not ui.refresh()["can_submit"]
        source = tmp_path / "合成計算書.txt"
        source.write_text("僅供UI測試", encoding="utf-8")
        for key in m.DELIVERABLES:
            m.attach(ui.data, tmp_path, key, source)
        ui.reviewer.set("另一位合成覆核者")
        for key in m.DELIVERABLES:
            ui.tree.selection_set(key)
            ui.win.update()
            ui.comment.set("合成驗收依據與文件已核對")
            ui.review("accepted")
        assert ui.refresh()["can_submit"]
        saved = ui.save()
        assert m.load_revision(saved)["reviews"] == ui.data["reviews"]
        ui.variables["conditions"].set("變更室內相對濕度")
        ui.win.update()
        assert "變更" in ui.status.get()
        report = ui.export()
        assert "舊覆核失效" in report.read_text(encoding="utf-8")
        ui.install(m.load_revision(saved), tmp_path)
        assert ui.refresh()["can_submit"]
        ui.win.update()
        assert ui.win.winfo_width() >= 820
        ui.win.geometry("820x650")
        ui.win.update()
        # Check actual geometry at the minimum supported window size, without
        # needing access to the locked desktop's screen capture.
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        buttons = [w for w in widgets(ui.win) if w.winfo_class() == "TButton"]
        for button in buttons:
            if button.winfo_ismapped():
                assert button.winfo_width() >= button.winfo_reqwidth()
                assert button.winfo_rootx() + button.winfo_width() <= ui.win.winfo_rootx() + ui.win.winfo_width()
    finally:
        root.destroy()


def test_entry_button_opens_document_window_without_workbench():
    from facility_studio.localized_tk import tk
    from facility_studio.simple_desktop import SimpleToolsApp
    root = tk.Tk()
    app = SimpleToolsApp(root)
    try:
        app.design_review_button.invoke()
        root.update()
        assert any(isinstance(w, tk.Toplevel) and "交付審查" in w.title() for w in root.winfo_children())
        assert app.workbench is None
    finally:
        root.destroy()
