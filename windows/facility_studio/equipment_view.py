"""Equipment schedules: export, import, inspect and report."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .localized_tk import tk
from .localized_tk import ttk, filedialog, messagebox
from .schema import VERSION
from .equipment_io import (
    export_template,
    export_csv_templates,
    load_equipment,
    save_equipment_result,
)
from .equipment_analysis import analyze_equipment, equipment_report, group_metrics
from .equipment_schema import SYSTEMS
from .ui_common import app_icon
from .localized_tk import LanguagePicker
from . import i18n
from .utils import atomic_text


class EquipmentWindow:
    def refresh_language(self):
        if self.win.winfo_exists() and self.result:
            self.show_group()

    def __init__(self, parent, family="Microsoft JhengHei", main_app=None):
        self.main_app = main_app
        self.parent = parent
        self.owner_project_id = main_app.project_id if main_app else None
        self.project_bound = bool(main_app)
        if main_app:
            main_app.children.append(self)
        self.win = tk.Toplevel(parent)
        self.win.title("設備表匯入與需求分析 V" + VERSION)
        self.win.geometry("1150x800")
        self.win.minsize(830, 560)
        app_icon(self.win)
        i18n.subscribe(self)
        self.result = self.future = self.poll_id = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.win.columnconfigure(0, weight=1)
        self.win.rowconfigure(3, weight=1)
        header = ttk.Frame(self.win, padding=(18, 14))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="設備表 → 需求彙總", style="Simple.Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="匯出範本，填實際設備，再匯入檢查。各系統與供應群組會分開計算。",
            style="Simple.Muted.TLabel",
            wraplength=780,
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.language_picker = LanguagePicker(header)
        self.language_picker.grid(row=0, column=1, padx=12, sticky="e")
        header.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(self.win, padding=(18, 3))
        toolbar.grid(row=1, column=0, sticky="ew")
        ttk.Button(toolbar, text="1 匯出Excel範本", command=self.export_template).grid(
            row=0, column=0, padx=(0, 5), pady=4
        )
        self.import_button = ttk.Button(
            toolbar,
            text="2 匯入設備表",
            command=self.pick_import,
            style="Simple.Primary.TButton",
        )
        self.import_button.grid(row=0, column=1, padx=5, pady=4)
        ttk.Button(toolbar, text="另存CSV範本", command=self.export_csv).grid(
            row=0, column=2, padx=5, pady=4
        )
        ttk.Label(toolbar, text="CSV系統：").grid(row=1, column=0, sticky="e")
        self.csv_system = tk.StringVar(self.win, "電力")
        ttk.Combobox(
            toolbar,
            textvariable=self.csv_system,
            values=SYSTEMS,
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(
            toolbar,
            text="Excel一次讀全部系統；CSV依左方選擇。",
            style="Simple.Muted.TLabel",
        ).grid(row=1, column=2, sticky="w")
        self.status = ttk.Label(
            self.win,
            text="範例啟用欄為0；實際設備設為1。每張表最多10,000筆。",
            style="Simple.Muted.TLabel",
            wraplength=1000,
        )
        self.status.grid(row=2, column=0, sticky="ew", padx=18, pady=10)
        split = self.split = ttk.PanedWindow(self.win, orient="vertical")
        self.pane_job = None
        self.pane_size = None
        split.bind("<Configure>", self.layout_panes, add="+")
        split.grid(row=3, column=0, sticky="nsew", padx=18, pady=5)
        summary, details = ttk.Frame(split), ttk.Frame(split)
        split.add(summary, weight=2)
        split.add(details, weight=3)
        summary.rowconfigure(1, weight=1)
        summary.columnconfigure(0, weight=1)
        self.summary = ttk.Label(
            summary,
            text="需求彙總會顯示在這裡",
            style="Simple.Header.TLabel",
            wraplength=950,
        )
        self.summary.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        columns = ("system", "group", "demand", "condition", "size")
        self.tree = ttk.Treeview(
            summary, columns=columns, show="headings", height=8, selectmode="browse"
        )
        for key, label, width in zip(
            columns,
            ("系統", "供應群組／供電", "同時需求", "電流／容量／實際量", "尺寸候選"),
            (90, 160, 200, 225, 250),
        ):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=70, stretch=key != "system")
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(summary, orient="vertical", command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        hscroll = ttk.Scrollbar(summary, orient="horizontal", command=self.tree.xview)
        hscroll.grid(row=2, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=hscroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.show_group)
        details.rowconfigure(1, weight=1)
        details.columnconfigure(0, weight=1)
        ttk.Label(
            details,
            text="分組條件、公式與設備明細（點選上方一列查看）",
            style="Simple.Header.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(10, 6))
        self.details = tk.Text(
            details,
            wrap="word",
            font=(family, 10),
            bg="white",
            fg="#18334d",
            relief="flat",
            padx=12,
            pady=10,
            state="disabled",
        )
        self.details.grid(row=1, column=0, sticky="nsew")
        dscroll = ttk.Scrollbar(details, orient="vertical", command=self.details.yview)
        dscroll.grid(row=1, column=1, sticky="ns")
        self.details.configure(yscrollcommand=dscroll.set)
        footer = ttk.Frame(self.win, padding=(18, 10))
        footer.grid(row=4, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(
            footer,
            text="插座數僅統計點位；支路按單台額定負載。",
            style="Simple.Muted.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.report_button = ttk.Button(
            footer, text="匯出分析TXT", command=self.export_report, state="disabled"
        )
        self.report_button.grid(row=0, column=1, padx=3)
        self.json_button = ttk.Button(
            footer, text="匯出明細JSON", command=self.export_json, state="disabled"
        )
        self.json_button.grid(row=0, column=2, padx=3)
        transfer = ttk.Frame(footer)
        transfer.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Label(transfer, text="目的盤／特氣路：").pack(side="left")
        self.target = tk.StringVar(value="UP")
        self.target_selector = ttk.Combobox(transfer, textvariable=self.target, values=("UP", "NP"), state="readonly", width=6)
        self.target_selector.pack(side="left", padx=6)
        from .tutorial_help import open_tutorial
        ttk.Button(transfer, text="本工具教學", command=lambda: open_tutorial(self.win, "equipment")).pack(side="right")
        self.transfer_button = ttk.Button(transfer, text="3 預覽帶入主案", command=self.transfer_group, state="disabled")
        self.transfer_button.pack(side="left", padx=6)
        ttk.Label(transfer, text="先選上方一個供應群組；分析本身不會修改主案。", style="Simple.Muted.TLabel").pack(side="left")
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Configure>", self.resize, add="+")

    def resize(self, event):
        if event.widget is self.win:
            width = max(700, self.win.winfo_width() - 45)
            self.status.configure(wraplength=width)
            self.summary.configure(wraplength=width)

    def layout_panes(self, event=None):
        size = self.split.winfo_width(), self.split.winfo_height()
        if size == self.pane_size:
            return
        self.pane_size = size
        if self.pane_job:
            self.win.after_cancel(self.pane_job)
        self.pane_job = self.win.after_idle(self.position_panes)

    def position_panes(self):
        self.pane_job = None
        height = self.split.winfo_height()
        if height > 10:
            position = (
                max(120, min(height - 100, height // 2))
                if height >= 220
                else height // 2
            )
            self.split.sashpos(0, position)

    def set_details(self, text):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def invalidate(self):
        self.result = None
        self.tree.delete(*self.tree.get_children())
        self.summary.configure(text="等待新的設備表完成檢查")
        self.set_details("")
        self.report_button.state(["disabled"])
        self.json_button.state(["disabled"])
        self.transfer_button.state(["disabled"])

    def export_template(self, path=None):
        path = path or filedialog.asksaveasfilename(
            parent=self.win,
            defaultextension=".xlsx",
            initialfile="Equipment_Template.xlsx",
            filetypes=[("Excel範本", "*.xlsx")],
        )
        if not path:
            return False
        try:
            export_template(path)
            self.status.configure(
                text="已匯出範本。保留欄名，填實際數值；要納入的列設為啟用1。",
                style="Simple.Good.TLabel",
            )
            return True
        except (OSError, ValueError) as error:
            self.status.configure(text=str(error), style="Simple.Error.TLabel")
            return False

    def export_csv(self, path=None):
        path = path or filedialog.askdirectory(
            parent=self.win, title="選CSV範本存放資料夾"
        )
        if not path:
            return False
        try:
            export_csv_templates(path)
            self.status.configure(
                text="已匯出七個CSV範本。匯入前選CSV對應系統。",
                style="Simple.Good.TLabel",
            )
            return True
        except (OSError, ValueError) as error:
            self.status.configure(text=str(error), style="Simple.Error.TLabel")
            return False

    def pick_import(self):
        path = filedialog.askopenfilename(
            parent=self.win,
            title="匯入設備數據",
            filetypes=[
                ("設備表", "*.xlsx *.csv"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
            ],
        )
        if path:
            self.start_import(path)

    def start_import(self, path):
        if self.future is not None:
            return False
        self.invalidate()
        self.import_button.state(["disabled"])
        self.status.configure(
            text=f"正在檢查 {Path(path).name}…", style="Simple.Muted.TLabel"
        )
        system = self.csv_system.get()
        self.future = self.executor.submit(
            lambda: analyze_equipment(load_equipment(path, system))
        )
        self.poll_id = self.win.after(80, self.poll_import)
        return True

    def poll_import(self):
        self.poll_id = None
        if self.future is None:
            return
        if not self.future.done():
            self.poll_id = self.win.after(80, self.poll_import)
            return
        future, self.future = self.future, None
        self.import_button.state(["!disabled"])
        try:
            self.display_result(future.result())
        except Exception as error:
            self.invalidate()
            self.status.configure(
                text="匯入未完成，請修正下方列別問題。", style="Simple.Error.TLabel"
            )
            self.set_details(str(error))

    def display_result(self, result):
        self.invalidate()
        self.result = result
        for index, group in enumerate(result["groups"]):
            name = group["group"]
            if group["system"] == "電力":
                name += f"／{group['phases']}相{group['voltage']:g}V"
            if group["system"] == "EXHAUST":
                name += "／" + group["exhaust_type"]
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(group["system"], name, *group_metrics(group)),
            )
        totals = result["totals"]
        self.summary.configure(
            text=f"{result['active_records']}筆設備，{len(result['groups'])}個分組｜連接{totals['connected_kw']:,.2f}kW，同時{totals['demand_kw']:,.2f}kW｜插座{totals['sockets']}個"
        )
        self.status.configure(
            text=f"已分析 {result['source_name']}；略過{result['skipped_records']}筆未啟用列。百分比正規化 {sum(len(row.get('normalizations', {})) for row in result['rows'])} 欄；採用值已列明細。分析尚未帶入主案。",
            style="Simple.Good.TLabel",
        )
        self.report_button.state(["!disabled"])
        self.json_button.state(["!disabled"])
        self.set_details(equipment_report(result))

    def show_group(self, event=None):
        selection = self.tree.selection()
        if not selection or self.result is None:
            return
        group = self.result["groups"][int(selection[0])]
        if group["system"] == "電力":
            choices = ("UP", "NP")
        elif group["system"] in ("CDA", "N2"):
            choices = ("1", "2", "3")
        else:
            choices = (group["system"],)
        self.target_selector.config(values=choices)
        if self.target.get() not in choices:
            self.target.set(choices[0])
        self.transfer_button.state(["!disabled"])
        rows = [
            r
            for r in self.result["rows"]
            if r["system"] == group["system"] and r["group"] == group["group"]
        ]
        if group["system"] == "電力":
            rows = [
                r
                for r in rows
                if (r["phases"], r["voltage"]) == (group["phases"], group["voltage"])
            ]
        elif group["system"] == "EXHAUST":
            rows = [r for r in rows if r["exhaust_type"] == group["exhaust_type"]]
        self.set_details(equipment_report(dict(self.result, groups=[group], rows=rows)))

    def transfer_group(self):
        if self.result is None or not self.tree.selection():
            return
        try:
            if self.main_app is None:
                if not messagebox.askokcancel("建立目的主案", "將開啟新的完整工程工作台；接著會預覽目的欄位，確認後才帶入。", parent=self.win):
                    return
                from .desktop import DesktopApp
                self.main_app = DesktopApp(tk.Toplevel(self.parent))
                self.owner_project_id = self.main_app.project_id
            if not self.main_app.root.winfo_exists() or self.owner_project_id != self.main_app.project_id:
                raise ValueError("目的主案已關閉或切換；請由目前主案重新開啟設備表匯入。")
            from .contributions import equipment_contribution
            group = self.result["groups"][int(self.tree.selection()[0])]
            entry = equipment_contribution(self.result, group, self.main_app.snapshot()["inputs"], self.target.get())
            if self.main_app.apply_contribution(entry, self.win):
                self.status.config(text="選取群組已帶入；同群組重匯會更新原來源。請在主案「需求彙整」確認採用範圍。", style="Simple.Good.TLabel")
        except (ValueError, KeyError, TypeError) as exc:
            messagebox.showerror("尚未帶入", str(exc), parent=self.win)

    def export_report(self, path=None):
        if self.result is None:
            return False
        path = path or filedialog.asksaveasfilename(
            parent=self.win,
            defaultextension=".txt",
            initialfile="Equipment_Demand.txt",
            filetypes=[("分析報告", "*.txt")],
        )
        if not path:
            return False
        try:
            atomic_text(path, equipment_report(self.result))
            self.status.configure(
                text="已匯出全部分組與設備明細。", style="Simple.Good.TLabel"
            )
            return True
        except OSError as error:
            self.status.configure(text=str(error), style="Simple.Error.TLabel")
            return False

    def export_json(self, path=None):
        if self.result is None:
            return False
        path = path or filedialog.asksaveasfilename(
            parent=self.win,
            defaultextension=".json",
            initialfile="Equipment_Demand.json",
            filetypes=[("分析明細", "*.json")],
        )
        if not path:
            return False
        try:
            save_equipment_result(path, self.result)
            self.status.configure(
                text="已匯出全部數值明細。", style="Simple.Good.TLabel"
            )
            return True
        except OSError as error:
            self.status.configure(text=str(error), style="Simple.Error.TLabel")
            return False

    def close(self, force=False):
        if self.main_app and self in self.main_app.children:
            self.main_app.children.remove(self)
        if self.pane_job:
            self.win.after_cancel(self.pane_job)
        if self.poll_id:
            self.win.after_cancel(self.poll_id)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.win.destroy()
