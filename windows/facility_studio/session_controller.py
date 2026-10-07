"""Whole-project lifecycle and explicit cross-window ownership."""

import copy
import uuid
from pathlib import Path
from datetime import datetime, timezone
from .localized_tk import messagebox, filedialog, ttk
from .localized_tk import tk
from .schema import VERSION, default_project
from .utils import project_hash
from .engine import calculate
from .workspace_store import validate_workspace, read_workspace
from .project_store import save_project_file, recovery_save
from .design_workflow import ahu_requirement_updates, ahu_source_hash
from .contributions import empty_ledger, aggregate_ledger, updated_ledger, removed_ledger, SUM_KEYS


class SessionController:
    def session_snapshot(self):
        documents = copy.deepcopy(self.ahu_documents)
        for child in list(self.children):
            if (
                hasattr(child, "ahu_id")
                and child.owner_project_id == self.project_id
                and child.win.winfo_exists()
            ):
                documents[child.ahu_id] = child.document()
        return dict(
            kind="facility_workspace",
            workspace_version=2,
            app_version=VERSION,
            project_id=self.project_id,
            main=self.snapshot(),
            ahus=list(documents.values()),
            comparisons=copy.deepcopy(self.comparisons),
            receipts=copy.deepcopy(self.transfer_receipts),
            drafts=copy.deepcopy(self.field_drafts),
            demand_ledger=copy.deepcopy(getattr(self, "demand_ledger", empty_ledger())),
        )

    def session_dirty(self):
        return project_hash(self.session_snapshot()) != self.saved_workspace_hash

    def refresh_session_status(self):
        if hasattr(self, "document_status"):
            count = len(self.session_snapshot()["ahus"])
            saved = (
                "未儲存變更"
                if self.session_dirty()
                else "專案已儲存" if self.path else "尚未另存完整專案"
            )
            self.document_status.set(
                f"{self.variables['project_name'].get()}｜{saved}｜主案＋{count} 台空調箱＋A/B"
            )

    def confirm_session_discard(self):
        return not self.session_dirty() or messagebox.askyesno(
            "整案尚未儲存",
            "主案、空調箱或 A/B 有未儲存修改。確定捨棄並切換案件？",
            parent=self.root,
        )

    def close_project_windows(self):
        for child in list(self.children):
            if getattr(child, "project_bound", False):
                child.close(force=True)

    def create_workspace(self):
        if not self.confirm_session_discard():
            return
        self.close_project_windows()
        self.project_id = uuid.uuid4().hex
        self.ahu_documents = {}
        self.comparisons = {}
        self.transfer_receipts = []
        self.field_drafts = {}
        self.demand_ledger = empty_ledger()
        self.undo_project = None
        self.undo_aux = None
        self.path = None
        self.last_good_result = None
        self.apply_project(default_project())
        self.saved_hash = project_hash(self.snapshot())
        self.saved_workspace_hash = project_hash(self.session_snapshot())
        self.notify_children()
        self.refresh_session_status()

    def apply_workspace(self, document, path=None):
        d = validate_workspace(document)
        self.close_project_windows()
        self.project_id = d["project_id"]
        self.ahu_documents = {x["id"]: x for x in d["ahus"]}
        self.comparisons = d["comparisons"]
        self.transfer_receipts = d["receipts"]
        self.field_drafts = d["drafts"]
        self.demand_ledger = d["demand_ledger"]
        self.path = path
        self.last_good_result = None
        self.undo_project = None
        self.undo_aux = None
        self.restore_snapshot(d["main"])
        self.saved_hash = project_hash(self.snapshot())
        self.saved_workspace_hash = (
            project_hash(self.session_snapshot()) if path else ""
        )
        self.notify_children()
        self.refresh_receipts()
        self.refresh_session_status()

    def open_workspace(self):
        path = filedialog.askopenfilename(
            parent=self.root, filetypes=[("整案／舊主案 JSON", "*.json")]
        )
        if not path:
            return
        try:
            from .json_io import read_json_file
            probe = read_json_file(path)
            if isinstance(probe, dict) and probe.get("kind") == "ahu_stage":
                from .ahu_desktop import AHUWindow
                from .ahu_engine import nm_read_project
                inputs = nm_read_project(path)["inputs"]
                inputs["linked_main_hash"] = "尚未連動"
                AHUWindow(self.root, self, document=dict(id=uuid.uuid4().hex, inputs=inputs, source_project_id=""))
                return
            if isinstance(probe, dict) and ("effective_inputs" in probe or "groups" in probe and "rows" in probe):
                raise ValueError("這是計算稽核／设备分析結果，不能作為可編輯專案。請開啟「儲存整案」或「另存新檔」的檔案。")
            doc = read_workspace(path)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            messagebox.showerror("不能開啟專案", str(exc), parent=self.root)
            return
        if self.confirm_session_discard():
            self.apply_workspace(doc, path)

    def save_workspace_as(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json", initialfile="Facility_Project_Copy.json", filetypes=[("可編輯完整專案", "*.json")])
        if path:
            return self.save_workspace(path)
        return False

    def open_practice(self):
        from .tutorial_help import prepare_tutorial
        folder = prepare_tutorial()
        path = folder / "02_Practice_MAU_and_AHU.json"
        doc = read_workspace(path)
        if self.confirm_session_discard():
            doc["project_id"] = uuid.uuid4().hex
            for entry in doc["ahus"]:
                entry["source_project_id"] = doc["project_id"]
            self.apply_workspace(doc)
            self.variables["project_name"].set("練習新案（假設值，非現場設備）")

    def open_equipment(self):
        from .equipment_view import EquipmentWindow
        return EquipmentWindow(self.root, main_app=self)

    def duplicate_workspace(self):
        """Save a new identity first; cancellation never changes the current case."""
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json", initialfile="Facility_Project_New_Scheme.json", filetypes=[("可編輯完整專案", "*.json")])
        if not path:
            return False
        if self.path and Path(path).resolve() == Path(self.path).resolve():
            messagebox.showerror("需另存路徑", "新方案請使用不同檔名，避免覆蓋原案。", parent=self.root)
            return False
        doc = self.session_snapshot()
        old_id = doc["project_id"]
        doc["project_id"] = uuid.uuid4().hex
        doc["main"]["inputs"]["project_name"] += " - Copy"
        for child in doc["ahus"]:
            if child["source_project_id"] == old_id:
                child["source_project_id"] = doc["project_id"]
        for receipt in doc["receipts"]:
            receipt["source_project_id"] = doc["project_id"]
        try:
            doc = validate_workspace(doc)
            save_project_file(path, doc)
        except (OSError, ValueError) as exc:
            messagebox.showerror("新方案未保存", str(exc), parent=self.root)
            return False
        self.apply_workspace(doc, path)
        return True

    def save_workspace(self, path=None):
        path = (
            path
            or self.path
            or filedialog.asksaveasfilename(
                parent=self.root,
                defaultextension=".json",
                initialfile="Facility_Project.json",
                filetypes=[("完整專案（主案、空調箱、A/B）", "*.json")],
            )
        )
        if not path:
            return False
        try:
            doc = validate_workspace(self.session_snapshot())
            save_project_file(path, doc)
            self.path = path
            self.saved_hash = project_hash(self.snapshot())
            self.saved_workspace_hash = project_hash(self.session_snapshot())
            self.ahu_documents = {d["id"]: d for d in doc["ahus"]}
            for child in self.children:
                if hasattr(child, "ahu_id"):
                    child.saved_hash = project_hash(child.snapshot())
            self.refresh_session_status()
            return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("整案未儲存", str(exc), parent=self.root)
            return False

    def close_workspace(self):
        if self.session_dirty():
            answer = messagebox.askyesnocancel(
                "整案未儲存",
                "關閉前儲存主案、所有空調箱及 A/B？\n無效輸入也可作為草稿保存。",
                parent=self.root,
            )
            if answer is None or (answer and not self.save_workspace()):
                return
        for child in list(self.children):
            child.close(force=True)
        for job in [self.after_id, getattr(self, "recovery_job", None)]:
            if job:
                self.root.after_cancel(job)
        self.root.destroy()

    def autosave_workspace(self):
        try:
            if self.session_dirty():
                recovery_save(self.session_snapshot(), self.recovery_token)
        except (OSError, ValueError) as exc:
            if hasattr(self, "document_status"):
                self.document_status.set("整案復原快照未保存：" + str(exc))
        self.recovery_job = self.root.after(30000, self.autosave)

    def notify_children(self):
        for child in list(self.children):
            if child.win.winfo_exists():
                if hasattr(child, "on_main_changed"):
                    child.on_main_changed()
                if hasattr(child, "refresh_link_status"):
                    child.refresh_link_status()
        self.refresh_receipts()
        self.refresh_session_status()

    def boundary_hash(self):
        key = project_hash(self.snapshot())
        if getattr(self, "_boundary_cache", (None,))[0] != key:
            try:
                result = calculate(self.snapshot(), isolate_utilities=True)
                value = ahu_requirement_updates(result)["linked_main_hash"]
            except (ValueError, KeyError, TypeError):
                value = None
            self._boundary_cache = key, value
        return self._boundary_cache[1]

    def refresh_receipts(self):
        documents = {d["id"]: d for d in self.session_snapshot()["ahus"]}
        notices = []
        for receipt in self.transfer_receipts:
            active = {
                k: v
                for k, v in receipt["values"].items()
                if self.variables[k].get() == v
                and self.provenance[k]["source"] == "來源快照"
            }
            if not active:
                receipt["status"] = "已由手動或其他來源取代"
                continue
            doc = documents.get(receipt["source_id"])
            if not doc:
                state = "來源未開啟，只保留快照"
            elif ahu_source_hash(doc["inputs"]) != receipt["source_hash"]:
                state = "來源已修改，快照過期"
            else:
                state = "與已保存來源條件一致"
            receipt["status"] = state
            if "過期" in state:
                notices.append(receipt["source_name"] + "：" + state)
        if hasattr(self, "receipt_status"):
            self.receipt_status.set(
                "；".join(notices) or "資料交換採來源快照；重新帶入前不會自動覆寫。"
            )
        result = getattr(self, "result", None)
        if result is not None:
            self.decorate_receipts(result)
            from .reports import report
            from .ui_common import quality_text, quality_style

            self.set_report(report(result))
            self.quality_label.config(
                text=quality_text(result["quality"]),
                style=quality_style(result["quality"]),
            )
            self.status.config(
                text=result["quality"]["status"] + "｜結果與來源狀態已同步",
                style=quality_style(result["quality"]),
            )
        return notices

    def decorate_receipts(self, result):
        from .quality import assessment, finding

        if "base_quality" not in result:
            result["base_quality"] = copy.deepcopy(result["quality"])
        items = copy.deepcopy(result["base_quality"]["items"])
        result["source_receipts"] = copy.deepcopy(self.transfer_receipts)
        ledger = getattr(self, "demand_ledger", empty_ledger())
        try:
            summary = aggregate_ledger(ledger, result["effective_inputs"])
        except (ValueError, TypeError, KeyError) as exc:
            summary = dict(updates={}, water=[], sources=[], notes=[], pending=["彙整未套用：" + str(exc)])
        result["demand_summary"] = summary
        for detail in summary["pending"]:
            finding(items, "需求彙整待確認", "待資料", detail, None)
        documents = {d["id"]: d for d in self.session_snapshot()["ahus"]}
        for source in ledger["entries"].values():
            if source["kind"] == "AHU":
                doc = documents.get(source["id"])
                if doc is None or ahu_source_hash(doc["inputs"]) != source["source_hash"]:
                    finding(items, "來源快照：" + source["name"], "待資料", "來源未保存或已修改；需求仍採上次帶入值，請重新檢核。", None)
        if any(self.variables[k].get() != v for k, v in ledger["last_updates"].items()):
            finding(items, "需求彙整目的值已修改", "待資料", "來源明細保留，但主案已有手動修改；請重新預覽帶入或移除來源，彙整表不能當成目前主案採用值。", None)
        for rec in self.transfer_receipts:
            if "過期" in rec["status"] or "來源未" in rec["status"]:
                finding(
                    items,
                    "來源快照：" + rec["source_name"],
                    "待資料",
                    rec["status"]
                    + "；主案仍採上次回傳值，需重新帶入或確認為獨立設定。",
                    next(iter(rec["values"]), None),
                )
        result["quality"] = assessment(items)

    def apply_contribution(self, entry, parent=None):
        from .workspace_view import apply_updates
        from .engine import std_lpm
        import math

        inputs = self.snapshot()["inputs"]
        ledger = copy.deepcopy(getattr(self, "demand_ledger", empty_ledger()))
        new_keys = (set(entry["updates"]) & SUM_KEYS) - set(ledger["last_updates"])
        old_loads = {}
        for key in new_keys:
            value = float(inputs[key])
            if key.startswith("e_"):
                unit = inputs["u_" + key]
                pan = key.split("_")[1]
                pf = float(inputs["e_" + pan + "_pf"] if inputs.get("e_" + pan + "_pf_mode") == "本盤獨立 PF" else inputs["e_pf"])
                from .data import VOLTAGE_MAP
                value = value if unit == "kW" else value * .745699871582 / float(inputs["e_eff"]) if unit == "HP" else value * math.sqrt(3) * VOLTAGE_MAP[inputs["e_volt"]] * pf / 1000
            elif key.startswith("gas") or key == "pv_q":
                value = std_lpm(value, inputs["u_" + key.removesuffix("_q")])
            elif key.endswith("ex_q"):
                value *= 1.69901079552 if inputs["u_" + key.removesuffix("_q")] == "CFM" else 1
            old_loads[key] = value
        if any(old_loads.values()):
            answer = messagebox.askyesnocancel("其他設備的原有需求", "目前目的欄位已有數值。這些是本次來源以外的其他設備嗎？\n是：作為其他服務基數保留並累加。\n否：改採來源彙整，原值保留供移除來源時復原。\n取消：不帶入。\n水迴路原負荷不自動相加，避免同一盤管重複計入。", parent=parent or self.root)
            if answer is None:
                return False
            ledger["baseline"].update({k: v if answer else 0.0 for k, v in old_loads.items()})
        next_ledger, updates, summary = updated_ledger(ledger, entry, inputs)
        note = entry["name"] + "\n同一識別碼更新，多個已回傳來源彙整。夏／冬分季求和後取較大水量。\n" + "\n".join(summary["notes"] + summary["pending"])
        if apply_updates(self, updates, note, parent, source_type="來源快照"):
            self.demand_ledger = next_ledger
            # Every active contributor owns the aggregate snapshot. Do not erase
            # earlier contributors merely because target fields overlap.
            for rec in self.transfer_receipts:
                if rec["source_id"] in next_ledger["entries"]:
                    rec["values"] = dict(summary["updates"])
            self.recalculate()
            self.refresh_session_status()
            return True
        return False

    def open_demand_ledger(self):
        """Inspect inclusion, remove a contribution, or choose a water circuit."""
        from .workspace_view import apply_updates
        win = tk.Toplevel(self.root)
        win.title("已納入需求的設備／迴路")
        win.geometry("1000x680")
        owner = self.project_id
        ttk.Label(win, text="只有明確回傳的來源才納入；同一台更新，多台才累加。下列不同水迴路不合併為一條總管。", wraplength=940, padding=12).pack(fill="x")
        sources = ttk.Treeview(win, columns=("kind", "name"), show="headings", height=5)
        sources.heading("kind", text="來源種類")
        sources.heading("name", text="已納入來源")
        sources.column("kind", width=100)
        sources.column("name", width=760)
        sources.pack(fill="x", padx=12)
        water = ttk.Treeview(win, columns=("loop", "condition", "summer", "winter", "design", "adopted"), show="headings", height=7)
        for key, label in zip(water["columns"], ("迴路", "供回水°C／服務群組", "夏 LPM", "冬 LPM", "設計 LPM", "主案採用")):
            water.heading(key, text=label)
            water.column(key, width=105 if key != "condition" else 290)
        water.pack(fill="both", expand=True, padx=12, pady=10)
        detail = tk.Text(win, height=6, wrap="word", state="disabled")
        detail.pack(fill="x", padx=12)

        def refresh():
            if owner != self.project_id:
                win.destroy()
                return
            sources.delete(*sources.get_children())
            water.delete(*water.get_children())
            try:
                summary = aggregate_ledger(self.demand_ledger, self.snapshot()["inputs"])
            except (ValueError, KeyError, TypeError) as exc:
                detail.config(state="normal")
                detail.delete("1.0", "end")
                detail.insert("1.0", str(exc))
                detail.config(state="disabled")
                return
            for entry in summary["sources"]:
                sources.insert("", "end", iid=entry["id"], values=(entry["kind"], entry["name"]))
            for group in summary["water"]:
                water.insert("", "end", iid=group["id"], values=(group["loop"], f"{group['supply']:g}/{group['return']:g}；{group['circuit']}", f"{group['summer_lpm']:.2f}", f"{group['winter_lpm']:.2f}", f"{group['design_lpm']:.2f}", "採用" if group["adopted"] else "未映射"))
            detail.config(state="normal")
            detail.delete("1.0", "end")
            detail.insert("1.0", "\n".join(summary["pending"] + ["其他設備基數：" + str(self.demand_ledger["baseline"])]))
            detail.config(state="disabled")
            return summary

        def remove():
            if owner != self.project_id or not sources.selection():
                return
            ident = sources.selection()[0]
            try:
                d, updates, summary = removed_ledger(self.demand_ledger, ident, self.snapshot()["inputs"])
            except (ValueError, KeyError, TypeError) as exc:
                messagebox.showerror("需求彙整待確認", str(exc), parent=win)
                return
            if apply_updates(self, updates, "只移除此來源的需求；單機設計文件仍保留。原採用值會在無其他來源且未手改時復原。", win):
                self.demand_ledger = d
                self.transfer_receipts = [r for r in self.transfer_receipts if r["source_id"] != ident]
                for rec in self.transfer_receipts:
                    if rec["source_id"] in d["entries"]:
                        rec["values"] = dict(summary["updates"])
                self.recalculate()
                refresh()

        def select_circuit():
            if owner != self.project_id or not water.selection():
                return
            ident = water.selection()[0]
            summary = refresh()
            if summary is None:
                return
            group = next(g for g in summary["water"] if g["id"] == ident)
            d = copy.deepcopy(self.demand_ledger)
            d["selections"][group["loop"]] = ident
            entry = next(iter(d["entries"].values()))
            d, updates, summary = updated_ledger(d, entry, self.snapshot()["inputs"])
            if apply_updates(self, updates, "主案 " + group["loop"] + " 水力列改採選取迴路；其餘迴路仍分列於彙整報告。", win):
                self.demand_ledger = d
                for rec in self.transfer_receipts:
                    if rec["source_id"] in d["entries"]:
                        rec["values"] = dict(summary["updates"])
                self.recalculate()
                refresh()

        bar = ttk.Frame(win, padding=12)
        bar.pack(fill="x")
        ttk.Button(bar, text="移除選取來源的需求", command=remove).pack(side="left")
        ttk.Button(bar, text="主案採用選取水迴路", command=select_circuit).pack(side="left", padx=8)
        ttk.Button(bar, text="重新讀取", command=refresh).pack(side="right")
        refresh()

    def add_receipt(self, child, values):
        receipt = dict(
            source_id=child.ahu_id,
            source_project_id=child.owner_project_id,
            source_name=child.vars["name"].get(),
            source_hash=ahu_source_hash(child.snapshot()),
            captured_at=datetime.now(timezone.utc).isoformat(),
            values=dict(values),
            status="與已保存來源條件一致",
        )
        for old in self.transfer_receipts:
            if old["source_id"] not in self.demand_ledger["entries"]:
                old["values"] = {k: v for k, v in old["values"].items() if k not in values}
        self.transfer_receipts = [x for x in self.transfer_receipts if x["values"] and x["source_id"] != child.ahu_id] + [
            receipt
        ]
        self.refresh_receipts()
        self.refresh_session_status()

    def open_ahu_manager(self):
        from .ahu_desktop import AHUWindow

        win = tk.Toplevel(self.root)
        win.title("空調箱管理｜" + self.variables["project_name"].get())
        win.geometry("660x420")
        ttk.Label(
            win, text="所有單機會隨整案保存；關閉單機視窗不會刪除設計。", padding=12
        ).pack(fill="x")
        listing = ttk.Treeview(win, columns=("name",), show="headings", height=10)
        listing.heading("name", text="本案空調箱")
        listing.pack(fill="both", expand=True, padx=12)
        documents = {x["id"]: x for x in self.session_snapshot()["ahus"]}
        for key, doc in documents.items():
            listing.insert("", "end", iid=key, values=(doc["inputs"]["name"],))
        owner = self.project_id

        def open_item(new=False):
            if owner != self.project_id:
                win.destroy()
                return
            selected = listing.selection()
            if not new and not selected:
                return
            ident = selected[0] if selected and not new else None
            existing = next(
                (x for x in self.children if getattr(x, "ahu_id", None) == ident), None
            )
            if existing:
                existing.win.lift()
            else:
                AHUWindow(self.root, self, document=documents.get(ident))
            win.destroy()
            self.refresh_session_status()

        bar = ttk.Frame(win, padding=12)
        bar.pack(fill="x")
        ttk.Button(bar, text="新增空調箱", command=lambda: open_item(True)).pack(
            side="left"
        )
        ttk.Button(bar, text="開啟選取單機", command=open_item).pack(side="right")
        listing.bind("<Double-1>", lambda event: open_item())
