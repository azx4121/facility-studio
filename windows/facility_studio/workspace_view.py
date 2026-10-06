"""Reviewable project changes, parameter provenance, and frozen A/B comparisons."""

import copy
import json
from .database import load_tables
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .schema import FIELDS
from .project_store import SOURCE_TYPES, app_data, read_recovery
from .design_workflow import compare_results
from .ui_common import app_icon
from .utils import atomic_text
from .project_store import provenance_record
from datetime import datetime, timezone


def apply_updates(main, updates, note, parent=None, source_type="來源快照"):
    """Validate a temporary full project and preview scope before any mutation."""
    from .engine import calculate
    from .field_state import error_text
    from .project_store import provenance_record
    from .schema import GROUPS

    if not updates or set(updates) - set(FIELDS):
        return False
    candidate = main.snapshot()
    updates = {k: str(v) for k, v in updates.items()}
    candidate["inputs"].update(updates)
    try:
        result = calculate(candidate)
    except (ValueError, TypeError, KeyError) as exc:
        messagebox.showerror("帶入前檢核未通過", error_text(exc) + "\n原主案已保留，請修正目的欄位條件後再帶入。", parent=parent or main.root)
        return False
    groups = {k: title for _, title, keys in GROUPS for k in keys}
    lines = [f"{groups[k]} / {FIELDS[k]['label']}：{main.variables[k].get()} → {v} {FIELDS[k]['unit']}" for k, v in updates.items()]
    affected = []
    if set(updates) & {"water_rho", "water_cp", "water_mu"}:
        affected.append("共用水物性會同時影響 MCHW、CHW、DCCW、PCW、HW；請確認所有迴路為相同介質及工況。")
        affected.append("套用後物性：ρ=" + candidate["inputs"]["water_rho"] + " kg/m³，cp=" + candidate["inputs"]["water_cp"] + " kJ/(kg·K)，μ=" + candidate["inputs"]["water_mu"] + " Pa·s。")
    if set(updates) & {"duct_shape", "duct_ratio"}:
        affected.append("共用形狀／寬高比會同時影響 GEX、SEX、AEX、VEX、HEX。")
    for key in ["GEX", "SEX", "AEX", "VEX", "HEX"]:
        if key.lower() + "_q" in updates:
            d = result["ducts"][key]
            affected.append(f"{key}：名目 {d['nominal_cmh']:.2f} → 設計 {d['flow_cmh']:.2f} CMH（含主案風量餘裕）。")
    pending = [x["name"] for x in result["quality"]["items"] if x["status"] != "通過"]
    preview = "目的主案：" + main.variables["project_name"].get() + "\n" + note
    preview += "\n\n" + "\n".join(lines + affected)
    preview += "\n\n帶入後：" + result["quality"]["status"]
    if pending:
        preview += "（估算草稿）\n待確認：" + "、".join(pending)
    if not messagebox.askokcancel("確認帶入此主案", preview, parent=parent or main.root):
        return False
    main.remember_main_undo()
    main.suspended = True
    try:
        for key, value in updates.items():
            main.variables[key].set(value)
            main.provenance[key] = provenance_record(source_type, note, value)
    finally:
        main.suspended = False
    main.unit_previous = {k: main.variables[k].get() for k in main.unit_previous}
    main.latent_mode_previous = main.variables["latent_mode"].get()
    main.changed()
    main.interlocks()
    main.recalculate()
    return True


