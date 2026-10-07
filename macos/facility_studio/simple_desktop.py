"""Independent short forms are the default entry; the full workbench is optional."""

from .localized_tk import tk
from tkinter import font
from .localized_tk import ttk, filedialog, messagebox

from .errors import ValidationError
from .main_view import ScrollPage
from .quick_tools import UNITS, UNIT_HELP
from .air_chart import AirChart
from .simple_engines import calculate_tool, FLOW_FACTORS, GAS_FLOW_FACTORS
from .simple_engines import AIR_PRESSURE_FACTORS, GAS_PRESSURE_FACTORS
from .simple_reports import presentation, tool_report
from .simple_schema import TOOLS, active_field, adopted_summary, defaults
from .ui_common import app_icon
from .localized_tk import LanguagePicker
from .utils import atomic_text, number


class SimplePage(ScrollPage):
    def __init__(self, parent, tool, app):
        super().__init__(parent)
        self.tool, self.app = tool, app
        self.pending = None
        self.suspended = True
        self.result = None
        self.variables = {
            key: tk.StringVar(self, value) for key, value in defaults(tool).items()
        }
        self.previous = {key: var.get() for key, var in self.variables.items()}
        self.widgets, self.rows, self.labels, self.hints = {}, {}, {}, {}
        self.minimum_body_width = 520
        self.horizontal = self.grid_slaves(row=1, column=0)[0]
        self.canvas.configure(xscrollcommand=self.horizontal_scroll)
        self.advanced = tk.BooleanVar(self, False)
        self.body.columnconfigure(0, weight=1)
        self.body.columnconfigure(1, weight=1)
        ttk.Label(
            self.body, text=TOOLS[tool]["title"], style="Simple.Title.TLabel"
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.subtitle = ttk.Label(
            self.body,
            text=TOOLS[tool]["subtitle"],
            style="Simple.Muted.TLabel",
            wraplength=710,
        )
        self.subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 16))
        self.form = ttk.Frame(self.body, style="Simple.Card.TFrame", padding=16)
        self.form.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.form.columnconfigure(1, weight=1)
        if tool == "air":
            self.form.columnconfigure(0, weight=1)
        for index, spec in enumerate(TOOLS[tool]["fields"]):
            key = spec["key"]
            row = ttk.Frame(self.form, style="Simple.Card.TFrame")
            row.grid(row=index, column=0, columnspan=2, sticky="ew", pady=5)
            row.columnconfigure(1, weight=1)
            self.labels[key] = ttk.Label(
                row,
                text=spec["label"],
                style="Simple.Card.TLabel",
                width=23,
                wraplength=185,
            )
            self.labels[key].grid(row=0, column=0, sticky="w")
            if spec["checkbox"]:
                widget = ttk.Checkbutton(
                    row,
                    variable=self.variables[key],
                    onvalue="1",
                    offvalue="0",
                    text="啟用此路徑檢查",
                )
            elif spec["options"]:
                widget = ttk.Combobox(
                    row,
                    textvariable=self.variables[key],
                    values=spec["options"],
                    state="readonly",
                    width=22,
                )
            else:
                widget = ttk.Entry(row, textvariable=self.variables[key], width=18)
            widget.grid(row=0, column=1, sticky="ew", padx=(5, 8))
            self.widgets[key] = widget
            if spec["units"]:
                unit_key, options = spec["units"]
                unit = ttk.Combobox(
                    row,
                    textvariable=self.variables[unit_key],
                    values=options,
                    state="readonly",
                    width=12,
                )
                unit.grid(row=0, column=2, sticky="e")
                self.widgets[unit_key] = unit
            if spec["help"]:
                hint = ttk.Label(
                    row, text=spec["help"], style="Simple.Hint.TLabel", wraplength=440
                )
                hint.grid(
                    row=1, column=1, columnspan=2, sticky="w", padx=5, pady=(2, 0)
                )
                self.hints[key] = hint
            self.rows[key] = row
            if tool == "air" and key in ("temperature", "rh"):
                row.grid_configure(
                    row=0, column=0 if key == "temperature" else 1, columnspan=1, padx=5
                )
            elif tool == "air":
                row.grid_configure(row=1)
        self.assumptions = ttk.Label(
            self.body, style="Simple.Muted.TLabel", wraplength=710
        )
        self.assumptions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 6))
        controls = ttk.Frame(self.body)
        controls.grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)
        if any(row["advanced"] for row in TOOLS[tool]["fields"]):
            ttk.Checkbutton(
                controls,
                text="調整預設值／進階條件",
                variable=self.advanced,
                command=self.update_visibility,
            ).pack(side="left")
        ttk.Button(controls, text="恢復本工具預設", command=self.reset).pack(
            side="right"
        )
        self.status = ttk.Label(self.body, style="Simple.Muted.TLabel", wraplength=710)
        self.status.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(3, 10))
        self.result_box = ttk.Frame(self.body, style="Simple.Card.TFrame", padding=16)
        self.result_box.grid(row=6, column=0, columnspan=2, sticky="ew")
        self.cards = []
        self.card_boxes = []
        for index in range(3):
            box = ttk.Frame(self.result_box, style="Simple.Card.TFrame")
            box.grid(row=0, column=index, sticky="nsew", padx=6)
            self.card_boxes.append(box)
            self.result_box.columnconfigure(index, weight=1)
            title = ttk.Label(box, style="Simple.Hint.TLabel")
            value = ttk.Label(box, style="Simple.Value.TLabel", wraplength=230)
            title.pack(anchor="w")
            value.pack(anchor="w", pady=5)
            self.cards.append((title, value))
        self.details = ttk.Label(
            self.body, style="Simple.Normal.TLabel", wraplength=710
        )
        self.details.grid(row=7, column=0, columnspan=2, sticky="ew", pady=12)
        self.formula = ttk.Label(self.body, style="Simple.Muted.TLabel", wraplength=710)
        self.formula.grid(row=8, column=0, columnspan=2, sticky="ew", pady=4)
        self.note = ttk.Label(self.body, style="Simple.Muted.TLabel", wraplength=710)
        self.note.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(4, 16))
        self.air_chart = None
        if tool == "air":
            self.air_chart = AirChart(self.body, app.family)
            self.air_chart.grid(row=6, column=0, columnspan=2, sticky="ew", pady=12)
            self.result_box.grid_configure(row=7)
            self.details.grid_configure(row=8)
            self.formula.grid_configure(row=9)
            self.note.grid_configure(row=10)
        for key, variable in self.variables.items():
            variable.trace_add("write", lambda *args, k=key: self.changed(k))
        self.suspended = False
        self.update_visibility()
        self.calculate()

    def data(self):
        return {key: variable.get() for key, variable in self.variables.items()}

    def horizontal_scroll(self, first, last):
        self.horizontal.set(first, last)
        if float(first) <= 1e-8 and float(last) >= 1 - 1e-8:
            self.horizontal.grid_remove()
        else:
            self.horizontal.grid()

    def clear(self, text="輸入已變更，等待計算…"):
        self.result = None
        if self.air_chart is not None:
            self.air_chart.clear()
        for title, value in self.cards:
            title.config(text="")
            value.config(text="—")
        self.details.config(text="")
        self.formula.config(text="")
        self.note.config(text="")
        self.status.config(text=text, style="Simple.Muted.TLabel")
        if self.app.current == self.tool:
            self.app.sync_actions()

    def changed(self, key):
        if self.suspended:
            return
        self.suspended = True
        try:
            rules = {
                "duct": {
                    "flow_unit": ("flow", FLOW_FACTORS),
                    "pressure_unit": ("pressure", AIR_PRESSURE_FACTORS),
                },
                "gas": {
                    "flow_unit": ("flow", GAS_FLOW_FACTORS),
                    "pressure_unit": ("pressure", GAS_PRESSURE_FACTORS),
                },
                "water": {
                    "flow_unit": ("flow", UNITS["水量"]),
                    "power_unit": ("power", UNITS["冷熱功率"]),
                },
            }
            if key in rules.get(self.tool, {}):
                value_key, factors = rules[self.tool][key]
                old, new = self.previous[key], self.variables[key].get()
                value = number(self.variables[value_key].get(), value_key, 0)
                self.variables[value_key].set(
                    format(value * factors[old] / factors[new], ".15g")
                )
            if self.tool == "gas" and key == "gas":
                reference = {"CDA": 15.0, "N2": 12.0, "Ar": 12.0}
                try:
                    if (
                        float(self.variables["velocity"].get())
                        == reference[self.previous["gas"]]
                    ):
                        self.variables["velocity"].set(
                            str(reference[self.variables[key].get()])
                        )
                except ValueError:
                    pass
            if self.tool == "units" and key == "category":
                options = tuple(UNITS[self.variables[key].get()])
                self.widgets["unit"].configure(values=options)
                if self.variables["unit"].get() not in options:
                    self.variables["unit"].set(options[0])
            if self.tool == "lighting" and key == "area_mode":
                old, new = self.previous[key], self.variables[key].get()
                source = self.previous
                height = (
                    number(source["height"], "height", 0.1, 100)
                    if "體積 m³" in (old, new)
                    else 1
                )
                if old == "長×寬":
                    area = number(source["length"], "length", 0.01) * number(
                        source["width"], "width", 0.01
                    )
                else:
                    area = number(source["area"], "area", 0.01) * (
                        400 / 121 if old == "面積 坪" else 1
                    )
                    if old == "體積 m³":
                        area /= height
                if new == "長×寬":
                    width = number(source["width"], "width", 0.01)
                    self.variables["length"].set(format(area / width, ".15g"))
                else:
                    value = area * (
                        height
                        if new == "體積 m³"
                        else 121 / 400 if new == "面積 坪" else 1
                    )
                    self.variables["area"].set(format(value, ".15g"))
            self.previous = self.data()
        except (ValueError, KeyError):
            self.variables[key].set(self.previous[key])
        finally:
            self.suspended = False
        if self.pending:
            self.after_cancel(self.pending)
        self.clear()
        self.update_visibility()
        self.pending = self.after(280, self.calculate)

    def update_visibility(self):
        data = self.data()
        for spec in TOOLS[self.tool]["fields"]:
            visible = active_field(self.tool, spec["key"], data) and (
                not spec["advanced"] or self.advanced.get()
            )
            if visible:
                self.rows[spec["key"]].grid()
            else:
                self.rows[spec["key"]].grid_remove()
        if self.tool == "lighting":
            label = {
                "面積 m²": "地板照明面積（m²）",
                "面積 坪": "地板照明面積（坪）",
                "體積 m³": "空間體積（m³，立方公尺）",
                "長×寬": "空間面積",
            }[data["area_mode"]]
            self.labels["area"].configure(text=label)
            self.hints["area"].configure(
                text={
                    "面積 m²": "填地板面積。例如長6m×寬5m＝30m²；不需填淨高。",
                    "面積 坪": "填地板坪數，1坪＝3.305785m²；不需填淨高。",
                    "體積 m³": "這格填m³，不是m²。例：90m³ ÷ 淨高3m＝地板照明面積30m²。",
                    "長×寬": "",
                }[data["area_mode"]]
            )
        if self.tool == "units":
            self.subtitle.configure(
                text=UNIT_HELP.get(data["category"], TOOLS["units"]["subtitle"])
            )
        self.assumptions.configure(text=adopted_summary(self.tool, data))

    def calculate(self, focus=False):
        if self.pending:
            self.after_cancel(self.pending)
            self.pending = None
        for widget in self.widgets.values():
            if isinstance(widget, ttk.Entry) and not isinstance(widget, ttk.Combobox):
                widget.configure(style="TEntry")
        try:
            result = calculate_tool(self.tool, self.data())
            cards, details = presentation(result)
            for index, (title, value) in enumerate(self.cards):
                if index < len(cards):
                    title.config(text=cards[index][0])
                    value.config(text=cards[index][1])
                else:
                    title.config(text="")
                    value.config(text="")
            self.result = result
            if self.air_chart is not None:
                self.air_chart.set_state(result["state"])
            self.details.config(text="\n".join(details))
            if (
                self.tool == "lighting"
                and self.variables["area_mode"].get() == "體積 m³"
            ):
                explanation = f"地板照明面積＝{self.variables['area'].get()}m³ ÷ 淨高{self.variables['height'].get()}m＝{result['area_m2']:,.3f}m²"
                self.details.config(text=explanation + "\n" + "\n".join(details))
            self.formula.config(text="公式：" + result["formula"])
            self.note.config(text=result["note"])
            shortfall = (
                self.tool == "duct"
                and result["path_checked"]
                and any(
                    row.get("budget_sufficient") is False
                    for row in (result["rectangle"], result["round"])
                )
            )
            self.status.config(
                text=(
                    "已計算｜路徑壓力預算不足，請核對"
                    if shortfall
                    else "已計算｜本工具可獨立使用，結果為初估"
                ),
                style="Simple.Error.TLabel" if shortfall else "Simple.Good.TLabel",
            )
        except (ValidationError, ValueError) as error:
            self.clear()
            key = getattr(error, "field_name", None)
            spec = next(
                (row for row in TOOLS[self.tool]["fields"] if row["key"] == key), None
            )
            label = spec["label"] if spec else key or "輸入"
            self.status.config(
                text=f"請修正「{label}」：{error}", style="Simple.Error.TLabel"
            )
            if spec and spec["advanced"]:
                self.advanced.set(True)
                self.update_visibility()
            widget = self.widgets.get(key)
            if widget is not None:
                if isinstance(widget, ttk.Entry) and not isinstance(
                    widget, ttk.Combobox
                ):
                    widget.configure(style="Simple.Invalid.TEntry")
                if focus:
                    self.reveal(widget)
                    widget.focus_set()
        self.app.sync_actions()

    def reset(self):
        self.suspended = True
        try:
            for key, value in defaults(self.tool).items():
                self.variables[key].set(value)
            self.previous = self.data()
            self.advanced.set(False)
            if self.tool == "units":
                self.widgets["unit"].configure(values=tuple(UNITS["風量"]))
        finally:
            self.suspended = False
        self.update_visibility()
        self.calculate()


