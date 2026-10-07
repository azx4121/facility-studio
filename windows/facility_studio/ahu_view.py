from .localized_plot import translated_axes
from .localized_tk import tk
from .localized_tk import ttk
from .ahu_schema import NM_BASIC, NM_FIELDS
from .ui_common import quality_style
from .utils import state_trh
from .display_helpers import annotate_states

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    NM_HAS_PLOT = True
except ImportError:
    NM_HAS_PLOT = False


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
        canvas = tk.Canvas(frame, bg="#f1f5f9", highlightthickness=0)
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
            "<Configure>", lambda e: canvas.itemconfigure(item, width=max(780, e.width))
        )
        body.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        frame.bind(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"),
        )
        return (frame, body, canvas)

    def wheel(self, e):
        if isinstance(e.widget, (tk.Text, ttk.Treeview)):
            return
        selected = self.nb.nametowidget(self.nb.select())
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
        for item in self.table.get_children():
            self.table.delete(item)
        self.set_text("輸入已變更；不沿用舊計算書。")
        if NM_HAS_PLOT:
            translated_axes(self.ax).clear()
            self.plot.draw_idle()

    def _render_stage_results(self):
        if not self.result:
            return
        r = self.result
        s = r["winter" if self.season.get() == "冬季" else "summer"]
        failed = [k for k, v in s["checks"].items() if not v]
        self.summary.config(
            text=f"{self.season.get()}：H1 等效全電熱需求 {s['h1']['backup_electric_kw']:.1f} / 配置 {s['h1']['installed_kw']:.1f} kW；H2 {s['h2']['backup_electric_kw']:.1f} / {s['h2']['installed_kw']:.1f} kW\n水洗蒸發 {s['evap_kg_h']:.1f}／蒸汽 {s.get('steam', {}).get('kg_h', 0):.1f} kg/h；"
            + ("未達：" + "、".join(failed) if failed else "本季額定初估通過"),
            style="Error.TLabel" if failed else "Good.TLabel",
        )
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
                    f"{inlet['t']:.3f}",
                    f"{inlet['rh']:.3f}",
                    f"{outlet['t']:.3f}",
                    f"{outlet['rh']:.3f}",
                    f"{s['mass'] * (outlet['h'] - inlet['h']):.3f}",
                ),
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

    def render(self):
        self._render_stage_results()
        if self.result:
            q = self.result["quality"]
            self.summary.config(
                text=self.summary.cget("text") + "\n整機：" + q["status"],
                style=quality_style(q),
            )