class WorkspaceWindow:
    def __init__(self, parent, main):
        self.main = main
        self.project_bound = True
        self.owner_project_id = main.project_id
        self.mark_token = None
        self.win = tk.Toplevel(parent)
        self.win.title("專案管理｜參數來源與方案比較")
        self.win.geometry("1050x760")
        self.win.minsize(820, 580)
        app_icon(self.win)
        main.children.append(self)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=12, pady=12)
        source = ttk.Frame(nb, padding=12)
        nb.add(source, text="參數來源")
        ttk.Label(
            source,
            text="預設值是估算起點；原廠資料需留下文件／選型編號。來源註記不會把初估升級成認證。",
            wraplength=940,
        ).pack(anchor="w")
        tree_frame = ttk.Frame(source)
        tree_frame.pack(fill="both", expand=True, pady=8)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("label", "value", "source", "note", "time"),
            show="headings",
            height=16,
        )
        for key, title, width in [
            ("label", "參數", 260),
            ("value", "目前值", 180),
            ("source", "來源", 110),
            ("note", "文件／說明", 330),
            ("time", "來源記錄時間 UTC", 190),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width)
        self.tree.pack(side="left", fill="both", expand=True)
        sc = ttk.Scrollbar(source, orient="horizontal", command=self.tree.xview)
        sc.pack(fill="x")
        self.tree.config(xscrollcommand=sc.set)
        vs = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vs.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=vs.set)
        self.origin = tk.StringVar(value="使用者輸入")
        self.note = tk.StringVar()
        self.tree.bind("<<TreeviewSelect>>", self.select)
        row = ttk.Frame(source)
        row.pack(fill="x", pady=8)
        ttk.Combobox(
            row,
            textvariable=self.origin,
            values=SOURCE_TYPES,
            state="readonly",
            width=16,
        ).pack(side="left")
        ttk.Entry(row, textvariable=self.note, width=40).pack(
            side="left", fill="x", expand=True, padx=8
        )
        ttk.Button(row, text="更新來源", command=self.mark).pack(side="left")
        ttk.Button(row, text="重新讀取", command=self.refresh).pack(side="left", padx=4)
        comparison = ttk.Frame(nb, padding=12)
        nb.add(comparison, text="方案 A／B")
        bar = ttk.Frame(comparison)
        bar.pack(fill="x")
        for tag in ["A", "B"]:
            ttk.Button(
                bar,
                text="將目前主案固定為 " + tag,
                command=lambda t=tag: self.capture(t),
            ).pack(side="left", padx=4)
        ttk.Button(bar, text="匯出比較紀錄", command=self.export_compare).pack(
            side="right"
        )
        ttk.Label(
            comparison,
            text="快照保留當時計算條件與雜湊；主案修改不會自動覆寫 A／B。請用相同計算邊界比較。",
        ).pack(anchor="w", pady=10)
        self.compare_text = tk.Text(comparison, wrap="word", state="disabled")
        self.compare_text.pack(fill="both", expand=True)
        recovery = ttk.Frame(nb, padding=16)
        nb.add(recovery, text="備份與計算依據")
        ttk.Label(
            recovery,
            text="每 30 秒保存整案復原快照（主案、空調箱、A/B、來源）；手動覆存保留上一份 .json.bak。\n無效輸入可保存為草稿，復原後仍會重新檢核。",
            wraplength=900,
        ).pack(anchor="w", pady=8)
        ttk.Button(recovery, text="選擇復原快照", command=self.restore).pack(
            anchor="w", pady=8
        )
        data = load_tables()
        txt = tk.Text(recovery, height=18, wrap="word")
        txt.pack(fill="both", expand=True, pady=8)
        txt.insert(
            "1.0",
            "工程資料表中繼資料（非現行法規認證）\n"
            + json.dumps(
                {k: v for k, v in data.items() if k != "tables"},
                ensure_ascii=False,
                indent=2,
            ),
        )
        txt.config(state="disabled")
        self.refresh()
        self.show_comparison()

    def refresh(self):
        for key, f in FIELDS.items():
            p = self.main.provenance[key]
            values = (
                    f["label"],
                    self.main.variables[key].get(),
                    p["source"],
                    p["note"],
                    p.get("recorded_at", "舊資料未記時間"),
                )
            if self.tree.exists(key):
                self.tree.item(key, values=values)
            else:
                self.tree.insert("", "end", iid=key, values=values)
        self.win.title("來源與方案｜" + self.main.variables["project_name"].get())

    def on_main_changed(self):
        self.refresh()
        self.show_comparison()

    def select(self, event=None):
        if self.tree.selection():
            key = self.tree.selection()[0]
            p = self.main.provenance[key]
            self.origin.set(p["source"])
            self.note.set(p["note"])
            self.mark_token = (self.main.project_id, key, self.main.variables[key].get())

    def mark(self):
        if not self.tree.selection():
            return
        key = self.tree.selection()[0]
        current = (self.main.project_id, key, self.main.variables[key].get())
        if self.mark_token != current:
            messagebox.showerror("數值已改變", "請重新選取目前值並核對文件後再標記來源。", parent=self.win)
            self.refresh()
            return
        if key == "upw_res" and self.main.variables["upw_quality_mode"].get() == "自動參考值":
            messagebox.showerror("自動參考值", "請先改為自訂水質規格，再將同工況數值標記為原廠資料。", parent=self.win)
            return
        if self.origin.get() == "原廠資料" and not self.note.get().strip():
            messagebox.showerror(
                "需補資料", "請填入原廠文件或選型編號", parent=self.win
            )
            return
        if len(self.note.get()) > 1000:
            return
        key = self.tree.selection()[0]
        self.main.provenance[key] = provenance_record(self.origin.get(), self.note.get(), self.main.variables[key].get())
        self.main.changed()
        self.main.recalculate()
        self.refresh()

    def capture(self, tag):
        if not self.main.ensure_result():
            return
        if not hasattr(self.main, "comparisons"):
            self.main.comparisons = {}
        self.main.comparisons[tag] = copy.deepcopy(self.main.result)
        self.main.comparisons[tag]["captured_at"] = datetime.now(timezone.utc).isoformat()
        self.main.comparisons[tag]["owner_project_id"] = self.main.project_id
        self.show_comparison()
        self.main.refresh_session_status()

    def comparison_string(self):
        cases = getattr(self.main, "comparisons", {})
        if not all(k in cases for k in ["A", "B"]):
            return "請分別固定方案 A 與 B。"
        r = compare_results(cases["A"], cases["B"])
        lines = [
            f"A：{cases['A']['project']['inputs']['project_name']}｜{cases['A'].get('captured_at', '舊快照')}｜{r['status_a']}｜V{cases['A'].get('version', '?')}",
            f"B：{cases['B']['project']['inputs']['project_name']}｜{cases['B'].get('captured_at', '舊快照')}｜{r['status_b']}｜V{cases['B'].get('version', '?')}",
            f"計算依據識別 A {r['hash_a']} / B {r['hash_b']}",
            "\n項目：A → B（B−A）",
        ]
        lines += [
            f"{x['name']}：{x['a']:.5g} → {x['b']:.5g}（{x['delta']:+.5g}）"
            for x in r["metrics"]
        ]
        lines += ["\n變更的設計條件"] + [
            f"{x['name']}：{x['a']} → {x['b']}" for x in r["changes"]
        ]
        return "\n".join(lines)

    def show_comparison(self):
        self.compare_text.config(state="normal")
        self.compare_text.delete("1.0", "end")
        self.compare_text.insert("1.0", self.comparison_string())
        self.compare_text.config(state="disabled")

    def export_compare(self):
        cases = getattr(self.main, "comparisons", {})
        if len(cases) < 2:
            return
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".txt", filetypes=[("比較紀錄", "*.txt")]
        )
        if path:
            atomic_text(path, self.comparison_string())

    def restore(self):
        path = filedialog.askopenfilename(
            parent=self.win,
            initialdir=app_data() / "Recovery",
            filetypes=[("復原快照", "*.json")],
        )
        if not path:
            return
        try:
            project = read_recovery(path)
            if not self.main.confirm_discard():
                return
            self.main.apply_workspace(project, None)
        except (ValueError, KeyError, TypeError, OSError) as e:
            messagebox.showerror("不能復原", str(e), parent=self.main.root)

    def may_close(self):
        return True

    def close(self, force=False):
        if self in self.main.children:
            self.main.children.remove(self)
        self.win.destroy()
