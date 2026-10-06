"""Small, standalone calculators usable without a valid factory project."""

import tkinter as tk
from tkinter import ttk, messagebox
import json, math
from . import quick_tools as q
from .project_store import app_data
from .utils import atomic_text, state_trh
from .ui_common import app_icon

TOOLS = {
    "單位轉換": [
        ("category", "類別", "風量", list(q.UNITS)),
        ("unit", "輸入單位", "CMH", ["CMH", "CFM", "L/s", "m³/s"]),
        ("value", "數值", "1000", None),
    ],
    "濕空氣計算": [
        ("mode", "輸入組合", "乾球＋RH", q.PSY_MODES),
        ("first", "第一個值", "35", None),
        ("second", "第二個值", "70", None),
        ("pressure", "大氣壓 kPa(abs)，60～120", "101.325", None),
    ],
    "兩股混風": [
        ("t1", "第一股乾球 °C", "35", None),
        ("rh1", "第一股 RH %", "70", None),
        ("flow1", "第一股實際風量 CMH", "1000", None),
        ("t2", "第二股乾球 °C", "22", None),
        ("rh2", "第二股 RH %", "50", None),
        ("flow2", "第二股實際風量 CMH", "4000", None),
        ("pressure", "大氣壓 kPa(abs)，60～120", "101.325", None),
    ],
    "兩點空氣過程": [
        ("t1", "入口乾球 °C", "35", None),
        ("rh1", "入口 RH %", "70", None),
        ("t2", "出口乾球 °C", "15", None),
        ("rh2", "出口 RH %", "95", None),
        ("flow", "入口實際風量 CMH", "5000", None),
        ("pressure", "大氣壓 kPa(abs)，60～120", "101.325", None),
    ],
    "水量與熱量": [
        ("solve", "求解目標", "熱量 kW", ["熱量 kW", "流量 LPM", "溫差 K"]),
        ("first", "第一個值", "400", None),
        ("second", "第二個值", "5", None),
        ("rho", "密度 kg/m³", "1000", None),
        ("cp", "比熱 kJ/(kg·K)", "4.1868", None),
        ("mu", "黏度 Pa·s（供主案壓損）", "0.001", None),
    ],
    "水管實際流速": [
        ("flow_lpm", "流量 LPM", "400", None),
        ("inner_diameter_mm", "實際內徑 mm", "67.9", None),
    ],
    "風管定寸": [
        ("cmh", "風量 CMH", "6000", None),
        ("velocity", "流速上限 m/s", "10", None),
        ("ratio", "最大寬高比", "2", None),
        ("shape", "形狀", "方管", ["方管", "圓管"]),
    ],
    "水管定寸": [("lpm", "水量 LPM", "400", None), ("vmax", "流速上限 m/s", "2", None)],
    "Kv 與壓差": [
        ("solve", "求解目標", "Kv", ["Kv", "流量 m³/h", "壓差 bar"]),
        ("first", "第一個值", "10", None),
        ("second", "第二個值", "0.2", None),
        ("specific_gravity", "液體比重 SG", "1", None),
    ],
    "耗電與費用": [
        ("power_kw", "設備輸入 kW", "100", None),
        ("hours_per_day", "每日運轉時數", "12", None),
        ("days", "計算天數", "30", None),
        ("load_fraction", "平均負載比例 0～1", "0.8", None),
        ("rate", "自填每 kWh 單價", "4", None),
    ],
}
LABELS = {
    "t": "乾球 °C",
    "rh": "相對濕度 %",
    "w": "含濕比 kg/kg乾空氣",
    "h": "焓 kJ/kg乾空氣",
    "v_da": "比容 m³/kg乾空氣",
    "rho_moist": "濕空氣密度 kg/m³",
    "dewpoint_c": "露點 °C",
    "wetbulb_c": "濕球 °C",
    "pressure_kpa": "大氣壓 kPa",
    "state": "混合後狀態",
    "mass_da_kg_s": "乾空氣質量流率 kg/s",
    "flow_out_cmh": "混合後實際風量 CMH",
    "mass1_da_kg_s": "第一股乾空氣 kg/s",
    "mass2_da_kg_s": "第二股乾空氣 kg/s",
    "basis": "計算基準",
    "inlet": "入口",
    "outlet": "出口",
    "net_air_kw": "加入空氣的淨熱量 kW",
    "net_moisture_kg_h": "加入空氣的淨水氣 kg/h",
    "kw": "熱量 kW",
    "lpm": "流量 LPM",
    "delta_t": "水溫差 K",
    "us_rt": "US RT",
    "formula": "公式／限制",
    "velocity_mps": "流速 m/s",
    "area_m2": "截面積 m²",
    "kv": "Kv",
    "cv_us": "Cv（US）",
    "flow_m3h": "流量 m³/h",
    "drop_bar": "壓差 bar",
    "kwh": "累積電量 kWh",
    "cost": "費用（依自填幣別）",
    "flow_cmh": "風量 CMH",
    "width_mm": "寬 mm",
    "height_mm": "高 mm",
    "diameter_m": "計算直徑 m",
    "velocity_limit_mps": "流速上限 m/s",
    "runs": "並聯支數",
    "size": "候選尺寸",
    "id_mm": "實際內徑 mm",
    "shape": "風管形狀",
    "nominal": "名目尺寸",
}


