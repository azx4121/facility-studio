from .design_workflow import ahu_requirement_updates, ahu_utility_preview
from .tutorial_help import open_tutorial
from .workspace_view import apply_updates
from .project_store import save_project_file
from .errors import InputError
from .localized_tk import filedialog
import json
import copy
import uuid
from .localized_tk import messagebox
from .localized_tk import tk
from .localized_tk import ttk
from .ahu_engine import nm_calculate, nm_draft_inputs, nm_read_project, nm_validate
from .ahu_schema import NM_CONTROL_NOTES, NM_DEFAULTS, NM_FIELDS, NM_GROUPS
from .ahu_view import AHUView, NM_HAS_PLOT

if NM_HAS_PLOT:
    from .ahu_view import Figure, FigureCanvasTkAgg
from .reports import nm_report
from .localized_tk import LanguagePicker
from . import i18n
from .ui_common import app_icon, quality_style, quality_text
from .utils import atomic_text, project_hash
from .field_state import error_text
from .schema import VERSION


class AHUWindow(AHUView):

    def document(self):
        return dict(
            id=self.ahu_id,
            inputs=self.snapshot(),
            source_project_id=self.source_project_id,
        )

    def remember_undo(self):
        self.undo_inputs = (copy.deepcopy(self.snapshot()), self.source_project_id)

    def undo_changes(self):
        if not self.undo_inputs:
            return
        inputs, source = self.undo_inputs
        self.undo_inputs = None
        self.source_project_id = source
        self.suspended = True
        for k, v in inputs.items():
            self.vars[k].set(v)
        self.suspended = False
        self.changed()
        self.calculate()

    def make_independent(self):
        if not messagebox.askokcancel(
            "設為本案獨立設計",
            "保留目前所有單機設定，解除來源主案需求快照。\n後續回傳會明列為本案獨立設計，請自行確認服務範圍。",
            parent=self.win,
        ):
            return
        self.remember_undo()
        self.source_project_id = ""
        self.vars["linked_main_hash"].set("尚未連動")
        self.calculate()

    def focus_issue(self):
        key = self.bad_key
        if not key and self.result:
            key = next(
                (
                    x["field"]
                    for x in self.result["quality"]["items"]
                    if x["status"] != "通過" and x["field"] in self.widgets
                ),
                None,
            )
        if key in self.widgets:
            self.advanced.set(True)
            self.visibility()
            self.reveal(key)
            if not isinstance(NM_FIELDS[key]["limit"], list):
                self.widgets[key].configure(style="Invalid.TEntry")
        else:
            self.nb.select(2)

    def snapshot(self):
        return {k: v.get() for k, v in self.vars.items()}

    def changed(self, key=None):
        if self.suspended:
            return
        boundary_keys = {
            "target_mode",
            "p",
            "summer_t",
            "summer_rh",
            "winter_t",
            "winter_rh",
            "sa_t",
            "sa_rh",
            "flow",
            "flow_basis",
            "summer_sa_t",
            "summer_sa_rh",
            "winter_sa_t",
            "winter_sa_rh",
            "summer_flow",
            "winter_flow",
            "c1_in",
            "c1_out",
            "c2_in",
            "c2_out",
        }
        if key in boundary_keys and self.vars["linked_main_hash"].get() != "尚未連動":
            self.suspended = True
            self.vars["linked_main_hash"].set("尚未連動")
            self.source_project_id = ""
            self.suspended = False
        if self.job:
            self.win.after_cancel(self.job)
        self.last_good_result = self.result or getattr(self, "last_good_result", None)
        self.result = None
        self.export_button.configure(state="disabled")
        self.status.config(text="輸入變更，等待單機檢核…", style="Muted.TLabel")
        self.summary.config(text="上次有效結果｜待重算，不能匯出" if self.last_good_result else "等待目前輸入檢核")
        self.clear_output()
        self.visibility()
        self.job = self.win.after(700, self.calculate)
        if self.main_app:
            self.main_app.refresh_receipts()
            self.main_app.refresh_session_status()

    def target_preset(self, rh):
        self.remember_undo()
        self.suspended = True
        try:
            if self.vars["target_mode"].get() == "主案分季需求":
                for season in ["summer", "winter"]:
                    self.vars[season + "_sa_t"].set("22")
                    self.vars[season + "_sa_rh"].set(str(rh))
            else:
                self.vars["sa_t"].set("22")
                self.vars["sa_rh"].set(str(rh))
            self.vars["linked_main_hash"].set("尚未連動")
            self.source_project_id = ""
        finally:
            self.suspended = False
        self.changed()
        self.calculate()

    def import_climate(self):
        if not self.main_app:
            return
        self.remember_undo()
        self.suspended = True
        for key, source in [
            ("summer_t", "oa_t"),
            ("summer_rh", "oa_rh"),
            ("winter_t", "ow_t"),
            ("winter_rh", "ow_rh"),
            ("p", "atm_kpa"),
        ]:
            self.vars[key].set(self.main_app.variables[source].get())
        self.vars["linked_main_hash"].set("尚未連動")
        self.source_project_id = ""
        self.suspended = False
        self.changed()
        self.calculate()

    def ensure(self):
        if self.result is None or self.result["hash"] != project_hash(self.snapshot()):
            self.calculate()
        self.refresh_link_status()
        return self.result is not None

    def save(self):
        path = self.path or filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".json", initialfile="AHU_Project.json"
        )
        if not path:
            return
        try:
            inputs = nm_draft_inputs(self.snapshot())
            doc = {"kind": "ahu_stage", "schema_version": 4, "inputs": inputs}
            try:
                nm_validate(inputs)
            except InputError as error:
                if not messagebox.askyesno(
                    "儲存單機草稿",
                    "目前含無效輸入，只保存原始草稿，不能匯出設計結果。\n是否仍要儲存？\n"
                    + error_text(error, NM_FIELDS),
                    parent=self.win,
                ):
                    return
                doc.update(schema_version=5, draft=True)
            save_project_file(path, doc)
            self.path = path
            self.saved_hash = project_hash(inputs)
            if doc.get("draft"):
                self.status.config(text="已儲存單機草稿；請修正條件後重新計算。", style="Warn.TLabel")
        except (OSError, ValueError) as e:
            messagebox.showerror("儲存失敗", str(e), parent=self.win)

    def apply(self, inputs, *, allow_draft=False):
        inputs = nm_draft_inputs(inputs) if allow_draft else nm_validate(inputs)
        self.suspended = True
        try:
            for k, v in inputs.items():
                self.vars[k].set(v)
        finally:
            self.suspended = False
        self.changed()
        self.calculate()

    def load(self):
        path = filedialog.askopenfilename(
            parent=self.win, filetypes=[("單機專案", "*.json")]
        )
        if not path:
            return
        try:
            doc = nm_read_project(path)
        except (OSError, ValueError, KeyError, TypeError) as e:
            return messagebox.showerror("開啟失敗", str(e), parent=self.win)
        if project_hash(self.snapshot()) != self.saved_hash and (
            not messagebox.askyesno(
                "未儲存", "捨棄本單機未儲存修改並開啟？", parent=self.win
            )
        ):
            return
        self.remember_undo()
        self.path = path
        inputs = dict(doc["inputs"])
        inputs["linked_main_hash"] = "尚未連動"
        self.source_project_id = ""
        self.saved_hash = project_hash(inputs)
        self.result = None
        self.last_good_result = None
        self.apply(inputs, allow_draft=doc.get("draft") is True)

    def export(self):
        if not self.ensure():
            return
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".txt", initialfile="AHU_Review.txt"
        )
        if path:
            try:
                atomic_text(path, nm_report(self.result))
            except OSError as e:
                messagebox.showerror("匯出失敗", str(e), parent=self.win)

    def save_plot(self):
        if not NM_HAS_PLOT or not self.ensure():
            return
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".png", initialfile="AHU_Process.png"
        )
        if path:
            try:
                self.render()
                self.fig.savefig(path, dpi=180)
            except (OSError, ValueError) as e:
                messagebox.showerror("匯出失敗", str(e), parent=self.win)

    def _build_window(self, parent, main_app=None):
        self.main_app = main_app
        self.win = tk.Toplevel(parent)
        self.win.title("空調箱｜分段式單機送審校核")
        self.win.geometry("1160x850")
        self.win.minsize(850, 600)
        initial = (
            self._initial_document["inputs"] if self._initial_document else NM_DEFAULTS
        )
        self.vars = {k: tk.StringVar(value=v) for k, v in initial.items()}
        self.advanced = tk.BooleanVar(value=False)
        self.season = tk.StringVar(value="冬季")
        self.result = None
        self.rows = {}
        self.adoption_notes = {}
        self.boxes = []
        self.widgets = {}
        self.job = None
        self.suspended = True
        self.path = None
        self.saved_hash = project_hash(NM_DEFAULTS)
        top = ttk.Frame(self.win, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="空調箱｜分段需求反算", style="Title.TLabel").pack(
            side="left"
        )
        for text, cmd in [
            ("開啟", self.load),
            ("另存單機", self.save),
            ("重算", self.calculate),
            ("匯出校核書", self.export),
        ]:
            b = ttk.Button(top, text=text, command=cmd)
            b.pack(side="right", padx=3)
            if text == "匯出校核書":
                self.export_button = b
        language_bar = ttk.Frame(self.win, padding=(12, 2))
        language_bar.pack(fill="x")
        self.tutorial_button = ttk.Button(
            language_bar, text="新手教學", command=lambda: open_tutorial(self.win, "ahu")
        )
        self.tutorial_button.pack(side="left")
        self.language_picker = LanguagePicker(language_bar)
        self.language_picker.pack(side="right")
        ttk.Label(language_bar, text="Language / 語言").pack(side="right", padx=8)
        linkbar = ttk.Frame(self.win, padding=(12, 0))
        linkbar.pack(fill="x")
        if main_app:
            self.link_button = ttk.Button(
                linkbar, text="帶入主案分季送風需求", command=self.link_requirements
            )
            self.link_button.pack(side="left", padx=4)
            self.return_button = ttk.Button(
                linkbar, text="預覽回傳水量／額定電力", command=self.return_utilities
            )
            self.return_button.pack(side="left", padx=4)
            ttk.Button(
                linkbar, text="設為本案獨立設計", command=self.make_independent
            ).pack(side="left", padx=4)
        ttk.Button(linkbar, text="定位問題", command=self.focus_issue).pack(
            side="right"
        )
        self.link_info = ttk.Label(
            self.win, text="", wraplength=1000, style="Muted.TLabel", padding=(14, 4)
        )
        self.link_info.pack(fill="x")
        self.status = ttk.Label(
            self.win, text="", wraplength=1020, style="Muted.TLabel", padding=(14, 5)
        )
        self.status.pack(fill="x")
        self.nb = ttk.Notebook(self.win)
        self.nb.pack(fill="both", expand=True, padx=12, pady=8)
        self.input_frame, self.input_body, self.input_canvas = self.scroll_tab(
            "1 設計條件"
        )
        intro = ttk.Frame(self.input_body)
        intro.pack(fill="x", pady=8)
        ttk.Checkbutton(
            intro,
            text="顯示進階／廠商資料",
            variable=self.advanced,
            command=self.visibility,
        ).pack(side="left")
        if main_app:
            ttk.Button(intro, text="帶入主畫面外氣", command=self.import_climate).pack(
                side="left", padx=10
            )
        for rh in (50, 55):
            ttk.Button(
                intro,
                text=f"套用送風 22°C／{rh}%",
                command=lambda value=rh: self.target_preset(value),
            ).pack(side="left", padx=4)
        ttk.Button(intro, text="復原帶入", command=self.undo_changes).pack(
            side="left", padx=4
        )
        nav = ttk.Frame(self.input_body)
        nav.pack(fill="x", pady=4)
        for label, key in [
            ("夏季逐段設定", "summer_h1_mode"),
            ("冬季逐段設定", "winter_h1_mode"),
            ("H1/H2 熱源", "h1_source"),
            ("加濕設備", "humidifier"),
        ]:
            ttk.Button(nav, text=label, command=lambda k=key: self.reveal(k)).pack(
                side="left", padx=3
            )
        ttk.Label(
            self.input_body,
            text="單機指定風量校核：保留電熱器與熱水盤管，逐段反算需求，再比對既有容量。\n每段入口沿用前段出口；H1/H2 純加熱的 RH 自動計算。電極式蒸汽列於加濕設備，與直接電熱分開。",
            wraplength=980,
            style="Muted.TLabel",
        ).pack(fill="x", pady=8)
        self.adopted_summary = ttk.Label(
            self.input_body, text="", wraplength=950, style="Warn.TLabel"
        )
        self.adopted_summary.pack(fill="x", pady=6)
        for title, keys in NM_GROUPS:
            box = ttk.LabelFrame(self.input_body, text=title, padding=12)
            box.pack(fill="x", pady=8)
            self.boxes.append((box, keys))
            if "逐段出口" in title:
                ttk.Label(
                    box,
                    text="自動：H1 依加濕需求預熱；C1 按預冷目標（需加濕時旁通）；C2 依送風含濕比／溫度反算；H2 補足送風溫度並扣除風機熱。\n指定：直接檢核本段出口條件；旁通：出口沿用入口。入口由上一段連動，結果表另列各段實際採用的需求點。",
                    wraplength=880,
                    style="Muted.TLabel",
                ).pack(fill="x", pady=5)
            elif "獨立熱水" in title:
                ttk.Label(
                    box,
                    text="選擇熱水＋電熱可由熱回收優先分擔、電熱補足；回收水未上線或未填能力時，不會假定有可用熱量。",
                    wraplength=880,
                    style="Muted.TLabel",
                ).pack(fill="x", pady=5)
            for key in keys:
                f = NM_FIELDS[key]
                line = ttk.Frame(box)
                line.pack(fill="x", pady=4)
                line.columnconfigure(1, weight=1)
                self.rows[key] = line
                ttk.Label(line, text=f["label"], width=44).grid(
                    row=0, column=0, sticky="w"
                )
                if isinstance(f["limit"], list):
                    w = ttk.Combobox(
                        line,
                        textvariable=self.vars[key],
                        values=f["limit"],
                        state="readonly",
                        width=30,
                    )
                else:
                    w = ttk.Entry(line, textvariable=self.vars[key], width=30)
                w.grid(row=0, column=1, sticky="ew")
                ttk.Label(line, text=f["unit"], width=10).grid(row=0, column=2, padx=8)
                self.widgets[key] = w
                help_label = ttk.Label(
                    line, text="", wraplength=850, style="Muted.TLabel"
                )
                help_label.grid(row=1, column=0, columnspan=3, sticky="w")
                self.adoption_notes[key] = help_label
        self.output_frame, self.output_body, self.output_canvas = self.scroll_tab(
            "2 分段結果與線圖"
        )
        bar = ttk.Frame(self.output_body)
        bar.pack(fill="x", pady=8)
        cb = ttk.Combobox(
            bar,
            textvariable=self.season,
            values=["夏季", "冬季"],
            state="readonly",
            width=8,
        )
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.render())
        ttk.Button(bar, text="另存線圖 PNG", command=self.save_plot).pack(side="right")
        ttk.Label(
            bar, text="下列為需求狀態；容量未達時不代表實機出風", style="Muted.TLabel"
        ).pack(side="left", padx=12)
        ttk.Label(
            self.output_body,
            text="水洗近似等焓：降低乾球、增加水氣；空氣側 0 kW 不代表沒有加濕。",
            style="Muted.TLabel",
        ).pack(fill="x", pady=3)
        self.summary = ttk.Label(
            self.output_body, text="", wraplength=960, style="Good.TLabel"
        )
        self.summary.pack(fill="x", pady=8)
        self.table = ttk.Treeview(
            self.output_body,
            columns=("name", "tin", "rhin", "tout", "rhout", "kw"),
            show="headings",
            height=11,
        )
        for key, label, width in [
            ("name", "段落", 250),
            ("tin", "進風 °C", 115),
            ("rhin", "進風 %RH", 115),
            ("tout", "出風 °C", 115),
            ("rhout", "出風 %RH", 115),
            ("kw", "空氣側 kW（＋熱／−冷）", 205),
        ]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width, anchor="w" if key == "name" else "e")
        self.table.pack(fill="x")
        scroll = ttk.Scrollbar(
            self.output_body, orient="horizontal", command=self.table.xview
        )
        scroll.pack(fill="x")
        self.table.configure(xscrollcommand=scroll.set)
        if NM_HAS_PLOT:
            self.fig = Figure(figsize=(9, 4.5), dpi=100)
            self.ax = self.fig.add_subplot(111)
            self.plot = FigureCanvasTkAgg(self.fig, master=self.output_body)
            self.plot.get_tk_widget().configure(height=380)
            self.plot.get_tk_widget().pack(fill="x", pady=10)
        else:
            ttk.Label(
                self.output_body, text="未安裝 matplotlib；表格與校核書仍可使用。"
            ).pack(pady=10)
        textpage = ttk.Frame(self.nb, padding=10)
        self.nb.add(textpage, text="3 校核書")
        self.text = tk.Text(
            textpage,
            wrap="word",
            font=("TkDefaultFont", 11),
            padx=12,
            pady=12,
            state="disabled",
        )
        self.text.pack(side="left", fill="both", expand=True)
        sc = ttk.Scrollbar(textpage, command=self.text.yview)
        sc.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sc.set)
        note_frame, note_body, _ = self.scroll_tab("4 控制／需補資料")
        self.control_notes = ttk.Label(
            note_body, text=NM_CONTROL_NOTES, wraplength=1000, justify="left"
        )
        self.control_notes.pack(fill="x", pady=10)
        ttk.Label(
            note_body,
            text="需補資料：風量的參考狀態、送風與室內目標區別、H1/H2 內部相對位置、C1/C2 正本選型、濕膜有效度與面積／淋水密度、擋水器性能、噴頭壓力、水盤尺寸、熱回收同工況能力、各段終阻力、風機曲線與實際入室熱。\n所有原廠性能資料應以本專案同工況選型文件確認。",
            wraplength=1000,
            style="Muted.TLabel",
        ).pack(fill="x", pady=15)
        for key, var in self.vars.items():
            var.trace_add("write", lambda *a, k=key: self.changed(k))
        self.win.bind("<MouseWheel>", self.wheel)
        self.win.bind("<Button-4>", self.wheel)
        self.win.bind("<Button-5>", self.wheel)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Control-s>", lambda e: self.save())
        self.win.bind("<F5>", lambda e: self.calculate())
        self.suspended = False
        self.visibility()
        self.calculate()

    def __init__(self, parent, main_app=None, document=None):
        self.project_bound = True
        self.ahu_id = document["id"] if document else uuid.uuid4().hex
        self.owner_project_id = main_app.project_id if main_app else ""
        self.source_project_id = document["source_project_id"] if document else ""
        self._initial_document = document
        self.undo_inputs = None
        self.bad_key = None
        self._build_window(parent, main_app)
        self.win.title("分段空調箱設計｜V" + VERSION)
        app_icon(self.win)
        i18n.subscribe(self)
        if main_app:
            main_app.children.append(self)
            main_app.refresh_session_status()
        if document:
            self.saved_hash = project_hash(self.snapshot())
        self.refresh_link_status()

    def refresh_language(self):
        if self.win.winfo_exists() and self.result:
            self.set_text(nm_report(self.result))
            self.render()

    def _calculate_stage_project(self):
        if self.job:
            self.win.after_cancel(self.job)
            self.job = None
        try:
            self.bad_key = None
            r = nm_calculate(self.snapshot())
        except (InputError, ValueError, KeyError, TypeError) as e:
            self.result = None
            self.clear_output()
            self.bad_key = getattr(e, "field_name", None)
            self.status.config(text=error_text(e, NM_FIELDS), style="Error.TLabel")
            self.summary.config(text="條件未成立：" + error_text(e, NM_FIELDS))
            self.export_button.configure(state="disabled")
            return
        self.result = r
        self.last_good_result = r
        self.stale_plot_label = None
        failed = [
            f"{season} {k}"
            for season in ["summer", "winter"]
            for k, v in r[season]["checks"].items()
            if not v
        ]
        self.status.config(
            text=(
                "有未達額定條件，請查看校核書；列出的狀態是需求，不是實機性能。"
                if failed
                else "分段平衡及額定初估通過；仍待廠商性能資料核對。"
            ),
            style="Error.TLabel" if failed else "Good.TLabel",
        )
        self.export_button.configure(state="normal")
        self.set_text(nm_report(r))
        self.render()

    def calculate(self):
        self._calculate_stage_project()
        self.refresh_link_status()

    def refresh_link_status(self):
        linked = self.vars["linked_main_hash"].get()
        state = "獨立送風條件；未宣告主案連動，尚未帶入快照"
        valid_owner = (
            not self.main_app or self.owner_project_id == self.main_app.project_id
        )
        fresh = linked == "尚未連動"
        if self.main_app:
            project_name = self.main_app.variables["project_name"].get()
            self.win.title("空調箱｜" + project_name + " / " + self.vars["name"].get())
            if not valid_owner:
                state = "所屬主案不同，回傳已停止"
            elif linked != "尚未連動":
                fresh = (
                    self.source_project_id == self.main_app.project_id
                    and linked == self.main_app.boundary_hash()
                )
                state = (
                    "與目前主案工程邊界一致"
                    if fresh
                    else "來源快照已過期，請重新帶入主案需求"
                )
            supported = self.main_app.variables["sys_type"].get().startswith("MAU")
            self.link_button.configure(
                state="normal" if valid_owner and supported else "disabled"
            )
            self.return_button.configure(
                state="normal" if valid_owner and fresh and self.result else "disabled"
            )
            suffix = "" if supported else "；混風主案不能直接當全外氣箱，請獨立指定入口"
            self.link_info.config(
                text="所屬主案：" + project_name + "｜" + state + suffix
            )
        if self.result:
            self.result["link_status"] = state
            self.status.config(
                text=quality_text(self.result["quality"]),
                style=quality_style(self.result["quality"]),
            )
            self.set_text(nm_report(self.result))
        if self.main_app:
            self.main_app.refresh_receipts()

    def may_close(self):
        if self.main_app:
            return True  # The draft is retained in the whole-project session.
        if project_hash(self.snapshot()) == self.saved_hash:
            return True
        answer = messagebox.askyesnocancel(
            "未儲存空調箱",
            "關閉前儲存分段空調箱？\n是：儲存；否：捨棄；取消：返回。",
            parent=self.win,
        )
        if answer is None:
            return False
        if answer:
            self.save()
            return project_hash(self.snapshot()) == self.saved_hash
        return True

    def _legacy_close(self):
        if project_hash(self.snapshot()) != self.saved_hash and (
            not messagebox.askyesno(
                "未儲存", "關閉並捨棄本單機未儲存修改？", parent=self.win
            )
        ):
            return
        if self.job:
            self.win.after_cancel(self.job)
        self.win.destroy()

    def close(self, force=False):
        if not force and (not self.may_close()):
            return
        if self.job:
            self.win.after_cancel(self.job)
        if self.main_app and self.owner_project_id == self.main_app.project_id:
            self.main_app.ahu_documents[self.ahu_id] = self.document()
        if self.main_app and self in self.main_app.children:
            self.main_app.children.remove(self)
        self.win.destroy()
        if self.main_app:
            self.main_app.refresh_session_status()

    def link_requirements(self):
        if not self.main_app or self.owner_project_id != self.main_app.project_id:
            return messagebox.showerror(
                "案件不同", "此單機不屬於目前主案，不能直接帶入。", parent=self.win
            )
        if not self.main_app.ensure_result():
            return
        try:
            updates = ahu_requirement_updates(self.main_app.result)
            from tkinter import simpledialog
            fraction = simpledialog.askfloat(i18n.translate("本台服務比例"), i18n.translate("若多台分攤同一主案，請填本台分攤的設計風量百分比。\n100% 代表單台負責整案；方案比較請勿把各方案同時回傳。"), initialvalue=100.0, minvalue=1.0, maxvalue=100.0, parent=self.win)
            if fraction is None:
                return
            for season in ("summer", "winter"):
                updates[season + "_flow"] = format(float(updates[season + "_flow"]) * fraction / 100, ".15g")
            if not messagebox.askokcancel(
                "主案連動",
                "來源主案："
                + self.main_app.variables["project_name"].get()
                + "\n帶入夏冬入口、送風目標、乾空氣流率與冰水供回水。\n逐段指定目標與設備額定保留，可能需要調整才能符合新的送風需求。",
                parent=self.win,
            ):
                return
            self.remember_undo()
            values = self.snapshot()
            values.update(updates)
            self.source_project_id = self.main_app.project_id
            self.apply(values)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("無法帶入", str(exc), parent=self.win)

    def return_utilities(self):
        if not self.ensure():
            return
        if self.owner_project_id != self.main_app.project_id:
            return messagebox.showerror(
                "案件不同", "此單機屬於另一主案，回傳已停止。", parent=self.win
            )
        linked = self.vars["linked_main_hash"].get()
        if linked != "尚未連動" and (
            self.source_project_id != self.main_app.project_id
            or linked != self.main_app.boundary_hash()
        ):
            return messagebox.showerror(
                "來源快照已過期",
                "請先重新帶入目前主案需求；若要使用獨立單機設計，請明確選擇「設為本案獨立設計」。",
                parent=self.win,
            )
        try:
            from .contributions import ahu_contribution
            entry = ahu_contribution(self.result, self.ahu_id, self.main_app.snapshot()["inputs"])
            if self.main_app.apply_contribution(entry, self.win):
                self.main_app.add_receipt(self, self.main_app.demand_ledger["last_updates"])
                self.main_app.recalculate()
        except (ValueError, KeyError) as exc:
            messagebox.showerror("無法回傳", str(exc), parent=self.win)
