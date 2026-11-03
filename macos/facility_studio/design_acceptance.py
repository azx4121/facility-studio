"""Bundled acceptance for document review and pump suction, synthetic data only."""
from pathlib import Path
from tempfile import TemporaryDirectory


def run(root, app, check):
    from .design_basis_ui import DesignReviewWindow
    from . import design_basis as model
    from .simple_engines import calculate_tool
    from .simple_schema import defaults
    from .errors import ValidationError
    try:
        calculate_tool("liquid", dict(defaults("liquid"), check_npsh="invalid"))
    except ValidationError as error:
        check("Invalid suction switch is rejected with its field name", error.field_name == "check_npsh")
    else:
        raise AssertionError("Invalid suction switch was accepted")
    with TemporaryDirectory(prefix="facility-design-check-") as temporary:
        folder = Path(temporary)
        ui = DesignReviewWindow(root)
        try:
            ui.install(model.new_dossier(), folder)
            check("空白設計資料不會標為文件齊備", not ui.refresh()["can_submit"])
            for key, var in ui.variables.items():
                var.set("合成案例－" + key)
            ui.standards.insert("1.0", "合成規範｜R1｜3.1｜合成案例｜SYNTHETIC-001")
            ui.sync()
            source = folder / "合成證據.txt"
            source.write_text("Synthetic acceptance evidence, not an engineering approval.", encoding="utf-8")
            for key in model.DELIVERABLES:
                model.attach(ui.data, folder, key, source)
            record = ui.data["documents"]["basis"]["evidence"][0]
            existing = folder / record["path"]
            original_bytes = existing.read_bytes()
            original_uuid = model.uuid4
            class FixedId:
                hex = existing.stem
            try:
                model.uuid4 = FixedId
                try:
                    model.attach(ui.data, folder, "basis", source)
                except FileExistsError:
                    pass
                else:
                    raise AssertionError("Attachment collision was not rejected")
            finally:
                model.uuid4 = original_uuid
            check("Attachment collision preserves existing evidence", existing.is_file() and existing.read_bytes() == original_bytes)
            ui.reviewer.set("合成獨立覆核者")
            for key in model.DELIVERABLES:
                ui.tree.selection_set(key)
                root.update()
                ui.comment.set("僅限合成測試，文件依據已核對")
                ui.review("accepted")
            check("逐項覆核後可送工程審查但不宣稱認證", ui.refresh()["can_submit"] and "不驗證" in ui.status.get())
            saved = ui.save()
            check("設計資料可儲存並重新讀回", model.load_revision(saved) == ui.data)
            ui.variables["revision"].set("合成新版 R2")
            check("版次變更使既有覆核失效", not ui.refresh()["can_submit"])
            exported = ui.export()
            check("匯出會重算失效狀態並保存對應設計資料", "舊覆核失效" in exported.read_text(encoding="utf-8") and len(list(folder.glob("設計審查_*.json"))) == 2)
            ui.install(model.load_revision(saved), folder)
            evidence = folder / ui.data["documents"]["basis"]["evidence"][0]["path"]
            evidence.write_text("Modified synthetic evidence", encoding="utf-8")
            check("證據遭修改會阻擋齊備判定", not ui.refresh()["can_submit"])
        finally:
            ui.win.destroy()
    from . import design_basis_ui
    review = app.open_design_review()
    check("重複開啟設計審查沿用同一視窗", app.open_design_review() is review)
    review.variables["project"].set("合成未存草稿")
    root.update()
    asked = []
    original_ask = design_basis_ui.messagebox.askyesno
    try:
        design_basis_ui.messagebox.askyesno = lambda *a, **k: asked.append(a) or False
        app.close()
        check("主視窗關閉會詢問設計審查未存草稿，拒絕時保留", len(asked) == 1 and root.winfo_exists() and review.win.winfo_exists() and review.dirty)
    finally:
        design_basis_ui.messagebox.askyesno = original_ask
    review.dirty = False
    review.close()
    root.update()
    check("無未存變更時設計審查可直接關閉", not review.win.winfo_exists())
    app.show_tool("liquid")
    liquid = app.active_page()
    liquid.reset()
    for key, value in dict(check_npsh="1", suction_loss_kpa="10", suction_level_m="2",
                           npshr_m="3", pump_curve_reference="合成原廠曲線 100 LPM、1450 rpm",
                           npsh_margin_m="1", npsh_margin_reference="合成業主要求 R1").items():
        liquid.variables[key].set(value)
    liquid.calculate()
    root.update()
    check("液體頁完成本案泵浦吸入條件校核", liquid.result is not None and liquid.result["suction"]["criterion_met"])
    liquid.variables["flow"].set("120")
    liquid.calculate()
    check("變更流量使吸入損失與泵曲線依據失效", liquid.result is None and not liquid.variables["suction_loss_kpa"].get() and not liquid.variables["pump_curve_reference"].get())
    liquid.reset()