def result_text(value, indent=""):
    rows = []
    for k, v in value.items():
        if k == "x" and "w" in value:
            continue
        label = LABELS.get(k, k)
        if isinstance(v, dict):
            rows.append(indent + label + "：\n" + result_text(v, indent + "  "))
        elif isinstance(v, (float, int)):
            rows.append(indent + label + "：" + format(v, ",.6g"))
        else:
            rows.append(indent + label + "：" + ("無有限露點" if v is None else str(v)))
    return "\n".join(rows)


class QuickToolsWindow:
    def __init__(self, parent, main_app):
        self.main_app = main_app
        self.win = tk.Toplevel(parent)
        self.win.title("工程快算｜V5.5.4")
        self.win.geometry("1020x850")
        self.win.minsize(840, 650)
        app_icon(self.win)
        main_app.children.append(self)
        self.values = {}
        self.widgets = {}
        self.result = None
        self.history = []
        self.favorites = []
        self.drafts = {}
        self.mode_drafts = {}
        self.built_tool = None
        self.targets = {}
        self.suspended = False
        self.settings = app_data() / "Quick_Tools.json"
        try:
            data = json.loads(self.settings.read_text(encoding="utf-8-sig"))
            raw_drafts = data.get("drafts", {})
            if isinstance(raw_drafts, dict):
                self.drafts = {
                    name: {
                        k: v
                        for k, v in values.items()
                        if isinstance(v, str) and len(v) <= 1000
                    }
                    for name, values in raw_drafts.items()
                    if name in TOOLS and isinstance(values, dict)
                }
            self.history = [
                x
                for x in data.get("history", [])
                if isinstance(x, dict)
                and x.get("tool") in TOOLS
                and isinstance(x.get("values"), dict)
                and isinstance(x.get("summary"), str)
            ][:30]
            self.favorites = list(
                dict.fromkeys(
                    x
                    for x in data.get("favorites", [])
                    if isinstance(x, str) and x in TOOLS
                )
            )
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        top = ttk.Frame(self.win, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="工程快算", style="Title.TLabel").pack(side="left")
        self.tool = tk.StringVar(
            value=self.favorites[0] if self.favorites else "單位轉換"
        )
        self.selector = ttk.Combobox(
            top,
            textvariable=self.tool,
            values=self.ordered_tools(),
            state="readonly",
            width=20,
        )
        self.selector.pack(side="left", padx=15)
        self.selector.bind("<<ComboboxSelected>>", lambda e: self.build())
        ttk.Button(top, text="收藏／取消收藏", command=self.favorite).pack(side="left")
        ttk.Button(top, text="帶入目前專案…", command=self.send_to_project).pack(
            side="right"
        )
        target_bar = ttk.Frame(self.win, padding=(12, 4))
        target_bar.pack(fill="x")
        self.recipient_label = ttk.Label(target_bar, text="")
        self.recipient_label.pack(side="left")
        self.target = tk.StringVar(value="")
        self.target_box = ttk.Combobox(
            target_bar, textvariable=self.target, values=[], state="disabled", width=22
        )
        self.target_box.pack(side="left", padx=10)
        self.form = ttk.Frame(self.win, padding=12)
        self.form.pack(fill="x")
        self.hint = ttk.Label(self.win, wraplength=950, style="Muted.TLabel")
        self.hint.pack(fill="x", padx=15, pady=6)
        bar = ttk.Frame(self.win, padding=(12, 4))
        bar.pack(fill="x")
        ttk.Button(
            bar, text="計算", command=self.calculate, style="Accent.TButton"
        ).pack(side="left")
        ttk.Button(bar, text="複製結果", command=self.copy).pack(side="left", padx=8)
        ttk.Label(bar, text="最近計算").pack(side="left", padx=8)
        self.recent = ttk.Combobox(
            bar,
            values=[x["tool"] + "｜" + x.get("summary", "") for x in self.history],
            state="readonly",
            width=35,
        )
        self.recent.pack(side="left")
        self.recent.bind("<<ComboboxSelected>>", lambda e: self.restore())
        pane = ttk.Panedwindow(self.win, orient="vertical")
        pane.pack(fill="both", expand=True, padx=12, pady=8)
        textframe = ttk.Frame(pane)
        self.text = tk.Text(
            textframe,
            wrap="word",
            height=10,
            font=("TkDefaultFont", 11),
            padx=12,
            pady=10,
            state="disabled",
        )
        sc = ttk.Scrollbar(textframe, command=self.text.yview)
        sc.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        self.text.config(yscrollcommand=sc.set)
        pane.add(textframe, weight=1)
        self.plot = None
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            pf = ttk.Frame(pane)
            self.fig = Figure(figsize=(7, 3), dpi=90)
            self.ax = self.fig.add_subplot(111)
            self.plot = FigureCanvasTkAgg(self.fig, master=pf)
            self.plot.get_tk_widget().pack(fill="both", expand=True)
            pane.add(pf, weight=1)
        except ImportError:
            pass
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.build()
        self.calculate()

    def ordered_tools(self):
        return self.favorites + [x for x in TOOLS if x not in self.favorites]

    def set_text(self, text):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.config(state="disabled")

    def build(self):
        if self.built_tool:
            self.drafts[self.built_tool] = {k: v.get() for k, v in self.values.items()}
            self.targets[self.built_tool] = self.target.get()
        self.built_tool = self.tool.get()
        self.field_labels = {}
        for w in self.form.winfo_children():
            w.destroy()
        self.values = {}
        self.widgets = {}
        self.suspended = True
        for j, (k, label, default, options) in enumerate(TOOLS[self.tool.get()]):
            r, c = divmod(j, 2)
            base = c * 3
            self.field_labels[k] = ttk.Label(self.form, text=label)
            self.field_labels[k].grid(row=r, column=base, sticky="w", padx=6, pady=5)
            saved = self.drafts.get(self.tool.get(), {}).get(k, default)
            if options and saved not in options:
                saved = default
            v = tk.StringVar(value=saved)
            self.values[k] = v
            w = (
                ttk.Combobox(
                    self.form,
                    textvariable=v,
                    values=options,
                    state="readonly",
                    width=22,
                )
                if options
                else ttk.Entry(self.form, textvariable=v, width=24)
            )
            w.grid(row=r, column=base + 1, sticky="ew", padx=6, pady=5)
            self.widgets[k] = w
            v.trace_add("write", lambda *a, key=k: self.changed(key))
        self.form.columnconfigure(1, weight=1)
        self.form.columnconfigure(4, weight=1)
        self.suspended = False
        self.mode_previous = self.current_mode()
        self.result = None
        self.update_targets()
        self.changed()

    def current_mode(self):
        key = (
            "mode"
            if "mode" in self.values
            else "solve" if "solve" in self.values else None
        )
        return self.values[key].get() if key else ""

    def update_targets(self):
        options = {
            "濕空氣計算": ["夏季外氣", "冬季外氣", "室內目標"],
            "水量與熱量": ["CHW", "MCHW", "DCCW", "PCW", "HW"],
            "風管定寸": ["GEX", "SEX", "AEX", "VEX", "HEX"],
        }.get(self.tool.get(), [])
        target = self.targets.get(self.tool.get(), "")
        self.target.set(
            target if target in options else options[0] if options else "僅獨立計算"
        )
        self.target_box.config(
            values=options, state="readonly" if options else "disabled"
        )
        self.on_main_changed()

    def on_main_changed(self):
        self.recipient_label.config(
            text="帶入目標｜" + self.main_app.variables["project_name"].get()
        )

    def switch_input_mode(self, old_result):
        mode = self.current_mode()
        if mode == self.mode_previous or not all(
            k in self.values for k in ["first", "second"]
        ):
            return
        tool = self.tool.get()
        self.mode_drafts[(tool, self.mode_previous)] = [
            self.values[k].get() for k in ["first", "second"]
        ]
        values = self.mode_drafts.get((tool, mode), ["", ""])
        if old_result:
            if tool == "濕空氣計算":
                r = old_result
                values = {
                    "乾球＋RH": [r["t"], r["rh"]],
                    "乾球＋濕球": [r["t"], r["wetbulb_c"]],
                    "乾球＋露點": [r["t"], r["dewpoint_c"]],
                    "焓＋含濕比": [r["h"], r["w"] * 1000],
                }[mode]
            elif tool == "水量與熱量":
                r = old_result
                values = {
                    "熱量 kW": [r["lpm"], r["delta_t"]],
                    "流量 LPM": [r["kw"], r["delta_t"]],
                    "溫差 K": [r["kw"], r["lpm"]],
                }[mode]
            elif tool == "Kv 與壓差":
                r = old_result
                values = {
                    "Kv": [r["flow_m3h"], r["drop_bar"]],
                    "流量 m³/h": [r["kv"], r["drop_bar"]],
                    "壓差 bar": [r["flow_m3h"], r["kv"]],
                }[mode]
        self.suspended = True
        try:
            for key, value in zip(["first", "second"], values):
                self.values[key].set("" if value is None else str(value))
        finally:
            self.suspended = False
        self.mode_previous = mode

    def changed(self, key=None):
        if self.suspended:
            return
        self.switch_input_mode(self.result)
        self.result = None
        self.set_text("條件已變更，按「計算」更新結果。")
        if self.plot:
            self.ax.clear()
            self.plot.draw_idle()
        tool = self.tool.get()
        hint = "所有工具可離線獨立計算；不必先完成廠房專案。"
        if tool == "單位轉換":
            category = self.values["category"].get()
            units = list(q.UNITS[category])
            self.widgets["unit"].config(values=units)
            if self.values["unit"].get() not in units:
                self.suspended = True
                self.values["unit"].set(units[0])
                self.suspended = False
            hint = q.UNIT_HELP.get(
                category,
                "壓力換算不改變表壓／絕壓基準；標準氣體流量需另給溫壓。DN／英吋名目管徑不是實際內徑。",
            )
        elif tool == "濕空氣計算":
            hint = {
                "乾球＋RH": "第一值 °C；第二值 %RH。",
                "乾球＋濕球": "第一值乾球 °C；第二值濕球 °C。",
                "乾球＋露點": "第一值乾球 °C；第二值露點 °C。",
                "焓＋含濕比": "第一值 kJ/kg乾空氣；第二值 g/kg乾空氣。",
            }[self.values["mode"].get()]
        elif tool == "水量與熱量":
            hint = {
                "熱量 kW": "第一值流量 LPM；第二值溫差 K。",
                "流量 LPM": "第一值熱量 kW；第二值溫差 K。",
                "溫差 K": "第一值熱量 kW；第二值流量 LPM。",
            }[self.values["solve"].get()]
        elif tool == "Kv 與壓差":
            hint = {
                "Kv": "第一值流量 m³/h；第二值壓差 bar。",
                "流量 m³/h": "第一值 Kv；第二值壓差 bar。",
                "壓差 bar": "第一值流量 m³/h；第二值 Kv。",
            }[self.values["solve"].get()] + " 限不可壓縮液體初估。"
        names = {
            "濕空氣計算": {
                "乾球＋RH": ["乾球 °C", "相對濕度 %RH"],
                "乾球＋濕球": ["乾球 °C", "濕球 °C"],
                "乾球＋露點": ["乾球 °C", "露點 °C"],
                "焓＋含濕比": ["焓 kJ/kg乾空氣", "含濕比 g/kg乾空氣"],
            },
            "水量與熱量": {
                "熱量 kW": ["流量 LPM", "溫差 K"],
                "流量 LPM": ["熱量 kW", "溫差 K"],
                "溫差 K": ["熱量 kW", "流量 LPM"],
            },
            "Kv 與壓差": {
                "Kv": ["流量 m³/h", "壓差 bar"],
                "流量 m³/h": ["閥 Kv", "壓差 bar"],
                "壓差 bar": ["流量 m³/h", "閥 Kv"],
            },
        }
        if tool in names:
            for key, label in zip(
                ["first", "second"], names[tool][self.current_mode()]
            ):
                self.field_labels[key].config(text=label)
        self.drafts[tool] = {k: v.get() for k, v in self.values.items()}
        self.hint.config(
            text=hint
            + " 切換工具會保留草稿；切換輸入組合時，有效結果可自動換算，否則請依新欄名重填。"
        )

    def calculate(self):
        for widget in self.widgets.values():
            if widget.winfo_class() == "TEntry":
                widget.configure(style="TEntry")
        args = {k: v.get() for k, v in self.values.items()}
        name = self.tool.get()
        funcs = {
            "單位轉換": q.convert_all,
            "濕空氣計算": q.psychrometric,
            "兩股混風": q.mix_air,
            "兩點空氣過程": q.air_process,
            "水量與熱量": q.water_heat,
            "水管實際流速": q.pipe_velocity,
            "Kv 與壓差": q.valve,
            "耗電與費用": q.energy_cost,
        }
        try:
            if name == "風管定寸":
                r = q.duct_selection(
                    float(args["cmh"]),
                    float(args["velocity"]),
                    float(args["ratio"]),
                    args["shape"],
                )
            elif name == "水管定寸":
                r = q.water_selection(float(args["lpm"]), float(args["vmax"]))
            else:
                call_args = dict(args)
                if name == "水量與熱量":
                    mu = float(call_args.pop("mu"))
                    if not math.isfinite(mu) or mu <= 0:
                        raise ValueError("黏度必須是大於零的有限數值")
                r = funcs[name](**call_args)
            self.result = r
            self.set_text(result_text(r))
            self.draw()
            record = dict(tool=name, values=args, summary=next(iter(args.values())))
            self.history = [record] + [x for x in self.history if x != record]
            self.history = self.history[:30]
            self.persist()
            self.recent.config(
                values=[x["tool"] + "｜" + x["summary"] for x in self.history]
            )
        except (ValueError, KeyError, TypeError, OverflowError) as e:
            self.result = None
            key = getattr(e, "field_name", None)
            label = self.field_labels.get(key)
            prefix = f"請修正「{label.cget('text')}」：" if label else "請修正："
            self.set_text(prefix + str(e))
            widget = self.widgets.get(key)
            if widget is not None and widget.winfo_class() == "TEntry":
                widget.configure(style="Invalid.TEntry")

    def draw(self):
        if not self.plot:
            return
        self.ax.clear()
        r = self.result
        tool = self.tool.get()
        states = []
        if tool == "濕空氣計算":
            states = [("P1", r)]
        elif tool == "兩股混風":
            p = float(self.values["pressure"].get())
            states = [
                (
                    "A",
                    state_trh(
                        float(self.values["t1"].get()),
                        float(self.values["rh1"].get()),
                        p,
                    ),
                ),
                (
                    "B",
                    state_trh(
                        float(self.values["t2"].get()),
                        float(self.values["rh2"].get()),
                        p,
                    ),
                ),
                ("MIX", r["state"]),
            ]
        elif tool == "兩點空氣過程":
            states = [("IN", r["inlet"]), ("OUT", r["outlet"])]
        if states:
            p = float(self.values["pressure"].get())
            lo = min(s["t"] for _, s in states) - 6
            hi = max(s["t"] for _, s in states) + 6
            temps = [lo + (hi - lo) * j / 99 for j in range(100)]
            for rh in [20, 40, 60, 80, 100]:
                values = []
                for t in temps:
                    try:
                        values.append(state_trh(t, rh, p)["w"] * 1000)
                    except ValueError:
                        values.append(math.nan)
                self.ax.plot(temps, values, color="#a7bac8", lw=0.8, label=f"{rh}% RH")
            for name, s in states:
                self.ax.scatter(s["t"], s["w"] * 1000, color="#176c85")
                self.ax.annotate(
                    name,
                    (s["t"], s["w"] * 1000),
                    xytext=(7, 7),
                    textcoords="offset points",
                )
            if len(states) == 3:
                self.ax.plot(
                    [states[0][1]["t"], states[1][1]["t"]],
                    [states[0][1]["w"] * 1000, states[1][1]["w"] * 1000],
                    "--",
                    color="#176c85",
                    label="Mixing reference",
                )
                self.ax.legend()
            if len(states) == 2:
                self.ax.annotate(
                    "",
                    (states[1][1]["t"], states[1][1]["w"] * 1000),
                    (states[0][1]["t"], states[0][1]["w"] * 1000),
                    arrowprops={"arrowstyle": "->", "color": "#176c85"},
                )
            self.ax.set(
                xlabel="Dry bulb °C",
                ylabel="g/kg dry air",
                xlim=(lo, hi),
                ylim=(0, max(s["w"] for _, s in states) * 1300 + 1),
                title=f"{p:g} kPa｜空氣狀態／兩點淨變化",
            )
            self.ax.legend(loc="upper left", fontsize=7, ncol=3)
            self.ax.grid(alpha=0.15)
        else:
            self.ax.text(
                0.5,
                0.5,
                "結果可複製；進階設計可帶入主專案",
                ha="center",
                transform=self.ax.transAxes,
            )
            self.ax.set_axis_off()
        self.fig.tight_layout()
        self.plot.draw_idle()

    def persist(self):
        try:
            atomic_text(
                self.settings,
                json.dumps(
                    dict(
                        history=self.history,
                        favorites=self.favorites,
                        drafts=self.drafts,
                    ),
                    ensure_ascii=False,
                ),
            )
        except OSError:
            self.hint.config(text="本次結果已算出；歷史紀錄無法寫入。")

    def favorite(self):
        name = self.tool.get()
        (
            self.favorites.remove(name)
            if name in self.favorites
            else self.favorites.append(name)
        )
        self.selector.config(values=self.ordered_tools())
        self.persist()

    def restore(self):
        idx = self.recent.current()
        if idx < 0:
            return
        item = self.history[idx]
        self.tool.set(item["tool"])
        self.build()
        self.suspended = True
        for k, v in item["values"].items():
            if k in self.values:
                self.values[k].set(v)
        self.suspended = False
        self.mode_previous = self.current_mode()
        self.result = None
        self.changed()
        self.calculate()

    def copy(self):
        if self.result is not None:
            self.win.clipboard_clear()
            self.win.clipboard_append(self.text.get("1.0", "end"))

    def send_to_project(self):
        if self.result is None:
            return messagebox.showinfo(
                "先計算", "請先取得目前條件的結果。", parent=self.win
            )
        r = self.result
        updates = {}
        if self.tool.get() == "濕空氣計算":
            prefix = {"夏季外氣": "oa", "冬季外氣": "ow", "室內目標": "ra"}[
                self.target.get()
            ]
            updates = {
                prefix + "_t": str(r["t"]),
                prefix + "_rh": str(r["rh"]),
                "atm_kpa": str(r["pressure_kpa"]),
            }
        elif self.tool.get() == "水量與熱量":
            prefix = self.target.get().lower()
            flow_key, unit_key, dt_key = {
                "chw": ("chw_q", "u_chw", "dt_chw"),
                "mchw": ("mchw_q", "u_mchw", "chw1_dt"),
                "dccw": ("dccw_q", "u_dccw", "dt_dccw"),
                "pcw": ("pcw_tot", "u_pcw_tot", "dt_pcw_sys"),
                "hw": ("hw_q", "u_hw", "dt_hw"),
            }[prefix]
            updates = {
                flow_key: str(r["lpm"]),
                unit_key: "LPM",
                dt_key: str(r["delta_t"]),
                prefix + "_link": "獨立輸入",
                "water_rho": self.values["rho"].get(),
                "water_cp": self.values["cp"].get(),
                "water_mu": self.values["mu"].get(),
            }
        elif self.tool.get() == "風管定寸":
            prefix = self.target.get().lower()
            updates = {
                prefix + "_q": self.values["cmh"].get(),
                "u_" + prefix: "CMH",
                "v_" + prefix: self.values["velocity"].get(),
                "duct_ratio": self.values["ratio"].get(),
                "duct_shape": self.values["shape"].get(),
            }
        else:
            return messagebox.showinfo(
                "獨立工具",
                "此工具可複製結果；沒有唯一對應的專案欄位，不自動覆寫。",
                parent=self.win,
            )
        from .workspace_view import apply_updates

        apply_updates(
            self.main_app,
            updates,
            "工程快算 → " + self.target.get() + "（來源快照）",
            self.win,
        )

    def may_close(self):
        return True

    def close(self, force=False):
        self.persist()
        if self in self.main_app.children:
            self.main_app.children.remove(self)
        self.win.destroy()
