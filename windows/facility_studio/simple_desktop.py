from .simple_engines import SUPPLIES, ELECTRICAL_POWER_UNITS, MOTOR_POWER_UNITS, electrical_unit_factor
"""Independent short forms are the default entry; the full workbench is optional."""

from .localized_tk import tk
from .localized_tk import ttk, filedialog, messagebox

from .errors import InputError, ValidationError
from .gas_catalog import CUSTOM_GAS, gas_label, reference_velocity, switched_velocity
from .tutorial_help import open_tutorial
from .version import VERSION, BUILD_VERSION
from .quick_tools import UNITS, UNIT_HELP
from .air_chart import AirChart
from .simple_engines import calculate_tool, FLOW_FACTORS, GAS_FLOW_FACTORS
from .simple_engines import AIR_PRESSURE_FACTORS, GAS_PRESSURE_FACTORS
from .simple_reports import presentation, tool_report
from .simple_schema import TOOLS, active_field, adopted_summary, defaults, input_unit
from .ui_common import app_icon
from .flow_toolbar import FlowToolbar
from .localized_tk import LanguagePicker
from .utils import atomic_text, number
from .industrial_theme import (Theme, ScrollableFrame, KPIFrame, ResultTable, InlineBanner,
                               format_number, set_entry_valid)
from .services import upstream_values


def field_unit(spec):
    """Keep a fixed unit column even for reference values with explanatory help."""
    if spec.get("display_unit"):
        return spec["display_unit"]
    if spec["units"] or spec["options"] or spec["checkbox"]:
        return ""
    hint = spec["help"]
    first = hint.split("；", 1)[0].split("，", 1)[0]
    if len(first) <= 12 and any(unit in first for unit in
            ("m", "W", "CMH", "Pa", "%", "°C", "LPM", "1/h", "人", "台", "K")):
        return first
    return {"pf": "—", "eta": "—", "efficiency": "—", "value": "",
            "quantity": "盞", "loaded": "條", "ratio": "—"}.get(spec["key"], "")


def wrap_to_width(label):
    """Wrap at the width the layout really gives the label, so a narrow column never cuts a word."""
    def resize(event):
        if event.width > 1 and int(float(label.cget("wraplength") or 0)) != event.width:
            label.configure(wraplength=event.width)
    label.bind("<Configure>", resize, add="+")


