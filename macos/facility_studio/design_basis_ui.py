"""Traditional Chinese document-register UI, with immutable saved revisions."""
from pathlib import Path
from uuid import uuid4

from .localized_tk import tk, ttk, filedialog, messagebox
from . import design_basis as model


class DesignReviewWindow:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("Facility Studio｜設計依據與交付審查")
        self.win.geometry("1000x760")
        self.win.minsize(820, 650)
        self.data = model.new_dossier()
        self.folder = None
        self.current = "basis"
        self.win.columnconfigure(0, weight=1)
        self.win.rowconfigure(2, weight=1)
        toolbar = ttk.Frame(self.win, padding=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        for label, action in (("新增獨立專案", self.new_project), ("開啟已存版次", self.open_project),
                              ("另存新版次", self.save), ("核對並匯出報告", self.export)):
            ttk.Button(toolbar, text=label, command=lambda f=action: self.guard(f)).pack(side="left", padx=3)
        self.location = tk.StringVar(value="先新增專案或開啟已存版次；不會更動原計算專案。")
        ttk.Label(self.win, textvariable=self.location, wraplength=780).grid(row=1, column=0, sticky="ew", padx=12)
        notebook = ttk.Notebook(self.win)
        notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=8)
        basis_tab, docs_tab = ttk.Frame(notebook, padding=10), ttk.Frame(notebook, padding=10)
        notebook.add(basis_tab, text="① 設計依據與規範")
        notebook.add(docs_tab, text="② 文件與人工覆核")
        basis_tab.columnconfigure(1, weight=1)
        self.variables = {}
        for row, (key, label) in enumerate(model.FIELDS.items()):
            ttk.Label(basis_tab, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=4)
            var = tk.StringVar(value="")
            self.variables[key] = var
            ttk.Entry(basis_tab, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(basis_tab, text="規範每行一筆，以 ｜ 分隔：名稱｜版次｜條號｜適用範圍｜來源網址或文件編號",
                  wraplength=740).grid(row=9, column=0, columnspan=2, sticky="w", pady=(14, 4))
        self.standards = tk.Text(basis_tab, height=6, wrap="word")
        self.standards.grid(row=10, column=0, columnspan=2, sticky="nsew")
        basis_tab.rowconfigure(10, weight=1)
        ttk.Label(basis_tab, text="這些是專案指定的適用依據；附件應另保存授權可用的規範／業主文件。",
                  wraplength=740).grid(row=11, column=0, columnspan=2, sticky="w", pady=8)
        docs_tab.columnconfigure(0, weight=1)
        docs_tab.rowconfigure(0, weight=1)
        columns = ("document", "status")
        self.tree = ttk.Treeview(docs_tab, columns=columns, show="headings", height=12, selectmode="browse")
        self.tree.heading("document", text="交付項目")
        self.tree.heading("status", text="證據與覆核狀態")
        self.tree.column("document", width=270)
        self.tree.column("status", width=420)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(docs_tab, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.select_document())
        for key, label in model.DELIVERABLES.items():
            self.tree.insert("", "end", iid=key, values=(label, "待處理"))
        self.tree.selection_set("basis")
        form = ttk.Frame(docs_tab)
        form.grid(row=1, column=0, sticky="ew", pady=8)
        form.columnconfigure(1, weight=1)
        self.exclusion, self.reviewer, self.comment = (tk.StringVar() for _ in range(3))
        for row, (label, var) in enumerate((("不適用理由（適用時留空）", self.exclusion),
                                           ("人工覆核者（非編製者）", self.reviewer),
                                           ("覆核意見與依據", self.comment))):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=4)
            ttk.Entry(form, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
        actions = ttk.Frame(docs_tab)
        actions.grid(row=2, column=0, sticky="ew")
        for label, action in (("附加本項證據", self.attach), ("重新核對", self.refresh),
                              ("記錄覆核接受", lambda: self.review("accepted")),
                              ("記錄要求修正", lambda: self.review("rejected"))):
            ttk.Button(actions, text=label, command=lambda f=action: self.guard(f)).pack(side="left", padx=3)
        self.details = tk.Text(docs_tab, height=5, wrap="word", state="disabled")
        self.details.grid(row=3, column=0, sticky="ew", pady=6)
        self.status = tk.StringVar(value="尚未核對。" + model.LIMITATION)
        ttk.Label(self.win, textvariable=self.status, wraplength=790).grid(row=3, column=0, sticky="ew", padx=12, pady=10)
        for var in (*self.variables.values(), self.exclusion):
            var.trace_add("write", lambda *args: self.changed())
        self.standards.bind("<<Modified>>", self.changed)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.dirty = False

    def changed(self, *args):
        if getattr(self, "_loading_document", False):
            return
        if args and hasattr(args[0], "widget") and args[0].widget == self.standards:
            if not self.standards.edit_modified():
                return
            self.standards.edit_modified(False)
        self.dirty = True
        self.status.set("輸入已變更；儲存／匯出前會重新核對，既有覆核可能失效。")

    def guard(self, action):
        try:
            return action()
        except (ValueError, OSError, TypeError) as error:
            self.status.set(str(error))
            messagebox.showerror("設計審查", str(error), parent=self.win)

    def require_folder(self):
        if self.folder is None:
            raise ValueError("請先新增獨立專案或開啟已存版次")

    def sync(self):
        standards = []
        for line in self.standards.get("1.0", "end").splitlines():
            if not line.strip():
                continue
            parts = [s.strip() for s in line.split("｜")]
            if len(parts) != 5 or not all(parts):
                raise ValueError("每筆規範須填五個欄位，使用全形 ｜ 分隔")
            standards.append(dict(zip(("name", "edition", "clause", "scope", "source"), parts)))
        self.data["basis"] = {key: var.get() for key, var in self.variables.items()}
        self.data["standards"] = standards
        self.data["documents"][self.current]["exclusion"] = self.exclusion.get()
        model.validate(self.data)

    def select_document(self):
        selection = self.tree.selection()
        if not selection or selection[0] == self.current:
            return
        self.data["documents"][self.current]["exclusion"] = self.exclusion.get()
        self.current = selection[0]
        # Displaying another row is navigation, not an edit. Genuine exclusion
        # edits already set dirty via the variable trace before selection changes.
        self._loading_document = True
        try:
            self.exclusion.set(self.data["documents"][self.current]["exclusion"])
        finally:
            self._loading_document = False
        self.comment.set("")
        self.show_details()

    def show_details(self):
        document = self.data["documents"][self.current]
        lines = ["附件：" + r["name"] for r in document["evidence"]] or ["尚無附件；請附加原計算工具匯出的報告或相關設計文件。"]
        review = self.data["reviews"].get(self.current)
        if review:
            lines.append("先前填報覆核：" + review["reviewer"] + "｜" + review["comment"])
        if hasattr(self, "last_state"):
            lines += next(row["issues"] for row in self.last_state["rows"] if row["key"] == self.current)
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", "\n".join(lines))
        self.details.configure(state="disabled")

    def refresh(self):
        self.require_folder()
        self.sync()
        state = model.evaluate(self.data, self.folder)
        self.last_state = state
        for row in state["rows"]:
            self.tree.item(row["key"], values=(row["label"], "；".join(row["issues"]) or row["status"]))
        missing = "；待填：" + "、".join(state["missing_basis"]) if state["missing_basis"] else ""
        self.status.set(state["status"] + missing + "。" + model.LIMITATION)
        self.show_details()
        return state

    def confirm_discard(self):
        return not self.dirty or messagebox.askyesno("未儲存變更", "目前輸入尚未另存版次，確定離開嗎？", parent=self.win)

    def new_project(self):
        if not self.confirm_discard():
            return
        parent = filedialog.askdirectory(title="選擇存放位置（會建立新的獨立資料夾）", parent=self.win)
        if not parent:
            return
        folder = Path(parent) / ("Facility Studio 設計審查_" + uuid4().hex[:12])
        folder.mkdir(exist_ok=False)
        self.install(model.new_dossier(), folder)

    def open_project(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(title="開啟設計審查版次", filetypes=[("設計審查", "*.json")], parent=self.win)
        if path:
            self.install(model.load_revision(path), Path(path).parent)

    def install(self, data, folder):
        self.data, self.folder, self.current = data, Path(folder), "basis"
        for key, var in self.variables.items():
            var.set(data["basis"][key])
        self.standards.delete("1.0", "end")
        self.standards.insert("1.0", "\n".join("｜".join(s[k] for k in ("name", "edition", "clause", "scope", "source")) for s in data["standards"]))
        self.standards.edit_modified(False)
        self.exclusion.set(data["documents"]["basis"]["exclusion"])
        self.reviewer.set("")
        self.comment.set("")
        self.tree.selection_set("basis")
        self.location.set(str(self.folder))
        self.refresh()
        self.dirty = False

    def attach(self):
        self.require_folder()
        self.sync()
        source = filedialog.askopenfilename(title="選擇已核對來源的設計證據（將複製到獨立專案）", parent=self.win)
        if source:
            model.attach(self.data, self.folder, self.current, source)
            self.dirty = True
            self.refresh()

    def review(self, decision):
        self.require_folder()
        self.sync()
        model.record_review(self.data, self.folder, self.current, self.reviewer.get(), decision, self.comment.get())
        self.dirty = True
        self.refresh()

    def save(self):
        self.refresh()
        path = model.save_revision(self.data, self.folder)
        self.dirty = False
        self.location.set("已另存：" + str(path))
        return path

    def export(self):
        self.refresh()
        path, state = model.export_review(self.data, self.folder)
        self.dirty = False
        self.location.set("已匯出：" + str(path))
        return path

    def close(self):
        if self.confirm_discard():
            self.win.destroy()