class SimpleToolsApp:
    def __init__(self, root):
        self.root = root
        self.current = "electrical"
        self.pages = {}
        self.workbench = None
        self.equipment_window = None
        root.title("廠務簡易工具 V5.5.5")
        width = min(1120, max(780, root.winfo_screenwidth() - 60))
        height = min(830, max(560, root.winfo_screenheight() - 100))
        root.geometry(f"{width}x{height}+20+20")
        root.minsize(780, 560)
        app_icon(root)
        self.configure_style()
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)
        side = tk.Frame(root, bg="#142c43", width=205)
        side.grid(row=0, column=0, rowspan=3, sticky="ns")
        side.pack_propagate(False)
        self.sidebar = side
        ttk.Label(side, text="廠務簡易工具\nV5.5.5", style="Simple.Brand.TLabel").pack(
            anchor="w", padx=18, pady=(22, 24)
        )
        self.nav = {}
        for key in ("electrical", "duct", "gas", "lighting"):
            button = tk.Button(
                side,
                text=TOOLS[key]["title"],
                command=lambda k=key: self.show_tool(k),
                relief="flat",
                anchor="w",
                padx=16,
                pady=11,
                bg="#142c43",
                fg="white",
                activebackground="#087d85",
                activeforeground="white",
                font=(self.family, 11),
            )
            button.pack(fill="x", padx=8, pady=3)
            self.nav[key] = button
        ttk.Label(side, text="其他常用快算", style="Simple.SideHint.TLabel").pack(
            anchor="w", padx=18, pady=(22, 6)
        )
        self.more_choice = tk.StringVar(root, "更多工具…")
        self.more = ttk.Combobox(
            side,
            textvariable=self.more_choice,
            values=[TOOLS[key]["title"] for key in ("water", "air", "units")],
            state="readonly",
            width=17,
        )
        self.more.pack(fill="x", padx=10, pady=3)
        self.more.bind(
            "<<ComboboxSelected>>",
            lambda event: self.show_tool(
                next(
                    key
                    for key in ("water", "air", "units")
                    if TOOLS[key]["title"] == self.more_choice.get()
                )
            ),
        )
        header = ttk.Frame(root, padding=(18, 12))
        header.grid(row=0, column=1, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header, text="選工具 → 填條件 → 看結果", style="Simple.Header.TLabel"
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(header, text="完整工程工作台", command=self.open_workbench).grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Button(header, text="設備表匯入", command=self.open_equipment).grid(
            row=1, column=1, padx=(6, 0), pady=(8, 0)
        )
        ttk.Label(header, text="Language / 語言").grid(
            row=2, column=2, sticky="e", pady=(3, 0)
        )
        self.language_picker = LanguagePicker(header)
        self.language_picker.grid(row=1, column=2, padx=(6, 0), pady=(8, 0), sticky="e")
        self.container = ttk.Frame(root)
        self.container.grid(row=1, column=1, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(0, weight=1)
        footer = ttk.Frame(root, padding=(16, 10))
        footer.grid(row=2, column=1, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.footer_text = ttk.Label(
            footer, text="各工具獨立計算", style="Simple.Muted.TLabel"
        )
        self.footer_text.grid(row=0, column=0, sticky="w")
        self.calc_button = ttk.Button(
            footer,
            text="計算",
            style="Simple.Primary.TButton",
            command=lambda: self.active_page().calculate(True),
        )
        self.calc_button.grid(row=0, column=1, padx=3)
        self.copy_button = ttk.Button(footer, text="複製結果", command=self.copy_result)
        self.copy_button.grid(row=0, column=2, padx=3)
        self.export_button = ttk.Button(
            footer, text="匯出TXT", command=self.export_result
        )
        self.export_button.grid(row=0, column=3, padx=3)
        root.bind("<F5>", lambda event: self.active_page().calculate(True))
        from .platform_support import bind_mac_shortcuts

        bind_mac_shortcuts(root, calculate=lambda: self.active_page().calculate(True))
        for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind(event, self.wheel, add="+")
        root.bind("<Configure>", self.resize, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        from .platform_support import install_mac_quit

        install_mac_quit(root, self.close)
        self.show_tool("electrical")

    def wheel(self, event):
        if event.widget.winfo_toplevel() is not self.root or isinstance(
            event.widget, ttk.Combobox
        ):
            return
        page = self.active_page()
        ancestor = event.widget
        while ancestor is not None and ancestor is not page:
            ancestor = getattr(ancestor, "master", None)
        if ancestor is None:
            return
        from .platform_support import scroll_units

        step = scroll_units(event)
        if not step:
            return
        page.canvas.yview_scroll(step, "units")
        return "break"

    def resize(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        compact = self.root.winfo_width() < 1000
        width = max(430, min(710, self.root.winfo_width() - 235))
        for page in self.pages.values():
            layout = (compact, width)
            if getattr(page, "_last_layout", None) == layout:
                continue
            page._last_layout = layout
            for spec in TOOLS[page.tool]["fields"]:
                key = spec["key"]
                stacked = compact or page.tool == "air"
                page.labels[key].grid_configure(
                    row=0, column=0, columnspan=3 if stacked else 1
                )
                page.labels[key].configure(
                    wraplength=max(280, width - 50) if stacked else 185
                )
                page.widgets[key].grid_configure(
                    row=1 if stacked else 0,
                    column=0 if stacked else 1,
                    columnspan=2 if stacked else 1,
                    pady=3 if stacked else 0,
                )
                if spec["units"]:
                    page.widgets[spec["units"][0]].grid_configure(
                        row=1 if stacked else 0, column=2
                    )
                if key in page.hints:
                    unit_only = len(spec["help"]) <= 10 and not spec["units"]
                    if unit_only:
                        page.hints[key].grid_configure(
                            row=1 if stacked else 0, column=2, columnspan=1, pady=0
                        )
                    else:
                        page.hints[key].grid_configure(
                            row=2 if stacked else 1,
                            column=0 if stacked else 1,
                            columnspan=3 if stacked else 2,
                        )
                    page.hints[key].configure(
                        wraplength=max(300, width - 50) if stacked else 440
                    )
            for index, box in enumerate(page.card_boxes):
                box.grid_configure(
                    row=index if compact else 0, column=0 if compact else index, pady=5
                )
                page.result_box.columnconfigure(
                    index, weight=1 if not compact or index == 0 else 0
                )
            for label in (
                page.subtitle,
                page.assumptions,
                page.status,
                page.details,
                page.formula,
                page.note,
            ):
                label.configure(wraplength=width)

    def configure_style(self):
        families = set(font.families(self.root))
        from .platform_support import preferred_ui_font

        self.family = preferred_ui_font(families)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            ".", font=(self.family, 10), background="#f1f5f9", foreground="#18334d"
        )
        style.configure("TButton", padding=(12, 8))
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=5)
        style.configure("Simple.Title.TLabel", font=(self.family, 21, "bold"))
        style.configure("Simple.Header.TLabel", font=(self.family, 12, "bold"))
        style.configure(
            "Simple.Brand.TLabel",
            background="#142c43",
            foreground="#6ee7df",
            font=(self.family, 15, "bold"),
        )
        style.configure(
            "Simple.SideHint.TLabel", background="#142c43", foreground="#b9cad8"
        )
        style.configure("Simple.Card.TFrame", background="white")
        style.configure("Simple.Card.TLabel", background="white")
        style.configure(
            "Simple.Value.TLabel",
            background="white",
            foreground="#087d85",
            font=(self.family, 17, "bold"),
        )
        style.configure(
            "Simple.Hint.TLabel",
            background="white",
            foreground="#587084",
            font=(self.family, 9),
        )
        style.configure("Simple.Muted.TLabel", foreground="#587084")
        style.configure("Simple.Good.TLabel", foreground="#087545")
        style.configure("Simple.Error.TLabel", foreground="#b12b2b")
        style.configure(
            "Simple.Primary.TButton", background="#087d85", foreground="white"
        )
        style.configure("Simple.Invalid.TEntry", fieldbackground="#fff0ed")

    def active_page(self):
        return self.pages[self.current]

    def show_tool(self, tool):
        for page in self.pages.values():
            page.grid_remove()
        self.current = tool
        if tool not in self.pages:
            self.pages[tool] = SimplePage(self.container, tool, self)
        page = self.pages[tool]
        page.grid(row=0, column=0, sticky="nsew")
        for key, button in self.nav.items():
            button.configure(bg="#087d85" if key == tool else "#142c43")
        self.more_choice.set(
            TOOLS[tool]["title"] if tool in ("water", "air", "units") else "更多工具…"
        )
        self.footer_text.configure(text=TOOLS[tool]["title"])
        self.sync_actions()
        self.resize()

    def sync_actions(self):
        if not hasattr(self, "copy_button"):
            return
        page = self.pages.get(self.current)
        enabled = page is not None and page.result is not None
        for button in (self.copy_button, self.export_button):
            button.state(["!disabled"] if enabled else ["disabled"])

    def copy_result(self):
        page = self.active_page()
        page.calculate()
        if page.result is None:
            return False
        self.root.clipboard_clear()
        self.root.clipboard_append(tool_report(page.result, page.data()))
        self.footer_text.configure(text="已複製本工具結果")
        return True

    def export_result(self, path=None):
        page = self.active_page()
        page.calculate()
        if page.result is None:
            return False
        path = path or filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".txt",
            initialfile=TOOLS[self.current]["title"] + ".txt",
            filetypes=[("文字結果", "*.txt")],
        )
        if not path:
            return False
        try:
            atomic_text(path, tool_report(page.result, page.data()))
            self.footer_text.configure(text="已匯出本工具結果")
            return True
        except OSError as error:
            messagebox.showerror("未能匯出", str(error), parent=self.root)
            return False

    def open_workbench(self):
        if self.workbench is not None and self.workbench.root.winfo_exists():
            self.workbench.root.lift()
            return self.workbench
        from .desktop import DesktopApp

        window = tk.Toplevel(self.root)
        self.workbench = DesktopApp(window)
        return self.workbench

    def close(self):
        if self.workbench is not None and self.workbench.root.winfo_exists():
            self.workbench.close()
            if self.workbench.root.winfo_exists():
                return
        if (
            self.equipment_window is not None
            and self.equipment_window.win.winfo_exists()
        ):
            self.equipment_window.close()
        for page in self.pages.values():
            if page.pending:
                page.after_cancel(page.pending)
        self.root.destroy()

    def open_equipment(self):
        if (
            self.equipment_window is not None
            and self.equipment_window.win.winfo_exists()
        ):
            self.equipment_window.win.lift()
            return self.equipment_window
        from .equipment_view import EquipmentWindow

        self.equipment_window = EquipmentWindow(self.root, self.family)
        return self.equipment_window
