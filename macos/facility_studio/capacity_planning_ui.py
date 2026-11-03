"""Independent capacity-plan editor. It never writes demand totals into the main project."""
import copy
import json
from pathlib import Path
from tkinter import simpledialog, Text as EditableText, ttk as NativeTtk
from uuid import uuid4

from .localized_tk import tk, ttk, filedialog, messagebox, attach_window
from .i18n import verbatim, translate
from . import capacity_planning as model
from .design_workflow import capacity_source_binding, capacity_plan_from_ledger
from .utils import atomic_text, project_hash

LABELS = {
    "id": "列 ID（重複編輯會取代）", "asset_id": "實體設備／來源 ID（防重複）", "name": "名稱",
    "boundary": "供應邊界／盤／迴路", "quantity": "台數", "phase": "階段 current／expansion",
    "coincidence": "同時率 0–1（未含在單台值時使用）", "included_margin_pct": "來源已含裕度 %（僅註記，不再乘）",
    "demand_complete": "需求完整性（需另行核對）",
    "derating": "容量降額係數 0–1", "reference": "來源文件／依據", "revision": "來源版次／日期",
    "voltage_v": "線電壓 V", "phases": "相數 1／3", "frequency_hz": "頻率 Hz",
    "fluid": "介質／濃度", "supply_c": "供水 °C", "return_c": "回水 °C", "rho_kg_m3": "密度 kg/m³",
    "cp_kj_kgk": "比熱 kJ/(kg·K)", "exhaust_type": "排氣種類", "temperature_c": "實際氣體溫度 °C",
    "absolute_kpa": "實際氣體絕壓 kPa", "required_static_pa": "同工況靜壓 Pa",
}


