"""Whole-project lifecycle and explicit cross-window ownership."""
import copy
import uuid
from datetime import datetime, timezone
from tkinter import messagebox, filedialog, ttk
import tkinter as tk
from .schema import VERSION, default_project
from .utils import project_hash
from .engine import calculate
from .workspace_store import validate_workspace, read_workspace
from .project_store import save_project_file, recovery_save
from .design_workflow import ahu_requirement_updates, ahu_source_hash


class SessionController:
    def session_snapshot(self):
        documents = copy.deepcopy(self.ahu_documents)
        for child in list(self.children):
            if hasattr(child, "ahu_id") and child.owner_project_id == self.project_id and child.win.winfo_exists():
                documents[child.ahu_id] = child.document()
        return dict(kind="facility_workspace", workspace_version=1,
                    app_version=VERSION, project_id=self.project_id,
                    main=self.snapshot(), ahus=list(documents.values()),
                    comparisons=copy.deepcopy(self.comparisons),
                    receipts=copy.deepcopy(self.transfer_receipts),
                    drafts=copy.deepcopy(self.field_drafts))

    def session_dirty(self):
        return project_hash(self.session_snapshot()) != self.saved_workspace_hash

    def refresh_session_status(self):
        if hasattr(self, "document_status"):
            count = len(self.session_snapshot()["ahus"])
            saved = "未儲存變更" if self.session_dirty() else "專案已儲存" if self.path else "尚未另存完整專案"
            self.document_status.set(f"{self.variables['project_name'].get()}｜{saved}｜主案＋{count} 台空調箱＋A/B")

    def confirm_session_discard(self):
        return not self.session_dirty() or messagebox.askyesno(
            "整案尚未儲存", "主案、空調箱或 A/B 有未儲存修改。確定捨棄並切換案件？", parent=self.root)

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
        self.undo_project = None
        self.undo_aux = None
        self.path = None
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
        self.path = path
        self.undo_project = None
        self.undo_aux = None
        self.restore_snapshot(d["main"])
        self.saved_hash = project_hash(self.snapshot())
        self.saved_workspace_hash = project_hash(self.session_snapshot()) if path else ""
        self.notify_children()
        self.refresh_receipts()
        self.refresh_session_status()

    def open_workspace(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("整案／舊主案 JSON", "*.json")])
        if not path:
            return
        try:
            doc = read_workspace(path)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            messagebox.showerror("不能開啟專案", str(exc), parent=self.root)
            return
        if self.confirm_session_discard():
            self.apply_workspace(doc, path)

    def save_workspace(self, path=None):
        path = path or self.path or filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".json", initialfile="Facility_Project.json",
            filetypes=[("完整專案（主案、空調箱、A/B）", "*.json")])
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
            answer = messagebox.askyesnocancel("整案未儲存", "關閉前儲存主案、所有空調箱及 A/B？\n無效輸入也可作為草稿保存。", parent=self.root)
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
            active = {k: v for k, v in receipt["values"].items()
                      if self.variables[k].get() == v and self.provenance[k]["source"] == "來源快照"}
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
            self.receipt_status.set("；".join(notices) or "資料交換採來源快照；重新帶入前不會自動覆寫。")
        result = getattr(self, "result", None)
        if result is not None:
            self.decorate_receipts(result)
            from .reports import report
            from .ui_common import quality_text, quality_style
            self.set_report(report(result))
            self.quality_label.config(text=quality_text(result["quality"]), style=quality_style(result["quality"]))
            self.status.config(text=result["quality"]["status"] + "｜結果與來源狀態已同步", style=quality_style(result["quality"]))
        return notices

    def decorate_receipts(self, result):
        from .quality import assessment, finding
        if "base_quality" not in result:
            result["base_quality"] = copy.deepcopy(result["quality"])
        items = copy.deepcopy(result["base_quality"]["items"])
        result["source_receipts"] = copy.deepcopy(self.transfer_receipts)
        for rec in self.transfer_receipts:
            if "過期" in rec["status"] or "來源未" in rec["status"]:
                finding(items, "來源快照：" + rec["source_name"], "待資料",
                        rec["status"] + "；主案仍採上次回傳值，需重新帶入或確認為獨立設定。",
                        next(iter(rec["values"]), None))
        result["quality"] = assessment(items)

    def add_receipt(self, child, values):
        receipt = dict(source_id=child.ahu_id, source_project_id=child.owner_project_id,
                       source_name=child.vars["name"].get(), source_hash=ahu_source_hash(child.snapshot()),
                       captured_at=datetime.now(timezone.utc).isoformat(), values=dict(values),
                       status="與已保存來源條件一致")
        # A new snapshot replaces only the overlapping target fields in older receipts.
        for old in self.transfer_receipts:
            old["values"] = {k: v for k, v in old["values"].items() if k not in values}
        self.transfer_receipts = [x for x in self.transfer_receipts if x["values"]] + [receipt]
        self.refresh_receipts()
        self.refresh_session_status()

    def open_ahu_manager(self):
        from .ahu_desktop import AHUWindow
        win = tk.Toplevel(self.root)
        win.title("空調箱管理｜" + self.variables["project_name"].get())
        win.geometry("660x420")
        ttk.Label(win, text="所有單機會隨整案保存；關閉單機視窗不會刪除設計。", padding=12).pack(fill="x")
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
            existing = next((x for x in self.children if getattr(x, "ahu_id", None) == ident), None)
            if existing:
                existing.win.lift()
            else:
                AHUWindow(self.root, self, document=documents.get(ident))
            win.destroy()
            self.refresh_session_status()
        bar = ttk.Frame(win, padding=12)
        bar.pack(fill="x")
        ttk.Button(bar, text="新增空調箱", command=lambda: open_item(True)).pack(side="left")
        ttk.Button(bar, text="開啟選取單機", command=open_item).pack(side="right")
        listing.bind("<Double-1>", lambda event: open_item())