class SimplePage(ttk.Frame):
    def __init__(self, parent, tool, app):
        super().__init__(parent)
        self.tool, self.app = tool, app
        self.pending = None
        self.suspended = True
        self.result = None
        self.upstream_sources = set()
        self.upstream_keys = set()
        self.upstream_stale = False
        self.variables = {key: tk.StringVar(self, value) for key, value in defaults(tool).items()}
        self.previous = self.data()
        self.widgets, self.rows, self.labels, self.hints, self.unit_labels = {}, {}, {}, {}, {}
        self.columnconfigure(0, weight=2, minsize=Theme.px(365))
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)
        self.input_scroll = ScrollableFrame(self)
        self.input_scroll.grid(row=0, column=0, sticky="nsew")
        self.output_frame = ttk.Frame(self)
        self.output_frame.grid(row=0, column=1, sticky="nsew")
        self.output_frame.columnconfigure(0, weight=1)
        self.output_frame.rowconfigure(0, weight=1, uniform="result-halves")
        self.output_frame.rowconfigure(1, weight=1, uniform="result-halves")
        self.output_scroll = ScrollableFrame(self.output_frame)
        self.output_scroll.grid(row=0, column=0, sticky="nsew")
        self.detail_scroll = None
        if tool != "air":
            self.detail_scroll = ScrollableFrame(self.output_frame)
            self.detail_scroll.grid(row=1, column=0, sticky="nsew")
        self.canvas, self.body, self.win = self.input_scroll.canvas, self.input_scroll.body, self.input_scroll.item
        self.advanced = tk.BooleanVar(self, False)
        self.body.columnconfigure(0, weight=1)
        ttk.Label(self.body, text=TOOLS[tool]["title"], style="Simple.Title.TLabel").grid(row=0, column=0, sticky="w")
        self.subtitle = ttk.Label(self.body, text=TOOLS[tool]["subtitle"],
                                  style="Simple.Muted.TLabel", wraplength=360)
        self.subtitle.grid(row=1, column=0, sticky="ew", pady=(6, 14))
        self.form = ttk.Frame(self.body, style="Simple.Card.TFrame", padding=(16, 14))
        self.form.grid(row=2, column=0, sticky="ew")
        self.form.columnconfigure(0, weight=1)
        for index, spec in enumerate(TOOLS[tool]["fields"]):
            key = spec["key"]
            row = ttk.Frame(self.form, style="Form.Row.TFrame")
            row.grid(row=index, column=0, sticky="ew", pady=6)
            row.columnconfigure(0, weight=1, minsize=Theme.px(120))
            row.columnconfigure(1, weight=1, minsize=Theme.px(90))
            row.columnconfigure(2, minsize=Theme.px(58))
            self.labels[key] = ttk.Label(row, text=spec["label"], style="Simple.Card.TLabel",
                                         width=16, wraplength=Theme.px(135), anchor="w")
            self.labels[key].grid(row=0, column=0, sticky="w", padx=(0, 8))
            wrap_to_width(self.labels[key])
            if spec["checkbox"]:
                widget = ttk.Checkbutton(row, variable=self.variables[key], onvalue="1", offvalue="0", text="啟用")
            elif spec["options"]:
                widget = ttk.Combobox(row, textvariable=self.variables[key], values=spec["options"],
                                      state="readonly", width=12, justify="right", font=(Theme.mono, 11))
            else:
                widget = ttk.Entry(row, textvariable=self.variables[key], width=12, justify="right", font=(Theme.mono, 11))
            widget.grid(row=0, column=1, sticky="ew", padx=(0, 8))
            widget.bind("<Return>", lambda event: self._enter(), add="+")
            self.widgets[key] = widget
            if spec["units"]:
                unit_key, options = spec["units"]
                unit = ttk.Combobox(row, textvariable=self.variables[unit_key], values=options,
                                    state="readonly", width=8, font=(Theme.mono, 10))
                unit.grid(row=0, column=2, sticky="ew")
                self.widgets[unit_key] = unit
            else:
                unit = ttk.Label(row, text=field_unit(spec), width=7, style="Unit.TLabel", anchor="w")
                unit.grid(row=0, column=2, sticky="w")
                self.unit_labels[key] = unit
            hint_row = 1
            if tool == "electrical" and key == "power":
                unit_bar = ttk.Frame(row)
                unit_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 2))
                for col_i in range(4):
                    unit_bar.columnconfigure(col_i, weight=1)
                for u_idx, u_opt in enumerate(ELECTRICAL_POWER_UNITS):
                    ttk.Button(
                        unit_bar,
                        text=u_opt,
                        command=lambda u=u_opt: self.variables["power_unit"].set(u),
                    ).grid(row=u_idx // 4, column=u_idx % 4, sticky="ew", padx=1, pady=1)
                hint_row = 2
            if spec["help"] or key in ("ffu_topology", "ffu_airflow_basis") or (spec["options"] and max(map(len, spec["options"])) > 18):
                hint = ttk.Label(row, text=spec["help"], style="Simple.Hint.TLabel", wraplength=310)
                hint.grid(row=hint_row, column=0, columnspan=3, sticky="ew", pady=(3, 0))
                wrap_to_width(hint)
                self.hints[key] = hint
            self.rows[key] = row
        self.assumptions = ttk.Label(self.body, style="Simple.Muted.TLabel", wraplength=360)
        self.assumptions.grid(row=3, column=0, sticky="ew", pady=10)
        controls = ttk.Frame(self.body)
        controls.grid(row=4, column=0, sticky="ew", pady=6)
        if any(row["advanced"] for row in TOOLS[tool]["fields"]):
            ttk.Checkbutton(controls, text="調整預設值／進階條件", variable=self.advanced,
                            command=self.update_visibility).pack(anchor="w", pady=4)
        action_row = ttk.Frame(controls)
        action_row.pack(fill="x")
        self.upstream_button = ttk.Button(action_row, text="帶入上游結果", command=self.import_upstream)
        self.upstream_button.pack(side="left")
        # Clearing every input sits apart from the import action and asks first.
        ttk.Button(action_row, text="恢復預設", command=self.confirm_reset).pack(side="right")
        # Tool-specific actions wrap onto further rows instead of being squeezed beside each other.
        extras = FlowToolbar(controls) if tool in ("heat_loads", "lighting", "air", "water", "units") else None
        if extras is not None:
            extras.pack(fill="x", pady=(5, 0))
        if tool == "heat_loads":
            links = extras
            ttk.Button(links, text="帶入照明功率密度", command=lambda: self.import_upstream("lighting")).pack(side="left")
            ttk.Button(links, text="帶入A/B空氣焓差", command=lambda: self.import_upstream("air")).pack(side="left")
        if tool == "lighting":
            self.dialux_button = ttk.Button(
                extras, text="型錄 U／室指數檢核", command=self.apply_dialux_mode
            )
            self.dialux_button.pack(side="left")
        if tool in ("water", "units"):
            ttk.Button(
                extras,
                text="帶入物性與壓損分析" if tool == "water" else "九類工程單位換算",
                command=lambda: app.open_engineering_verification(
                    "pipe" if tool == "water" else "units", carry_water=tool == "water"
                ),
            ).pack(side="left")
        # Retain the read-only label API for integrations; the visible status is a banner.
        self.status = ttk.Label(self.body, style="Simple.Muted.TLabel", wraplength=360)
        output = self.output_scroll.body
        output.columnconfigure(0, weight=1)
        ttk.Label(output, text="工程設計總覽", style="Simple.Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.banner = InlineBanner(output)
        self.banner.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.result_box = KPIFrame(output, compact=True)
        self.result_box.grid(row=2, column=0, sticky="ew")
        self.cards, self.card_boxes = [], []
        detail_output = self.detail_scroll.body if self.detail_scroll is not None else output
        detail_output.columnconfigure(0, weight=1)
        offset = 0 if self.detail_scroll is not None else 3
        self.result_table = ResultTable(detail_output)
        self.result_table.grid(row=offset, column=0, sticky="nsew", pady=12)
        self.details = ttk.Label(detail_output, style="Simple.Normal.TLabel", wraplength=600)
        self.details.grid(row=offset+1, column=0, sticky="ew", pady=6)
        self.formula = ttk.Label(detail_output, style="Simple.Muted.TLabel", wraplength=600)
        self.formula.grid(row=offset+2, column=0, sticky="ew", pady=6)
        self.note = ttk.Label(detail_output, style="Simple.Muted.TLabel", wraplength=600)
        self.note.grid(row=offset+3, column=0, sticky="ew", pady=(4, 12))
        self.air_chart = None
        if tool == "air":
            self.air_chart = AirChart(self.output_frame, app.family)
            self.air_chart.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
            ttk.Button(extras, text="放大空氣線圖", command=self.open_air_chart).pack(side="left")
        self._stacked = None
        self._wrap_widths = None
        self.bind("<Configure>", self.responsive, add="+")
        self.bind("<Map>", self.responsive, add="+")
        for key, variable in self.variables.items():
            variable.trace_add("write", lambda *args, k=key: self.changed(k))
        self.bind("<Destroy>", self._destroy_page, add="+")
        self.suspended = False
        self.update_visibility()
        self.calculate()

    def _destroy_page(self, event):
        if event.widget is self and self.pending:
            self.after_cancel(self.pending)
            self.pending = None

    def open_air_chart(self):
        if self.result is None:
            self.calculate(True)
        if self.result is None:
            return
        win = tk.Toplevel(self)
        win.title("空氣狀態｜放大空氣線圖")
        win.geometry("1100x700")
        chart = AirChart(win, self.app.family)
        chart.pack(fill="both", expand=True, padx=14, pady=14)
        chart.set_state(self.result["state"], self.result.get("comparison_state"))
        ttk.Label(win, text="本視窗為開啟當下的狀態快照；輸入變更後請重開核對。", style="Simple.Muted.TLabel").pack(pady=(0, 8))

    def _enter(self):
        self.calculate(True)
        return "break"

    def responsive(self, event=None):
        if not self.winfo_ismapped():
            return
        width = self.winfo_width()
        stacked = width < Theme.px(680)
        if self._stacked != stacked:
            self._stacked = stacked
            self.output_frame.grid(row=1 if stacked else 0, column=0 if stacked else 1, sticky="nsew")
            self.rowconfigure(1, weight=1 if stacked else 0)
            self.columnconfigure(0, weight=2)
            self.columnconfigure(1, weight=0 if stacked else 3)
        left_width = max(300, self.input_scroll.winfo_width() - 42)
        right_width = max(300, self.output_scroll.winfo_width() - 42)
        widths = (left_width, right_width)
        if widths == self._wrap_widths:
            return
        self._wrap_widths = widths
        for label in (self.subtitle, self.assumptions, self.status):
            label.configure(wraplength=left_width)
        for label in (self.details, self.formula, self.note):
            label.configure(wraplength=right_width)

    def reveal(self, widget):
        self.update_idletasks()
        self.canvas.yview_moveto(max(0, (widget.winfo_rooty() - self.body.winfo_rooty() - 35)
                                      / max(1, self.body.winfo_height())))

    def import_upstream(self, only=None):
        results = {key: page.result for key, page in self.app.pages.items() if page.result is not None}
        if only:
            results = {key: value for key, value in results.items() if key == only}
        elif self.upstream_sources:
            results = {key: value for key, value in results.items() if key in self.upstream_sources}
        try:
            values = upstream_values(self.tool, results, self.data())
            if not values:
                self.banner.show("尚無可帶入的上游結果；請先完成對應工具計算。", "warning")
                return False
            sources = {"heat_loads": ("cleanroom", "lighting", "air"), "water": ("heat_loads",),
                       "pumps": ("water",), "electrical": ("cleanroom", "heat_loads", "lighting", "pumps")}
            fresh_sources = {key for key in sources.get(self.tool, ()) if key in results}
            self.upstream_sources = self.upstream_sources | fresh_sources if only else fresh_sources
            self.upstream_keys = self.upstream_keys | set(values) if only else set(values)
            self.upstream_stale = False
            self.app.invalidate_dependents(self.tool)
            self.suspended = True
            try:
                for key, value in values.items():
                    if key in self.variables:
                        self.variables[key].set(str(value))
                self.previous = self.data()
            finally:
                self.suspended = False
            self.update_visibility()
            self.calculate(True)
            if self.result is not None:
                if self.tool == "electrical":
                    self.banner.show("已帶入明列設備用電；請核對冰機、MAU、排風及製程設備是否齊全。", "warning")
                else:
                    self.banner.show("已帶入上游計算結果；後續修改可再次帶入更新。", "success")
            return self.result is not None
        except (ValidationError, ValueError, KeyError) as error:
            self.banner.show(str(error), "warning")
            return False

    def data(self):
        return {key: variable.get() for key, variable in self.variables.items()}

    def clear(self, text="輸入已變更，等待計算…"):
        self.result = None
        if self.air_chart is not None:
            self.air_chart.mark_stale()
        self.result_box.set_cards([dict(title="等待更新", value="—", status="待重算", tone="neutral")])
        self.result_table.set_rows([])
        self.details.config(text="")
        self.formula.config(text="")
        self.note.config(text="")
        self.status.config(text=text, style="Simple.Muted.TLabel")
        self.banner.show(text, "neutral")
        if self.app.current == self.tool:
            self.app.sync_actions()

    def changed(self, key):
        if self.suspended:
            return
        # Editing an adopted value explicitly returns this form to manual input.
        if key in self.upstream_keys:
            self.upstream_sources.clear()
            self.upstream_keys.clear()
            self.upstream_stale = False
        self.app.invalidate_dependents(self.tool)
        self.suspended = True
        try:
            if self.tool == "electrical" and key == "power_unit":
                old, new = self.previous[key], self.variables[key].get()
                phases, volts = SUPPLIES[self.variables["supply"].get()]
                pf = number(self.variables["pf"].get(), "pf", 0.1, 1)
                efficiency = self.variables["motor_efficiency"].get()
                old_factor = electrical_unit_factor(old, volts, pf, efficiency, phases)
                new_factor = electrical_unit_factor(new, volts, pf, efficiency, phases)
                value = number(self.variables["power"].get(), "power", 0)
                self.variables["power"].set(format(value * old_factor / new_factor, ".15g"))
                if new in MOTOR_POWER_UNITS:
                    self.variables["kind"].set("馬達")
            if self.tool == "gas" and key == "flow_basis":
                from .simple_engines import compressed_air
                previous_result = compressed_air(self.previous)
                is_standard = self.variables[key].get() == "標準流量"
                self.variables["flow"].set(format(previous_result["standard_lpm" if is_standard else "actual_lpm"], ".15g"))
                self.variables["flow_unit"].set("SLPM" if is_standard else "ALPM")
            gas_factors = GAS_FLOW_FACTORS if self.variables.get("flow_basis") is None or self.variables["flow_basis"].get() == "標準流量" else {"ALPM": 1, "ACFM": 28.316846592, "Am³/h": 1000 / 60}
            rules = {
                "duct": {
                    "flow_unit": ("flow", FLOW_FACTORS),
                    "pressure_unit": ("pressure", AIR_PRESSURE_FACTORS),
                },
                "gas": {
                    "flow_unit": ("flow", gas_factors),
                    "pressure_unit": ("pressure", GAS_PRESSURE_FACTORS),
                },
                "water": {
                    "flow_unit": ("flow", UNITS["水量"]),
                    "power_unit": ("power", UNITS["冷熱功率"]),
                },
                "pumps": {
                    "flow_unit": ("flow", UNITS["水量"]),
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
                self.variables["velocity"].set(switched_velocity(
                    self.previous["gas"], self.variables[key].get(),
                    self.variables["velocity"].get()))
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
            if spec["key"] in self.unit_labels:
                self.unit_labels[spec["key"]].configure(text=input_unit(self.tool, spec, data))
            if spec["options"] and (spec["key"] in ("ffu_topology", "ffu_airflow_basis") or max(map(len, spec["options"])) > 18) and spec["key"] in self.hints:
                self.hints[spec["key"]].configure(text=data[spec["key"]] + ("\n" + spec["help"] if spec["help"] else ""))
            visible = active_field(self.tool, spec["key"], data) and (
                not spec["advanced"] or self.advanced.get() or (self.tool == "duct" and data["check_path"] == "1" and spec["key"] in ("length", "k_sum", "equipment"))
            )
            if visible:
                self.rows[spec["key"]].grid()
            else:
                self.rows[spec["key"]].grid_remove()
        if self.tool == "electrical":
            u_cur = data.get("power_unit", "kW")
            self.labels["power"].configure(
                text="設備用電功率" if u_cur == "kW" else f"設備用電功率（{u_cur}）"
            )
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
        if self.tool == "gas":
            gas = data["gas"]
            self.hints["gas"].configure(text=gas_label(gas))
            self.hints["velocity"].configure(text="m/s；此氣體須填設計流速，沒有預設值" if reference_velocity(gas) is None else "m/s；既有氣體初估值可依設計修改")
            is_standard = data["flow_basis"] == "標準流量"
            self.labels["flow"].config(text="所需標準流量" if is_standard else "管內實際流量")
            self.widgets["flow_unit"].config(values=("SLPM", "SCFM", "Sm³/h") if is_standard else ("ALPM", "ACFM", "Am³/h"))
        if self.tool == "units":
            self.subtitle.configure(
                text=UNIT_HELP.get(data["category"], TOOLS["units"]["subtitle"])
            )
        self.assumptions.configure(text=adopted_summary(self.tool, data))

    def calculate(self, focus=False):
        if self.pending:
            self.after_cancel(self.pending)
            self.pending = None
        if self.upstream_stale:
            message = "上游條件已變更，請重新帶入；亦可修改帶入欄位改為手動輸入。"
            self.clear(message)
            self.banner.show(message, "warning")
            return
        for widget in self.widgets.values():
            set_entry_valid(widget, True)
        try:
            result = calculate_tool(self.tool, self.data())
            cards, details = presentation(result)
            warnings = result.get("warnings", [])
            tone = "warning" if warnings else "success"
            self.result_box.set_cards([dict(title=title, value=value, status="需核對" if warnings else "需求初估", tone=tone)
                                       for title, value in cards])
            rows = self.table_rows(result)
            rows += [("計算說明", text, "", "") for text in details]
            self.result_table.set_rows(rows)
            self.result = result
            if self.air_chart is not None:
                self.air_chart.set_state(result["state"], result.get("comparison_state"))
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
            status_message = (
                    "已計算｜路徑壓力預算不足，請核對"
                    if shortfall
                    else "已計算｜本工具可獨立使用，結果為初估"
                )
            self.status.config(
                text=status_message,
                style="Simple.Error.TLabel" if shortfall else "Simple.Good.TLabel",
            )
            self.banner.show(warnings[0] if warnings else status_message,
                             "warning" if warnings or shortfall else "success")
        except (ValidationError, ValueError) as error:
            self.clear()
            key = getattr(error, "field_name", None)
            spec = next(
                (row for row in TOOLS[self.tool]["fields"] if row["key"] == key), None
            )
            label = spec["label"] if spec else key or "輸入"
            message = f"請修正「{label}」：{error}"
            self.status.config(text=message, style="Simple.Error.TLabel")
            self.banner.show(message, "danger")
            if spec and spec["advanced"]:
                self.advanced.set(True)
                self.update_visibility()
            widget = self.widgets.get(key)
            if widget is not None:
                set_entry_valid(widget, False)
                if focus:
                    self.reveal(widget)
                    widget.focus_set()
        if self.result is not None:
            issues = self.result.get("warnings", [])
            self.banner.show("；".join(issues) if issues else status_message,
                             "warning" if issues else "danger" if shortfall else "success")
        self.app.sync_actions()

    def table_rows(self, result):
        from .display_helpers import engineering_result_rows
        return engineering_result_rows(result)

    def apply_dialux_mode(self):
        if self.tool != "lighting":
            return False
        self.advanced.set(True)
        if self.variables["area_mode"].get() != "長×寬":
            # Area alone cannot establish the actual room geometry. Keep the
            # current calculation instead of adopting hidden length/width drafts.
            self.update_visibility()
            self.calculate(True)
            if self.result is not None:
                self.banner.show(
                    "已保留目前面積與燈具條件。室指數 K 需要實際長寬；請選長×寬並確認尺寸後，再按此按鈕。",
                    "warning",
                )
                self.reveal(self.widgets["area_mode"])
            return False
        self.app.invalidate_dependents(self.tool)
        self.suspended = True
        try:
            self.variables["u_mode"].set("型錄 U＋室指數 K 檢核")
            self.previous = self.data()
        finally:
            self.suspended = False
        self.update_visibility()
        self.calculate(True)
        return self.result is not None

    def confirm_reset(self):
        """Button entry point: ask before discarding inputs that differ from the defaults."""
        changed = any(key in self.variables and self.variables[key].get() != value
                      for key, value in defaults(self.tool).items())
        if changed and not messagebox.askokcancel(
                "恢復預設", "將清除本工具目前的所有輸入並恢復預設值，此動作無法復原。確定要繼續嗎？",
                parent=self.winfo_toplevel()):
            return False
        self.reset()
        return True

    def reset(self):
        self.app.invalidate_dependents(self.tool)
        self.upstream_sources.clear()
        self.upstream_keys.clear()
        self.upstream_stale = False
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
        self.canvas.yview_moveto(0)
        self.output_scroll.canvas.yview_moveto(0)


class SimpleToolsApp:
    def __init__(self, root):
        self.root = root
        self.current = "electrical"
        self.pages = {}
        self.workbench = None
        self.equipment_window = None
        self.workbench_mode = False
        self.extra_host = None
        self.verification_host = None
        self.verification_active = False
        root.title("廠務簡易工具 V" + BUILD_VERSION)
        self.configure_style()
        width = min(Theme.px(1440), max(Theme.px(980), root.winfo_screenwidth() - Theme.px(60)))
        height = min(Theme.px(830), max(Theme.px(600), root.winfo_screenheight() - Theme.px(100)))
        root.geometry(f"{width}x{height}+20+20")
        root.minsize(Theme.px(900), Theme.px(600))
        app_icon(root)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)
        side = tk.Frame(root, bg=Theme.NAV, width=Theme.px(185))
        side.grid(row=0, column=0, rowspan=3, sticky="ns")
        side.pack_propagate(False)
        self.sidebar = side
        # Footer first: pack gives space in packing order, so a short window clips the
        # navigation list instead of the tutorial button and the author credit.
        self.author_credit = tk.Label(
            side, text="設計：\nANDY HUANG ©", bg=Theme.NAV,
            fg=Theme.MUTED, justify="left", font=(self.family, 9),
        )
        self.author_credit.pack(side="bottom", anchor="w", padx=18, pady=(8, 16))
        self.tutorial_button = ttk.Button(
            side, text="本工具教學", command=lambda: open_tutorial(root, self.current),
        )
        self.tutorial_button.pack(side="bottom", fill="x", padx=12, pady=(8, 0))
        ttk.Label(side, text="廠務簡易工具\nV" + VERSION, style="Simple.Brand.TLabel").pack(
            anchor="w", padx=18, pady=(16, 12)
        )
        self.nav = {}
        for key in TOOLS:
            button = ttk.Button(
                side, text=TOOLS[key]["title"], command=lambda k=key: self.show_tool(k),
                style="Nav.TButton", width=20,
            )
            button.pack(fill="x", padx=8, pady=2)
            self.nav[key] = button
            if key == "gas":
                self.pv_button = ttk.Button(side, text="   PV 真空", command=self.open_pv, style="Nav.TButton", width=20)
                self.pv_button.pack(fill="x", padx=8, pady=2)
        self.fit_window_to_sidebar()
        header = ttk.Frame(root, padding=(18, 12))
        header.grid(row=0, column=1, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header, text="工程設計 → 獨立核對 → 匯出證據", style="Simple.Header.TLabel"
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        engineering = FlowToolbar(header)
        engineering.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(engineering, text="完整工程工作台", command=self.open_workbench).pack(side="left")
        ttk.Button(engineering, text="設備表匯入", command=self.open_equipment).pack(side="left", padx=(6, 0))
        ttk.Button(engineering, text="其他工程快算", command=self.open_extra_tools).pack(side="left", padx=(6, 0))
        ttk.Button(engineering, text="設計檢核中心", command=self.open_engineering_verification,
                   style="Simple.Primary.TButton").pack(side="left", padx=(6, 0))
        features = FlowToolbar(header)
        features.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        for title, tab in (("AHU 獨立核對", "ahu"), ("水管物性與壓損", "pipe"), ("九類單位換算", "units")):
            ttk.Button(features, text=title,
                       command=lambda k=tab: self.open_engineering_verification(k)).pack(side="left", padx=(0, 6))
        from .sandbox_ui import install_menus
        install_menus(root)
        ttk.Label(header, text="介面語言").grid(
            row=2, column=2, sticky="e", pady=(3, 0)
        )
        self.language_picker = LanguagePicker(header)
        self.language_picker.grid(row=1, column=2, padx=(6, 0), pady=(8, 0), sticky="e")
        self.container = ttk.Frame(root)
        self.container.grid(row=1, column=1, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(0, weight=1)
        footer = ttk.Frame(root, padding=(16, 10))
        self.footer = footer
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
        self.summary_button = ttk.Button(footer, text="設計總覽 HTML", command=self.export_summary)
        self.summary_button.grid(row=0, column=4, padx=3)
        self.bind_mode_shortcuts()
        root.bind("<Configure>", self.resize, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        from .platform_support import bind_mac_shortcuts, install_mac_quit

        bind_mac_shortcuts(
            root,
            calculate=self.calculate_active,
            save=lambda: self.workbench.save() if self.workbench_mode else None,
            open=lambda: self.workbench.load() if self.workbench_mode else None,
        )
        install_mac_quit(root, self.close)
        self.show_tool("electrical")
        self.simple_widgets = [w for w in root.winfo_children() if w.winfo_manager() == "grid"]

    def bind_mode_shortcuts(self):
        self.root.bind("<F5>", lambda event: self.calculate_active())
        self.root.bind("<Return>", lambda event: None if self.workbench_mode else
                       None if self.verification_active else self.extra_tools.calculate() if self.extra_host and self.extra_host.winfo_ismapped() else self.active_page()._enter())
        self.root.bind("<Control-s>", lambda event: self.workbench.save() if self.workbench_mode else None)
        self.root.bind("<Control-o>", lambda event: self.workbench.load() if self.workbench_mode else None)

    def calculate_active(self):
        if self.workbench_mode:
            return self.workbench.recalculate(True)
        if self.verification_active:
            return self.verification.calculate_current()
        if self.extra_host and self.extra_host.winfo_ismapped():
            return self.extra_tools.calculate()
        return self.active_page().calculate(True)

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
        delta = getattr(event, "delta", 0)
        step = -3 if getattr(event, "num", 0) == 4 or delta > 0 else 3
        page.canvas.yview_scroll(step, "units")
        return "break"

    def resize(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        page = self.pages.get(self.current)
        if page is not None:
            page.responsive()

    def configure_style(self):
        Theme.apply(self.root)
        self.family = Theme.family

    def open_engineering_verification(self, initial_tab="ahu", carry_water=False):
        from .feed_review_preview import VerificationWindow
        from .engineering_verification import pipe_from_water_tool

        def water_provider():
            if "water" not in self.pages:
                raise ValueError("請先開啟冷熱水快算並填寫條件。")
            return pipe_from_water_tool(self.pages["water"].data())

        if self.workbench_mode:
            self.show_simple_tools()
        if self.verification_host is None:
            self.verification_host = ttk.Frame(self.container)
            self.verification = VerificationWindow(
                self.root, water_provider=water_provider, host=self.verification_host,
                on_close=lambda: self.show_tool(self.current),
            )
        for page in self.pages.values():
            page.grid_remove()
        if self.extra_host is not None:
            self.extra_host.grid_remove()
        self.verification_host.grid(row=0, column=0, sticky="nsew")
        self.verification_active = True
        self.footer.grid_remove()
        self.verification.nb.select(self.verification.frames[initial_tab])
        if carry_water:
            self.verification.load_water()
        self.root.title("Facility Studio 設計檢核中心 V" + BUILD_VERSION)
        return self.verification_host

    def active_page(self):
        return self.pages[self.current]

    def show_tool(self, tool):
        if self.workbench_mode:
            self.show_simple_tools()
        if self.extra_host is not None and self.extra_host.winfo_exists():
            self.extra_host.grid_remove()
            self.footer.grid()
        if self.verification_host is not None:
            self.verification_host.grid_remove()
            self.verification_active = False
            self.footer.grid()
        for page in self.pages.values():
            page.grid_remove()
        self.current = tool
        self.root.title("Facility Studio 工程設計 V" + BUILD_VERSION)
        if tool not in self.pages:
            self.pages[tool] = SimplePage(self.container, tool, self)
        page = self.pages[tool]
        page.grid(row=0, column=0, sticky="nsew")
        for key, button in self.nav.items():
            button.configure(style="Nav.Active.TButton" if key == tool else "Nav.TButton",
                             text=("▎ " if key == tool else "   ") + TOOLS[key]["title"])
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
        self.summary_button.state(["!disabled"] if any(p.result is not None for p in self.pages.values()) else ["disabled"])

    def invalidate_dependents(self, source, visited=None):
        visited = set() if visited is None else visited
        if source in visited:
            return
        visited.add(source)
        for key, page in self.pages.items():
            if source in page.upstream_sources:
                page.upstream_stale = True
                page.clear("上游條件已變更，請重新帶入；亦可修改帶入欄位改為手動輸入。")
                self.invalidate_dependents(key, visited)

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
            filetypes=[("文字結果", "*.txt"), ("HTML 設計報表", "*.html")],
        )
        if not path:
            return False
        try:
            from pathlib import Path
            if Path(path).suffix.lower() in (".html", ".htm"):
                from .html_report import html_report
                content = html_report(page.result)
            else:
                content = tool_report(page.result, page.data())
            atomic_text(path, content)
            self.footer_text.configure(text="已匯出本工具結果")
            return True
        except OSError as error:
            page.banner.show("未能匯出：" + str(error), "danger")
            return False

    def export_summary(self, path=None):
        results = {key: page.result for key, page in self.pages.items() if page.result is not None}
        if not results:
            return False
        path = path or filedialog.asksaveasfilename(parent=self.root, defaultextension=".html",
                         initialfile="Facility_Design_Summary.html", filetypes=[("HTML 設計報表", "*.html")])
        if not path:
            return False
        try:
            from .html_report import html_report
            atomic_text(path, html_report({"pipeline": results}))
            self.footer_text.configure(text="已匯出目前有效計算的設備總覽")
            return True
        except (OSError, InputError, ValueError) as error:
            self.active_page().banner.show("未能匯出：" + str(error), "danger")
            return False

    def open_workbench(self):
        for widget in self.simple_widgets:
            widget.grid_remove()
        self.workbench_mode = True
        if self.workbench is None:
            from .desktop import DesktopApp
            before = set(self.root.winfo_children())
            self.workbench = DesktopApp(self.root)
            self.workbench.simple_app = self
            self.workbench_widgets = [w for w in self.root.winfo_children() if w not in before and w.winfo_manager() == "grid"]
        else:
            for widget in self.workbench_widgets:
                widget.grid()
        self.root.title("廠務工程工作台 V" + BUILD_VERSION)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.bind_mode_shortcuts()
        return self.workbench

    def sidebar_required_height(self):
        """Height at which every sidebar item (navigation, tutorial, credit) is fully visible."""
        self.sidebar.update_idletasks()
        total = 0
        for child in self.sidebar.winfo_children():
            pad = child.pack_info()["pady"]
            total += child.winfo_reqheight() + (sum(map(int, pad)) if isinstance(pad, (tuple, list)) else 2 * int(pad))
        return total

    def fit_window_to_sidebar(self):
        self.root.minsize(Theme.px(900), max(Theme.px(600), self.sidebar_required_height()))
        if self.root.winfo_height() < self.root.minsize()[1]:
            self.root.geometry(f"{self.root.winfo_width()}x{self.root.minsize()[1]}")

    def show_simple_tools(self):
        self.workbench_mode = False
        for widget in self.workbench_widgets:
            widget.grid_remove()
        for widget in self.simple_widgets:
            widget.grid()
        self.root.title("廠務簡易工具 V" + BUILD_VERSION)
        self.fit_window_to_sidebar()
        self.bind_mode_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        return self

    def open_extra_tools(self):
        if self.workbench is None:
            self.open_workbench()
            self.show_simple_tools()
        if self.extra_host is None or not self.extra_host.winfo_exists():
            from .tools_view import QuickToolsWindow
            self.extra_host = ttk.Frame(self.container)
            self.extra_tools = QuickToolsWindow(self.container, self.workbench, host=self.extra_host,
                allowed_tools=("濕空氣計算", "兩股混風", "兩點空氣過程", "水量與熱量", "水管實際流速", "Kv 與壓差", "耗電與費用"))
        for page in self.pages.values():
            page.grid_remove()
        if self.verification_host is not None:
            self.verification_host.grid_remove()
            self.verification_active = False
        self.extra_host.grid(row=0, column=0, sticky="nsew")
        self.footer.grid_remove()
        return self.extra_tools

    def open_pv(self):
        workbench = self.open_workbench()
        workbench.show_pv()
        return workbench

    def close(self):
        if self.workbench is not None and self.workbench.root is self.root:
            return self.workbench.close()
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