class RowDialog:
    def __init__(self, parent, plan, kind, row, commit):
        self.plan, self.kind, self.row, self.commit = plan, kind, copy.deepcopy(row), commit
        self.win = tk.Toplevel(parent)
        attach_window(self.win)
        self.win.title("編輯需求" if kind == "demand" else "編輯供應容量")
        self.win.geometry("760x720")
        self.win.minsize(660, 520)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.columnconfigure(0, weight=1)
        self.win.rowconfigure(1, weight=1)
        ttk.Label(self.win, text="空白代表未知，明確填 0 才是零；容量為同工況單台額定值，需求為單台用量。", wraplength=650).grid(row=0, column=0, sticky="w", padx=12, pady=8)
        notebook = ttk.Notebook(self.win)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10)
        self.variables = {}
        top_keys = ["id", "asset_id", "name", "boundary", "quantity"] + (["phase", "coincidence", "included_margin_pct", "demand_complete"] if kind == "demand" else ["derating"])
        for title, fields in (("① 身分與用量", [("top", k) for k in top_keys] + [("values", k) for k in plan["cases"]]),
                              ("② 同工況與來源", [("conditions", k) for k in model.CONDITIONS[row["system"]]] + [("source", k) for k in ("reference", "revision")])):
            outer = ttk.Frame(notebook)
            notebook.add(outer, text=title)
            canvas = tk.Canvas(outer, highlightthickness=0)
            scrollbar = ttk.Scrollbar(outer, command=canvas.yview)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            canvas.configure(yscrollcommand=scrollbar.set)
            frame = ttk.Frame(canvas, padding=8)
            frame.columnconfigure(1, weight=1)
            item = canvas.create_window(0, 0, window=frame, anchor="nw")
            frame.bind("<Configure>", lambda event, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.bind("<Configure>", lambda event, c=canvas, i=item: c.itemconfigure(i, width=event.width))
            for n, (section, key) in enumerate(fields):
                label = verbatim(key) + " 單台 " + model.UNITS[row["system"]] if section == "values" else LABELS[key]
                ttk.Label(frame, text=label, wraplength=240).grid(row=n, column=0, sticky="w", padx=4, pady=5)
                value = row[key] if section == "top" else row[section][key]
                var = tk.BooleanVar(value=value) if key == "demand_complete" and section == "top" else tk.StringVar(value="" if value is None else str(value))
                self.variables[section, key] = var
                if section == "top" and key == "demand_complete":
                    ttk.Checkbutton(frame, text="已核對為完整需求，非僅已知小計", variable=var).grid(row=n, column=1, sticky="w")
                elif section == "top" and key == "phase":
                    ttk.Combobox(frame, textvariable=var, values=("current", "expansion"), state="readonly").grid(row=n, column=1, sticky="ew")
                else:
                    ttk.Entry(frame, textvariable=var).grid(row=n, column=1, sticky="ew")
        notes = ttk.Frame(notebook, padding=8)
        notebook.add(notes, text="③ 待辦與註記")
        ttk.Label(notes, text="來源待辦每行一筆。只有資料與工況已核對後才能移除；刪字不代表工程核准。", wraplength=650).pack(anchor="w")
        self.pending = EditableText(notes, height=7, wrap="word")
        self.pending.pack(fill="both", expand=True, pady=5)
        self.pending.insert("1.0", "\n".join(row["pending"]))
        ttk.Label(notes, text="註記／核對依據（每行一筆）").pack(anchor="w")
        self.notes = EditableText(notes, height=7, wrap="word")
        self.notes.pack(fill="both", expand=True, pady=5)
        self.notes.insert("1.0", "\n".join(row["notes"]))
        bar = ttk.Frame(self.win, padding=10)
        bar.grid(row=2, column=0, sticky="e")
        ttk.Button(bar, text="取消", command=self.win.destroy).pack(side="left", padx=4)
        ttk.Button(bar, text="核對並儲存此列", command=self.save).pack(side="left")

    def save(self):
        try:
            row = copy.deepcopy(self.row)
            text_keys = {"id", "asset_id", "name", "boundary", "phase", "fluid", "exhaust_type", "reference", "revision"}
            for (section, key), var in self.variables.items():
                if section == "top" and key == "demand_complete":
                    row[key] = bool(var.get())
                    continue
                raw = var.get().strip()
                text_value = section == "source" or (section != "values" and key in text_keys)
                value = (raw or None) if text_value else (None if not raw else int(raw) if section == "top" and key == "quantity" else float(raw))
                if section == "top":
                    row[key] = value if value is not None else "" if text_value else None
                elif section == "source":
                    row[section][key] = raw
                else:
                    row[section][key] = value
            row["pending"] = [x.strip() for x in self.pending.get("1.0", "end").splitlines() if x.strip()]
            row["notes"] = [x.strip() for x in self.notes.get("1.0", "end").splitlines() if x.strip()]
            self.commit(self.kind, self.row["id"], row)
            self.win.destroy()
        except (ValueError, TypeError, KeyError) as error:
            messagebox.showerror("容量計畫", str(error), parent=self.win)


class CapacityPlanningWindow:
    independent_capacity_plan = True
    project_bound = False  # survives a main-project switch; linked snapshot then becomes stale

    def __init__(self, parent, main):
        self.main = main
        self.plan = model.new_plan()
        self.saved_hash = project_hash(self.plan)
        self.path = None
        self.win = tk.Toplevel(parent)
        attach_window(self.win)
        self.win.title("容量／擴建／替代方案")
        self.win.geometry("1120x800")
        self.win.minsize(960, 700)
        main.children.append(self)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.columnconfigure(0, weight=1)
        self.win.rowconfigure(2, weight=1)
        bar = ttk.Frame(self.win, padding=8)
        bar.grid(row=0, column=0, sticky="ew")
        for label, action in (("新增", self.new), ("開啟", self.open), ("另存計畫", self.save),
                              ("從需求彙整擷取", self.import_ledger), ("重算", self.refresh), ("匯出報告", self.export)):
            ttk.Button(bar, text=label, command=lambda f=action: self.guard(f)).pack(side="left", padx=3)
        basis = ttk.Frame(self.win, padding=8)
        basis.grid(row=1, column=0, sticky="ew")
        basis.columnconfigure(1, weight=1)
        self.variables = {key: tk.StringVar() for key in ("name", "scope", "additional_margin_pct", "margin_reason")}
        for n, (key, label) in enumerate((("name", "計畫名稱"), ("scope", "完整服務範圍"),
                                         ("additional_margin_pct", "額外裕度 %（只套用一次）"), ("margin_reason", "額外裕度依據"))):
            ttk.Label(basis, text=label).grid(row=n, column=0, sticky="w", padx=4)
            ttk.Entry(basis, textvariable=self.variables[key]).grid(row=n, column=1, sticky="ew", pady=2)
        self.confirmed = tk.BooleanVar()
        ttk.Checkbutton(basis, text="已核對範圍、完整清單及 N−1 供應假設（非工程簽核）", variable=self.confirmed).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)
        nb = ttk.Notebook(self.win)
        nb.grid(row=2, column=0, sticky="nsew", padx=10)
        self.trees = {}
        for kind, title in (("demand", "① 現有／擴建需求"), ("capacity", "② 供應容量")):
            frame = ttk.Frame(nb, padding=8)
            nb.add(frame, text=title)
            toolbar = ttk.Frame(frame)
            toolbar.pack(fill="x")
            system = tk.StringVar(value="ELECTRIC")
            ttk.Combobox(toolbar, textvariable=system, values=tuple(model.UNITS), state="readonly", width=12).pack(side="left")
            for label, action in (("新增列", lambda k=kind, v=system: self.edit(k, v.get(), new=True)),
                                  ("編輯選取", lambda k=kind: self.edit(k)), ("刪除選取", lambda k=kind: self.remove(k))):
                ttk.Button(toolbar, text=label, command=lambda f=action: self.guard(f)).pack(side="left", padx=4)
            tree = ttk.Treeview(frame, columns=("id", "name", "system", "phase", "boundary"), show="headings", selectmode="extended")
            for key, text, width in (("id", "ID", 190), ("name", "名稱", 210), ("system", "系統／單位", 130), ("phase", "階段／台數", 130), ("boundary", "供應邊界", 250)):
                tree.heading(key, text=text)
                tree.column(key, width=width, stretch=True)
            tree.pack(fill="both", expand=True, pady=6)
            tree.bind("<Double-1>", lambda event, k=kind: self.guard(lambda: self.edit(k)))
            self.trees[kind] = tree
        output = ttk.Frame(nb, padding=8)
        nb.add(output, text="③ 方案與結果")
        actions = ttk.Frame(output)
        actions.pack(fill="x")
        ttk.Button(actions, text="將兩頁選取列記為方案", command=lambda: self.guard(self.add_alternative)).pack(side="left")
        self.alt = tk.StringVar()
        self.alt_combo = NativeTtk.Combobox(actions, textvariable=self.alt, state="readonly", width=25)
        self.alt_combo.pack(side="left", padx=5)
        ttk.Button(actions, text="刪除該方案", command=lambda: self.guard(self.remove_alternative)).pack(side="left")
        ttk.Label(output, text="未建立方案時評估全部列；已有方案時只評估各方案明選的列。不同方案互為替代，不加總。", wraplength=950).pack(anchor="w", pady=5)
        self.output = tk.Text(output, wrap="word", state="disabled")
        self.output.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(output, command=self.output.yview)
        scroll.pack(side="right", fill="y")
        self.output.config(yscrollcommand=scroll.set)
        self.status = tk.StringVar()
        ttk.Label(self.win, textvariable=self.status, wraplength=1000).grid(row=3, column=0, sticky="w", padx=12, pady=8)
        self.install(self.plan)
        for key, var in self.variables.items():
            var.trace_add("write", lambda *args, field=key: self.basis_changed(field))
        self.confirmed.trace_add("write", self.changed)

    def basis_changed(self, field):
        if not getattr(self, "loading", False) and field != "name":
            self.confirmed.set(False)
        self.changed()

    def changed(self, *args):
        if not getattr(self, "loading", False):
            self.result = None
            self.status.set("輸入已變更，舊結果不可沿用；重算／匯出時重新核對。")
            self.output.configure(state="normal")
            self.output.delete("1.0", "end")
            self.output.insert("1.0", "輸入已變更，請重算。")
            self.output.configure(state="disabled")

    def guard(self, action):
        try:
            return action()
        except (ValueError, TypeError, KeyError, OSError) as error:
            self.status.set(str(error))
            messagebox.showerror("容量計畫", str(error), parent=self.win)

    def sync(self):
        p = copy.deepcopy(self.plan)
        p.update({key: var.get().strip() for key, var in self.variables.items()})
        p["additional_margin_pct"] = float(p["additional_margin_pct"])
        p["scope_confirmed"] = bool(self.confirmed.get())
        self.plan = model.validate_plan(p)

    def install(self, plan, path=None):
        self.loading = True
        try:
            self.plan = model.validate_plan(plan)
            self.path = path
            self.saved_hash = project_hash(self.plan)
            for key, var in self.variables.items():
                var.set(str(self.plan[key]))
            self.confirmed.set(self.plan["scope_confirmed"])
        finally:
            self.loading = False
        self.refresh()

    def refresh(self):
        self.changed()
        self.result = None
        self.sync()
        for kind, tree in self.trees.items():
            selected = tree.selection()
            tree.delete(*tree.get_children())
            for row in self.plan["demands" if kind == "demand" else "capacities"]:
                tree.insert("", "end", iid=row["id"], values=(verbatim(row["id"]), verbatim(row["name"]), row["system"] + " " + model.UNITS[row["system"]], row.get("phase", str(row["quantity"]) + " 台"), verbatim(row["boundary"])))
            tree.selection_set([ident for ident in selected if tree.exists(ident)])
        self.alt_combo.configure(values=[a["id"] for a in self.plan["alternatives"]])
        binding = capacity_source_binding(self.main.session_snapshot())
        self.source_binding = binding
        self.result = model.evaluate_plan(self.plan, current_binding=binding)
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", model.capacity_report(self.result))
        self.output.configure(state="disabled")
        self.status.set(("來源已過期，請重新擷取並覆核。" if self.result["stale"] else "已依本次輸入重算。") + "容量計畫需獨立另存，不會寫回主案。")
        return self.result

    def on_main_changed(self):
        binding = capacity_source_binding(self.main.session_snapshot())
        if self.plan["binding"] is not None and binding != getattr(self, "source_binding", None):
            self.source_binding = binding
            self.result = None
            self.changed()
            self.status.set("主案可能已變更；匯出前會重新核對來源，舊結果不可沿用。")

    def may_close(self):
        try:
            self.sync()
            dirty = project_hash(self.plan) != self.saved_hash
        except (ValueError, TypeError):
            dirty = True
        return not dirty or messagebox.askyesno("未儲存容量計畫", "容量計畫尚未另存，確定捨棄這些變更嗎？", parent=self.win)

    def close(self, force=False):
        if not force and not self.may_close():
            return False
        if self in self.main.children:
            self.main.children.remove(self)
        self.win.destroy()
        return True

    def new(self):
        if self.may_close():
            self.install(model.new_plan())

    def draft_signature(self):
        return (project_hash(self.plan), tuple(sorted((key, var.get()) for key, var in self.variables.items())),
                self.confirmed.get())

    def open(self):
        if not self.may_close():
            return
        signature = self.draft_signature()
        path = filedialog.askopenfilename(parent=self.win, filetypes=[("容量計畫 JSON", "*.json")])
        if path:
            # Opening a file must not silently discard edits dispatched by the dialog.
            if signature != self.draft_signature() and not self.may_close():
                return
            self.install(model.read_plan(path), path)

    def save(self, path=None):
        self.sync()
        path = path or filedialog.asksaveasfilename(parent=self.win, defaultextension=".json", initialfile="Capacity_Plan.json")
        if path:
            self.sync()  # modal file dialogs may dispatch edits before they return
            content = json.dumps(self.plan, ensure_ascii=False, indent=2, allow_nan=False)
            if len(content.encode("utf-8")) > 4_000_000:
                raise ValueError("容量計畫不得超過 4 MB")
            atomic_text(path, content)
            self.saved_hash, self.path = project_hash(self.plan), path
            self.status.set("已儲存獨立容量計畫：" + verbatim(str(path)))
            return Path(path)

    def export(self, path=None):
        result = self.refresh()  # always recompute against current live sources
        path = path or filedialog.asksaveasfilename(parent=self.win, defaultextension=".txt", initialfile="Capacity_Report.txt")
        if path:
            result = self.refresh()  # sources may have changed during the modal dialog
            atomic_text(path, model.capacity_report(result))
            return Path(path)

    def import_ledger(self):
        if not self.may_close():
            return
        plan = capacity_plan_from_ledger(self.main.session_snapshot())
        self.install(plan)
        self.saved_hash = ""  # a captured partial register must still be saved

    def edit(self, kind, system="ELECTRIC", new=False):
        self.sync()
        selection = self.trees[kind].selection()
        if not new and len(selection) != 1:
            raise ValueError("請選取一列編輯")
        field = "demands" if kind == "demand" else "capacities"
        row = model.new_row(kind, kind + "-" + uuid4().hex[:10], system, self.plan["cases"]) if new else next(r for r in self.plan[field] if r["id"] == selection[0])
        return RowDialog(self.win, self.plan, kind, row, self.commit_row)

    def commit_row(self, kind, old_id, row):
        self.sync()
        p = copy.deepcopy(self.plan)
        field = "demands" if kind == "demand" else "capacities"
        if row["id"] != old_id:
            if any(r["id"] == row["id"] for r in p[field]):
                raise ValueError("新的 ID 已存在，不可覆蓋其他列")
            p[field] = [r for r in p[field] if r["id"] != old_id]
            for alt in p["alternatives"]:
                key = "demand_ids" if kind == "demand" else "capacity_ids"
                alt[key] = [row["id"] if ident == old_id else ident for ident in alt[key]]
        old = next((r for r in self.plan[field] if r["id"] == old_id), None)
        if old and old["source"]["fingerprint"] and row != old:
            row = copy.deepcopy(row)
            note = "擷取後已人工修改；來源指紋只追溯原始快照，不代表修改值已由來源確認。"
            if note not in row["notes"]:
                row["notes"].append(note)
            if all(row["source"][k] == old["source"][k] for k in ("reference", "revision")):
                issue = "人工修改值需補新的來源文件／版次並覆核，再移除此待辦。"
                if issue not in row["pending"]:
                    row["pending"].append(issue)
        self.plan = model.upsert_row(p, kind, row)
        self.confirmed.set(False)
        self.refresh()

    def remove(self, kind):
        self.sync()
        ids = set(self.trees[kind].selection())
        if not ids or not messagebox.askyesno("刪除列", "刪除選取列及方案中的對應引用？", parent=self.win):
            return
        field = "demands" if kind == "demand" else "capacities"
        self.plan[field] = [r for r in self.plan[field] if r["id"] not in ids]
        for alt in self.plan["alternatives"]:
            key = "demand_ids" if kind == "demand" else "capacity_ids"
            alt[key] = [ident for ident in alt[key] if ident not in ids]
        self.confirmed.set(False)
        self.refresh()

    def add_alternative(self):
        self.sync()
        ids = {kind: list(tree.selection()) for kind, tree in self.trees.items()}
        if not ids["demand"]:
            raise ValueError("先在需求頁選取此方案的全部現有／擴建需求，再選取供應列")
        name = simpledialog.askstring(translate("替代方案"), translate("方案名稱"), parent=self.win)
        if name:
            p = copy.deepcopy(self.plan)
            p["alternatives"].append(dict(id="alt-" + uuid4().hex[:8], name=name, demand_ids=ids["demand"], capacity_ids=ids["capacity"]))
            self.plan = model.validate_plan(p)
            self.confirmed.set(False)
            self.refresh()

    def remove_alternative(self):
        self.sync()
        ident = self.alt.get()
        if ident and messagebox.askyesno("刪除方案", "僅移除選取方案，保留來源列？", parent=self.win):
            self.plan["alternatives"] = [a for a in self.plan["alternatives"] if a["id"] != ident]
            self.alt.set("")
            self.confirmed.set(False)
            self.refresh()
