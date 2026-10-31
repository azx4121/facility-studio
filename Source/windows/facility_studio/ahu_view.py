from .localized_plot import translated_axes
from .localized_tk import tk
from .localized_tk import ttk
from .ahu_schema import NM_BASIC, NM_FIELDS
from .ui_common import quality_style
from .utils import state_trh
from .display_helpers import annotate_states
from .industrial_theme import Theme, format_number


class SCADAAirflow(tk.Canvas):
    """Responsive vector schematic; all displayed states come from the model.

    The independent MAU calculation has no room/return boundary. Those cards
    deliberately remain unspecified until a matching main-project result is
    supplied. A diagram never turns a required state into measured performance.
    """

    OA = "#10B981"
    COOLING = "#06B6D4"
    HEATING = "#F97316"
    SUPPLY = "#3B82F6"
    EXHAUST = "#F59E0B"

    def __init__(self, parent, **kwargs):
        super().__init__(parent, background=Theme.BG, highlightthickness=0,
                         height=440, **kwargs)
        self.result = self.main_result = None
        self.season = "summer"
        self.stale = False
        self._resize_job = None
        self.bind("<Configure>", self._resize, add="+")
        self.bind("<Destroy>", self._dispose, add="+")

    def _dispose(self, event):
        if event.widget is self and self._resize_job:
            self.after_cancel(self._resize_job)
            self._resize_job = None

    def _resize(self, event=None):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after_idle(self.redraw)

    def set_result(self, result, season="summer", main_result=None, stale=False):
        self.result, self.season = result, season
        self.main_result, self.stale = main_result, stale
        self.redraw()

    def redraw(self):
        self._resize_job = None
        self.delete("all")
        width = max(1, self.winfo_width())
        # Recompute every coordinate on Configure instead of repeatedly scaling
        # existing items (which also accumulates rounding and font-size errors).
        self._scale = min(width / 1120.0, max(1, self.winfo_height()) / 440.0)
        self._offset = (width - 1120 * self._scale) / 2
        if not self.result:
            self._text(560, 205, "完成計算後顯示空調氣流與狀態", 13,
                       color=Theme.MUTED)
            return
        r = self.result
        s = r[self.season]
        self._text(24, 22, "空調系統 SCADA｜" + ("冬季" if self.season == "winter" else "夏季"),
                   13, bold=True, anchor="w")
        self._text(1096, 22, "需求狀態｜待重算" if self.stale else "需求狀態｜設備能力另行校核",
                   9, color=Theme.WARNING if self.stale else Theme.MUTED, anchor="e")

        # MAU equipment sequence follows the actual selected H1/C1 ordering.
        self._rounded(175, 111, 941, 218, fill=Theme.CARD, outline=Theme.BORDER)
        self._text(195, 128, "MAU 外氣處理箱", 10, bold=True, anchor="w")
        stages = [("H1", self.HEATING), ("C1", self.COOLING)]
        if r["inputs"]["sequence"].startswith("C1"):
            stages.reverse()
        stages += [("水洗／蒸汽", self.COOLING), ("C2", self.COOLING),
                   ("H2", self.HEATING), ("EC／HEPA", self.SUPPLY)]
        self._line(30, 177, 180, 177, color=self.OA, arrow=True)
        self._text(86, 201, "外氣 OA", 10, color=self.OA)
        for index, (label, color) in enumerate(stages):
            x = 192 + index * 122
            if index:
                self._line(x - 12, 177, x + 4, 177, color=self.OA, arrow=True)
            self._rounded(x, 148, x + 106, 205, fill="#F8FAFC", outline=color)
            self._text(x + 53, 177, label, 10, bold=True, color=color)
            if label.startswith(("H1", "H2", "C1", "C2")):
                tag = label.lower()
                load = s[tag].get("air_kw", 0)
                self._text(x + 53, 194, format_number(load, 1) + " kW", 8, color=Theme.MUTED)
        self._line(941, 177, 1042, 177, 1042, 255,
                   color=self.SUPPLY, arrow=True)

        main = self.main_result
        room = main.get("room") if main else None
        # Main-project return uses the declared well-mixed room state, and is
        # explicitly labelled as such, rather than presented as a measurement.
        self._state_card(24, 47, "外氣入口 OA", s.get("oa"), self.OA)
        self._state_card(296, 47, "MAU 出風 SA", s.get("sa"), self.SUPPLY)
        self._state_card(568, 47, "室內設計狀態", room, self.SUPPLY)
        self._state_card(840, 47, "回風 RA（室內模型）" if room else "回風 RA", room, self.COOLING)

        self._rounded(814, 258, 1088, 375, fill=Theme.CARD, outline=Theme.BORDER)
        self._text(951, 279, "天花板靜壓箱／FFU", 11, bold=True, color=self.SUPPLY)
        self._line(838, 302, 1065, 302, color=self.SUPPLY)
        for x in (862, 950, 1038):
            self._rounded(x - 25, 290, x + 25, 315, fill="#DBEAFE", outline=self.SUPPLY)
            self._line(x, 317, x, 339, color=self.SUPPLY, arrow=True)
        self._text(951, 357, "潔淨室／送風區", 11, bold=True)
        self._line(815, 348, 714, 348, color=self.COOLING, arrow=True)
        self._rounded(551, 317, 708, 376, fill=Theme.CARD, outline=self.COOLING)
        self._text(630, 336, "DCC 乾冷盤管", 11, bold=True, color=self.COOLING)
        self._text(630, 359, "室內回風循環", 9, color=Theme.MUTED)
        self._line(551, 348, 490, 348, 490, 245, 952, 245, 952, 258,
                   color=self.COOLING, arrow=True)
        self._text(615, 263, "循環回風 RA", 9, color=self.COOLING)
        self._line(856, 375, 856, 406, 1030, 406, color=self.EXHAUST, arrow=True)
        self._text(1040, 406, "排氣 EA", 10, color=self.EXHAUST, anchor="w")
        self._text(24, 303, "流向色彩", 10, bold=True, anchor="w")
        for j, (name, color) in enumerate((("OA 外氣", self.OA), ("CC／DCC 冷卻", self.COOLING),
                                          ("加熱／再熱", self.HEATING), ("SA／FFU 送風", self.SUPPLY),
                                          ("EA 排氣", self.EXHAUST))):
            x, y = 24 + (j % 2) * 183, 329 + (j // 2) * 26
            self._line(x, y, x + 24, y, color=color)
            self._text(x + 34, y, name, 9, anchor="w", color=Theme.MUTED)
        self._text(24, 421, "下游示意，未納入單機熱濕平衡；室內／回風未連動時不填入推測值。",
                   9, color=Theme.MUTED, anchor="w")

    def _xy(self, x, y):
        return self._offset + x * self._scale, y * self._scale

    def _line(self, *points, color, arrow=False):
        coords = []
        for j in range(0, len(points), 2):
            coords.extend(self._xy(points[j], points[j + 1]))
        return self.create_line(*coords, fill=color, width=max(1, self._scale * 3),
                                arrow="last" if arrow else "none",
                                arrowshape=tuple(v * self._scale for v in (9, 11, 4)),
                                joinstyle="round")

    def _rounded(self, x1, y1, x2, y2, fill, outline, radius=9):
        points = (x1 + radius, y1, x2 - radius, y1, x2, y1,
                  x2, y1 + radius, x2, y2 - radius, x2, y2,
                  x2 - radius, y2, x1 + radius, y2, x1, y2,
                  x1, y2 - radius, x1, y1 + radius, x1, y1)
        coords = []
        for j in range(0, len(points), 2):
            coords.extend(self._xy(points[j], points[j + 1]))
        return self.create_polygon(*coords, smooth=True, splinesteps=16,
                                   fill=fill, outline=outline, width=1)

    def _text(self, x, y, value, size=10, bold=False, color=None, anchor="center", numeric=False):
        return self.create_text(*self._xy(x, y), text=value, anchor=anchor,
                                fill=color or Theme.TEXT,
                                font=(Theme.mono if numeric else Theme.family,
                                      max(7, round(size * self._scale)),
                                      "bold" if bold else "normal"))

    def _state_card(self, x, y, title, state, color):
        self._rounded(x, y, x + 256, y + 53, fill=Theme.CARD, outline=Theme.BORDER)
        self._text(x + 11, y + 14, title, 9, bold=True, color=color, anchor="w")
        if state and all(key in state for key in ("t", "rh", "h")):
            value = f"{state['t']:.1f} °C | {state['rh']:.1f} %RH | {state['h']:.1f} kJ/kg"
        else:
            value = "未提供｜— °C | — %RH | — kJ/kg"
        self._text(x + 11, y + 36, value, 9, anchor="w", numeric=True)

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    NM_HAS_PLOT = True
except ImportError:
    NM_HAS_PLOT = False


def prepare_ahu_plot_fonts():
    """Standalone AHU windows need the same CJK fallback as the workbench."""
    if not NM_HAS_PLOT:
        return
    from matplotlib import font_manager, rcParams
    names = {font.name for font in font_manager.fontManager.ttflist}
    for name in (Theme.family, "Microsoft JhengHei", "Noto Sans CJK TC",
                 "Noto Sans CJK JP", "PingFang TC", "Arial Unicode MS"):
        if name in names:
            rcParams["font.family"] = [name]
            break
    rcParams["axes.unicode_minus"] = False


class AHUView:

    def reveal(self, key):
        self.nb.select(0)
        self.win.update_idletasks()
        row = self.rows[key]
        self.input_canvas.yview_moveto(
            max(
                0,
                (row.winfo_rooty() - self.input_body.winfo_rooty() - 25)
                / max(1, self.input_body.winfo_height()),
            )
        )
        self.widgets[key].focus_set()

    def scroll_tab(self, title):
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text=title)
        canvas = tk.Canvas(frame, bg=Theme.BG, highlightthickness=0)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
        hs.pack(side="bottom", fill="x")
        canvas.configure(xscrollcommand=hs.set)
        canvas.pack(side="left", fill="both", expand=True)
        vs = ttk.Scrollbar(frame, command=canvas.yview)
        vs.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=vs.set)
        body = ttk.Frame(canvas, padding=12)
        item = canvas.create_window(0, 0, window=body, anchor="nw")
        canvas.bind(
            "<Configure>", lambda e: canvas.itemconfigure(item, width=max(1, e.width))
        )
        body.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        frame.bind(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"),
        )
        return (frame, body, canvas)

    def design_tab(self):
        """Keep the established notebook API while exposing results beside inputs."""
        from .industrial_theme import KPIFrame, ResultTable, ScrollableFrame
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text="1 設計條件")
        split = ttk.Panedwindow(frame, orient="horizontal")
        split.pack(fill="both", expand=True)
        inputs = ttk.Frame(split, width=490)
        dashboard_panel = ScrollableFrame(split)
        dashboard = dashboard_panel.body
        split.add(inputs, weight=4)
        split.add(dashboard_panel, weight=5)
        canvas = tk.Canvas(inputs, bg=Theme.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(inputs, command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        body = ttk.Frame(canvas, padding=(10, 8))
        item = canvas.create_window(0, 0, window=body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=max(1, e.width)))
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        ttk.Label(dashboard, text="單機核心設計量", style="Ahu.Title.TLabel").pack(fill="x", pady=(0, 8))
        self.dashboard_summary = ttk.Label(dashboard, text="", style="Ahu.Card.TLabel", wraplength=560)
        self.dashboard_summary.pack(fill="x", pady=(0, 12))
        dashboard.bind("<Configure>", lambda e: self.dashboard_summary.configure(wraplength=max(200, e.width - 40)))
        self.kpis = KPIFrame(dashboard)
        self.kpis.pack(fill="x", pady=(0, 12))
        ttk.Label(dashboard, text="設備需求／容量檢核", style="Ahu.Section.TLabel").pack(fill="x", pady=(0, 6))
        self.design_table = ResultTable(dashboard)
        self.design_table.pack(fill="both", expand=True)
        ttk.Button(dashboard, text="查看 SCADA 流向與逐段狀態", command=lambda: self.nb.select(1)).pack(fill="x", pady=(12, 0))
        # Set the sash only after mapping; Tk 8.5 can discard a position applied
        # to an unmapped pane and leave the entire input pane at zero width.
        frame.after(150, lambda: split.sashpos(0, int(max(800, frame.winfo_width()) * .44)) if frame.winfo_exists() else None)
        return frame, body, canvas

    def wheel(self, e):
        if isinstance(e.widget, (tk.Text, ttk.Treeview)):
            return
        selected = self.nb.nametowidget(self.nb.select())
        if self.nb.index(self.nb.select()) == 0:
            # Do not steal Treeview scrolling from the dashboard on the right.
            if str(e.widget).startswith(str(self.input_canvas)):
                step = -1 if getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0 else 1
                self.input_canvas.yview_scroll(step, "units")
                return "break"
            return
        canvas = next(
            (w for w in selected.winfo_children() if isinstance(w, tk.Canvas)), None
        )
        if canvas:
            step = -1 if getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0 else 1
            canvas.yview_scroll(step, "units")
            return "break"

    def visibility(self):
        from .field_state import ahu_inactive
        from .ahu_schema import NM_DEFAULTS, NM_CONTROL_NOTES

        inputs = self.snapshot()
        inactive = ahu_inactive(inputs)
        single_coil = all(inputs[s + "_c1_mode"] == "旁通" for s in ("summer", "winter"))
        seasonal = inputs["target_mode"] == "主案分季需求"
        needed = set()
        if seasonal:
            needed.update(
                s + suffix
                for s in ["summer", "winter"]
                for suffix in ["_sa_t", "_sa_rh", "_flow"]
            )
        for key in inputs:
            if (
                key.startswith(("summer_", "winter_"))
                and key.endswith(("_t", "_rh"))
                and key not in inactive
            ):
                needed.add(key)
        if "蒸汽" in inputs["humidifier"]:
            needed.update(["steam_capacity", "steam_kw", "steam_water"])
        if "電極" in inputs["humidifier"]:
            needed.update(["steam_conductivity", "steam_cond_min", "steam_cond_max"])
        for tag in ["h1", "h2"]:
            if tag + "_water_mode" not in inactive:
                needed.add(tag + "_water_mode")
                needed.update(
                    tag + "_hw_" + x
                    for x in ["in", "out", "approach"]
                    if tag + "_hw_" + x not in inactive
                )
        for key, widget in self.widgets.items():
            state = (
                "disabled"
                if key in inactive
                else (
                    "readonly"
                    if isinstance(NM_FIELDS[key]["limit"], list)
                    else "normal"
                )
            )
            widget.configure(state=state)
            if hasattr(self, "adoption_notes"):
                note = self.adoption_notes[key]
                note.configure(
                    text=(
                        ("保留設定，未採用：" + inactive[key])
                        if key in inactive
                        else ""
                    )
                )
                if key in inactive:
                    note.grid()
                else:
                    note.grid_remove()
        if not hasattr(self, "flow_basis_display"):
            self.flow_basis_display = tk.StringVar(self.win)
        if seasonal:
            self.flow_basis_display.set("各季送風狀態（固定採用）")
            self.widgets["flow_basis"].configure(textvariable=self.flow_basis_display)
        else:
            self.widgets["flow_basis"].configure(textvariable=self.vars["flow_basis"])
        for box, keys in self.boxes:
            for key in reversed(keys):
                visible = (
                    self.advanced.get()
                    or ((key in NM_BASIC or key in needed) and key not in inactive)
                    or key == "flow_basis"
                )
                if single_coil and key in ("c1_in", "c1_out", "c1_adp", "c1_rt", "c1_t", "dp_c1"):
                    visible = False
                row = self.rows[key]
                if not visible:
                    row.pack_forget()
                elif not row.winfo_manager():
                    later = keys[keys.index(key) + 1 :]
                    anchor = next(
                        (self.rows[k] for k in later if self.rows[k].winfo_manager()),
                        None,
                    )
                    opts = {"fill": "x", "pady": 4}
                    if anchor:
                        opts["before"] = anchor
                    row.pack(**opts)
        modified = [
            NM_FIELDS[k]["label"] + "=" + inputs[k]
            for k in inputs
            if k not in inactive
            and not self.rows[k].winfo_manager()
            and inputs[k] != NM_DEFAULTS[k]
        ]
        if hasattr(self, "adopted_summary"):
            self.adopted_summary.config(
                text=(
                    ("基本畫面外仍採用：" + "；".join(modified))
                    if modified
                    else "進階初估值已帶入；停用欄位只保留草稿，不參與該功能的驗證。"
                )
            )
        if hasattr(self, "control_notes"):
            self.control_notes.config(
                text=NM_CONTROL_NOTES.replace("8 台 EC", inputs["fan_qty"] + " 台 EC")
            )

    def set_text(self, s):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", s)
        self.text.configure(state="disabled")

    def clear_output(self):
        if getattr(self, "last_good_result", None):
            from .reports import nm_report
            self.set_text("【上次有效需求結果／待重算，不能匯出】\n\n" + nm_report(self.last_good_result))
            self._render_dashboard(self.last_good_result, stale=True)
            if hasattr(self, "scada"):
                self.scada.set_result(self.last_good_result,
                                      "winter" if self.season.get() == "冬季" else "summer",
                                      stale=True)
            if NM_HAS_PLOT and getattr(self, "stale_plot_label", None) is None:
                self.stale_plot_label = translated_axes(self.ax).text(.5, .5, "上次有效需求結果｜待重算", transform=self.ax.transAxes, ha="center", va="center", fontsize=14, color="#b45309", bbox=dict(facecolor="white", alpha=.9))
                self.plot.draw_idle()
            return
        for item in self.table.get_children():
            self.table.delete(item)
        self.set_text("輸入已變更；不沿用舊計算書。")
        if hasattr(self, "kpis"):
            self.kpis.set_cards([])
            self.design_table.set_rows([])
            self.dashboard_summary.config(text="完成計算後顯示設備需求與容量檢核。")
        if hasattr(self, "scada"):
            self.scada.set_result(None)
        if NM_HAS_PLOT:
            translated_axes(self.ax).clear()
            self.plot.draw_idle()

    def _render_stage_results(self):
        if not self.result:
            return
        r = self.result
        s = r["winter" if self.season.get() == "冬季" else "summer"]
        self._render_dashboard(r)
        if hasattr(self, "scada"):
            main = getattr(getattr(self, "main_app", None), "result", None)
            # Only use a fresh linked main-project room state, never an unrelated
            # independent project's state merely because its window is open.
            linked = r["inputs"].get("linked_main_hash", "尚未連動")
            if not main or linked == "尚未連動" or linked != self.main_app.boundary_hash():
                main = None
            self.scada.set_result(r, "winter" if self.season.get() == "冬季" else "summer", main)
        failed = [k for k, v in s["checks"].items() if not v]
        self.summary.config(
            text=f"{self.season.get()}：H1 等效全電熱需求 {format_number(s['h1']['backup_electric_kw'], 1)} / 配置 {format_number(s['h1']['installed_kw'], 1)} kW；H2 {format_number(s['h2']['backup_electric_kw'], 1)} / {format_number(s['h2']['installed_kw'], 1)} kW\n水洗蒸發 {format_number(s['evap_kg_h'], 1)}／蒸汽 {format_number(s.get('steam', {}).get('kg_h', 0), 1)} kg/h；"
            + ("未達：" + "、".join(failed) if failed else "本季額定初估通過"),
            style="Error.TLabel" if failed else "Good.TLabel",
        )
        factor = 1 + float(r["inputs"]["sf"]) / 100
        from .utils import US_RT_KW
        capacity_lines = []
        for tag in ("c1", "c2"):
            need = s[tag]["water_kw"] * factor / US_RT_KW
            rating = float(r["inputs"][tag + "_rt"])
            capacity_lines.append(tag.upper() + f" 冷量需求 {format_number(need, 1)}／配置 {format_number(rating, 1)} RT；缺口 {format_number(max(0, need - rating), 1)} RT")
        self.summary.config(text=self.summary.cget("text") + "\n" + "；".join(capacity_lines) + "\n點位是滿足需求的目標；容量不足時，不能當成實際可達出風。")
        for item in self.table.get_children():
            self.table.delete(item)
        for j, ((_, inlet), (name, outlet)) in enumerate(
            zip(s["nodes"], s["nodes"][1:]), 1
        ):
            self.table.insert(
                "",
                "end",
                values=(
                    f"P{j} {name}",
                    format_number(inlet['t'], 3),
                    format_number(inlet['rh'], 3),
                    format_number(outlet['t'], 3),
                    format_number(outlet['rh'], 3),
                    format_number(s['mass'] * (outlet['h'] - inlet['h']), 3),
                ),
                tags=("even" if j % 2 == 0 else "odd",),
            )
        if not NM_HAS_PLOT:
            return
        translated_axes(self.ax).clear()
        states = [st for _, st in s["nodes"]]
        lo = min((st["t"] for st in states)) - 4
        hi = max((st["t"] for st in states)) + 5
        ymax = max((st["w"] for st in states)) * 1200 + 2
        p = float(r["inputs"]["p"])
        temps = [lo + (hi - lo) * j / 119 for j in range(120)]
        for rh in [10, 30, 50, 70, 90, 100]:
            translated_axes(self.ax).plot(
                temps,
                [state_trh(t, rh, p)["w"] * 1000 for t in temps],
                color="#9cb4c5",
                alpha=0.4,
                lw=1,
            )
        groups = {}
        for j, (_, st) in enumerate(s["nodes"]):
            groups.setdefault((round(st["t"], 5), round(st["w"] * 1000, 5)), []).append(
                f"P{j}"
            )
        for (t, w), names in groups.items():
            translated_axes(self.ax).scatter(t, w, color="#134b70", zorder=4, s=25)
        for a, b in zip(states, states[1:]):
            if abs(a["t"] - b["t"]) + abs(a["w"] - b["w"]) * 1000 < 1e-06:
                continue
            color = (
                "#21806b"
                if b["w"] > a["w"] + 1e-08
                else "#d47925" if b["h"] > a["h"] + 1e-08 else "#176e9e"
            )
            translated_axes(self.ax).annotate(
                "",
                (b["t"], b["w"] * 1000),
                (a["t"], a["w"] * 1000),
                arrowprops={"arrowstyle": "-|>", "color": color, "lw": 2},
            )
        translated_axes(self.ax).text(
            0.01,
            0.98,
            "灰線 RH 10 / 30 / 50 / 70 / 90 / 100%｜橘：加熱；藍：冷卻；綠：加濕",
            transform=translated_axes(self.ax).transAxes,
            va="top",
            fontsize=8,
            color="#456273",
        )
        translated_axes(self.ax).set(
            xlim=(lo, hi),
            ylim=(0, ymax),
            xlabel="乾球 °C",
            ylabel="含濕比 g/kg 乾空氣",
            title=self.season.get() + f"需求流程｜{p:g} kPa｜P0 外氣；其餘點號對應上表",
        )
        translated_axes(self.ax).grid(alpha=0.15)
        self.fig.tight_layout()
        annotate_states(self.ax, groups, fontsize=8)
        self.plot.draw_idle()

    def _render_dashboard(self, r, stale=False):
        if not hasattr(self, "kpis"):
            return
        s = r["winter" if self.season.get() == "冬季" else "summer"]
        q = r.get("quality", {})
        status = "待重算" if stale else q.get("status", "需求值")
        tone = "warning" if stale else "danger" if q.get("failed") else "warning" if q.get("pending") else "success"
        cooling_kw = s["c1"]["water_kw"] + s["c2"]["water_kw"]
        seasonal = r["inputs"].get("target_mode") == "主案分季需求"
        flow_key = ("winter_flow" if self.season.get() == "冬季" else "summer_flow") if seasonal else "flow"
        cards = [("MAU 指定風量", float(r["inputs"][flow_key]), "CMH"),
                 ("冷卻盤管需求", cooling_kw, "kW"),
                 ("H1 加熱需求", s["h1"]["air_kw"], "kW"),
                 ("H2 再熱需求", s["h2"]["air_kw"], "kW"),
                 ("EC 風機額定電力", r["fan_installed_kw"], "kW"),
                 ("水洗／蒸汽加濕", s["evap_kg_h"] + s.get("steam", {}).get("kg_h", 0), "kg/h")]
        self.kpis.set_cards([dict(title=title, value=format_number(value, 1), unit=unit,
                                 status=status, tone=tone) for title, value, unit in cards])
        rows = []
        for tag in ("c1", "c2"):
            need = s[tag]["water_kw"] * (1 + float(r["inputs"]["sf"]) / 100)
            from .utils import US_RT_KW
            rating = float(r["inputs"][tag + "_rt"]) * US_RT_KW
            rows.extend([(tag.upper() + " 計算冷量", format_number(need, 1), "kW", "需求含容量餘裕"),
                         (tag.upper() + " 已配置容量", format_number(rating, 1), "kW", "通過" if rating + 1e-6 >= need else "容量未達")])
        rows.extend([("EC 風機配置", r["inputs"]["fan_qty"], "台", "待廠商風機曲線"),
                     ("風機需求電力", format_number(r["fan_required_kw"], 1), "kW", "需求初估" if r["pressure_complete"] else "壓差資料待補"),
                     ("總選用設備電力", format_number(r["installed_electric_kw"], 1), "kW", "額定配置"),
                     ("熱量守恆殘差", format_number(s["energy_residual_kw"], 6), "kW", "通過")])
        self.design_table.set_rows(rows)
        self.dashboard_summary.config(text=("上次有效需求結果｜待重算，不能匯出。" if stale else
            "計算需求值與已配置容量分開顯示。\n" + self.season.get() + "：" + status + "；狀態點代表需求目標。"))

    def render(self):
        self._render_stage_results()
        if self.result:
            q = self.result["quality"]
            self.summary.config(
                text=self.summary.cget("text") + "\n整機：" + q["status"],
                style=quality_style(q),
            )
