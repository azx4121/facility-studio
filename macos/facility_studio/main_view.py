from .localized_plot import translated_axes
from pathlib import Path
from .localized_tk import tk
from tkinter import font as tkfont
from .localized_tk import ttk
from .engine import wetbulb
from .display_helpers import duct_dimensions, annotate_states
from .schema import (
    BASIC_KEYS,
    DEFAULTS,
    FIELDS,
    FIELD_HELP,
    GROUPS,
    PAGES,
    PD_FIELDS,
    PD_KEYS,
    REFERENCE_KEYS,
)
from .utils import dewpoint, state_trh

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib import font_manager, rcParams

    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False


class ScrollPage(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, bg="#f1f5f9", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vy = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        vy.grid(row=0, column=1, sticky="ns")
        hx = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        hx.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=vy.set, xscrollcommand=hx.set)
        self.body = ttk.Frame(self.canvas, padding=18)
        self.body.columnconfigure(0, weight=1)
        self.win = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.minimum_body_width = 700
        self._scroll_bounds = None
        self._body_width = None
        self.body.bind("<Configure>", self.sync_scroll_region)
        self.canvas.bind("<Configure>", self.fit_body)

    def sync_scroll_region(self, event=None):
        bounds = self.canvas.bbox("all")
        if bounds != self._scroll_bounds:
            self._scroll_bounds = bounds
            self.canvas.configure(scrollregion=bounds or (0, 0, 0, 0))

    def fit_body(self, event):
        width = max(self.minimum_body_width, event.width)
        if width != self._body_width:
            self._body_width = width
            self.canvas.itemconfigure(self.win, width=width)

    def reveal(self, widget):
        self.update_idletasks()
        self.canvas.yview_moveto(
            max(
                0,
                (widget.winfo_rooty() - self.body.winfo_rooty() - 60)
                / max(1, self.body.winfo_height()),
            )
        )


class MainView:

    def update_visibility(self):
        advanced = self.view_mode.get() == "進階模式"
        for key, line in self.form_rows.items():
            visible = advanced or key in BASIC_KEYS
            if (
                not advanced
                and str(self.widgets[key].cget("state")) == "disabled"
                and (key != "upw_res")
            ):
                visible = False
            (line.grid if visible else line.grid_remove)()
        for box, keys in self.form_boxes:
            visible = any((self.form_rows[k].winfo_manager() for k in keys))
            if not visible:
                box.pack_forget()
            elif not box.winfo_manager():
                order = self.pack_order[FIELDS[keys[0]]["page"]]
                later = order[order.index(box) + 1 :]
                anchor = next((w for w in later if w.winfo_manager() == "pack"), None)
                opts = {"fill": "x", "pady": (0, 16)}
                if anchor:
                    opts["before"] = anchor
                box.pack(**opts)
        if self.pd_widgets:
            if advanced and (not self.grid.winfo_manager()):
                self.grid.pack(fill="x", before=self.pd_hint)
            elif not advanced:
                self.grid.pack_forget()
            if self.result:
                d = self.result["pressure"][self.selected_pd]
                flow = d["flow_m3s"] * (
                    60000 if self.selected_pd in PD_KEYS[:5] else 3600
                )
                unit = "LPM" if self.selected_pd in PD_KEYS[:5] else "CMH"
                pressure = (
                    f"{d['total_pa'] / 1000:,.2f} kPa / {d['head_m']:.2f} m"
                    if self.selected_pd in PD_KEYS[:5]
                    else f"{d['total_pa']:,.1f} Pa / {d['mmAq']:.2f} mmAq"
                )
                self.pd_quick.config(
                    text=self.pressure_geometry(self.selected_pd)
                    + f"\n{self.selected_pd}：{flow:,.1f} {unit}，流速 {d['velocity_mps']:.2f} m/s\n{pressure}｜"
                    + (
                        "含輸入設備壓差"
                        if d["equipment_included"]
                        else "管路小計，未含設備"
                    )
                    + (f"｜軸功率 {d['shaft_kw']:.3f} kW" if advanced else "")
                )
            else:
                self.pd_quick.config(text="等待目前輸入通過檢核")
            simple = self.pd[self.selected_pd]["estimate_mode"].get() == "簡易估算"
            essentials = {
                "estimate_mode",
                "length_m",
                "equipment_drop",
                "unit",
                "boundary",
                "static_m",
            }
            if simple:
                essentials.update({"allowance_pct", "equipment_known"})
            for key, line in self.pd_rows.items():
                visible = key in essentials if simple else key != "allowance_pct"
                if simple and advanced:
                    visible = visible or key in ("manual_id_mm", "efficiency")
                if (
                    key in ("boundary", "static_m")
                    and self.selected_pd not in PD_KEYS[:5]
                ):
                    visible = False
                if (
                    key == "static_m"
                    and self.pd[self.selected_pd]["boundary"].get() != "開式系統"
                ):
                    visible = False
                if (
                    key == "equipment_drop"
                    and simple
                    and (
                        self.pd[self.selected_pd]["equipment_known"].get()
                        != "已知設備壓差"
                    )
                ):
                    visible = False
                (line.grid if visible else line.grid_remove)()
            self.pd_hint.config(
                text=(
                    "簡易初估：未提供設備壓差時，表格只列管路小計。"
                    if simple
                    else "沿用詳細管件／設備設定；切換簡易不會刪除詳細設定。"
                )
                + f"  效率採 {self.pd[self.selected_pd]['efficiency'].get()}；流量由各系統連動。"
            )
        if hasattr(self, "assumption_labels"):
            for page, label in self.assumption_labels.items():
                keys = sorted(
                    k
                    for k in FIELDS
                    if FIELDS[k]["page"] == page
                    and not self.form_rows[k].winfo_manager()
                    and str(self.widgets[k].cget("state")) != "disabled"
                )
                modified = [
                    FIELDS[k]["label"] + "=" + self.variables[k].get()
                    for k in keys
                    if self.variables[k].get() != DEFAULTS[k]
                ]
                label.config(
                    text=(
                        (
                            "畫面外仍採用的自訂條件：" + "；".join(modified)
                            if modified
                            else "本頁初估係數已帶入；可按「進階模式」查看數值。"
                        )
                        if keys
                        else ""
                    )
                )
        if hasattr(self, "ref_button"):
            self.ref_button.configure(
                state=(
                    "normal"
                    if any((FIELDS[k]["page"] == self.current for k in REFERENCE_KEYS))
                    else "disabled"
                )
            )
        if hasattr(self, "undo_button"):
            self.undo_button.configure(
                state="normal" if self.undo_project else "disabled"
            )

    def pressure_geometry(self, key):
        if not self.result:
            return ""
        d = (
            self.result["water"][key]
            if key in PD_KEYS[:5]
            else self.result["ducts"][key]
        )
        manual = self.pd[key]["manual_id_mm"].get()
        source = "手填內徑" if float(manual) > 0 else "流量自動定寸"
        if key in PD_KEYS[:5]:
            return f"採用 {d['runs']} 支並聯 × ID {d['id_mm']:.1f} mm｜{source}"
        return "採用 " + duct_dimensions(d) + "｜" + source

    def build_forms(self):
        for page in range(7):
            ttk.Label(
                self.pages[page].body,
                text=[
                    "設定外氣與室內目標；夏季負荷摘要及分季流程圖各自標明計算工況。",
                    "先選系統與區域循環需求；設備容量為需求候選，各季送風量仍需滿足熱濕平衡。",
                    "設備熱、照明與人員分開計算；潛熱只填散入室內的製程水氣，避免重複計入外氣。",
                    "標準流量先換算管內實際流量；壓力及流速可於進階模式逐路設定。PV 壓力為絕壓。",
                    "kW 是輸入電力，HP 是機械輸出；候選線徑需再核對敷設與保護條件。",
                    "名目風量先加設計餘裕，再定寸；管形與寬高比目前共用於所有排氣系統。",
                    "連動負荷時以熱量與 ΔT 反算水量；手填水量保留但不採用。水物性共用於全部水迴路。",
                ][page],
                wraplength=650,
                style="Muted.TLabel",
            ).pack(fill="x", pady=(0, 10))
        groups = sorted(
            enumerate(GROUPS),
            key=lambda t: (t[1][0], 0 if "latent_mode" in t[1][2] else 1, t[0]),
        )
        for _, (page, title, keys) in groups:
            if not keys:
                continue
            body = self.pages[page].body
            box = ttk.LabelFrame(body, text=title, padding=14)
            box.pack(fill="x", pady=(0, 16))
            box.columnconfigure(0, weight=1)
            self.form_boxes.append((box, keys))
            for row, key in enumerate(keys):
                f = FIELDS[key]
                line = ttk.Frame(box)
                line.grid(row=row, column=0, sticky="ew", pady=4)
                line.columnconfigure(1, weight=1)
                ttk.Label(line, text=f["label"]).grid(
                    row=0, column=0, sticky="w", padx=(0, 12)
                )
                if f["options"] == ["1", "0"]:
                    widget = ttk.Checkbutton(
                        line,
                        text="啟用",
                        variable=self.variables[key],
                        onvalue="1",
                        offvalue="0",
                    )
                elif f["options"]:
                    widget = ttk.Combobox(
                        line,
                        textvariable=self.variables[key],
                        values=f["options"],
                        state="readonly",
                        width=28,
                    )
                else:
                    widget = ttk.Entry(line, textvariable=self.variables[key], width=26)
                if f["options"]:
                    widget.bind("<MouseWheel>", self.wheel)
                widget.grid(row=0, column=1, sticky="ew")
                ttk.Label(line, text=f["unit"], foreground="#6b7c8d").grid(
                    row=0, column=2, sticky="w", padx=(10, 0)
                )
                self.widgets[key] = widget
                self.form_rows[key] = line
                if key in FIELD_HELP:
                    ttk.Label(
                        line, text=FIELD_HELP[key], wraplength=610, style="Muted.TLabel"
                    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 0))
            if page == 1 and ("en_ach_A" in keys or "en_ach_B" in keys):
                z = "A" if "en_ach_A" in keys else "B"
                ttk.Button(
                    box,
                    text="帶入此等級 ACH／壓差參考值",
                    command=lambda zone=z: self.preset(zone),
                ).grid(row=len(keys), column=0, sticky="w", pady=7)
            if "latent_mode" in keys:
                ttk.Label(
                    box,
                    text="潛熱＝水氣增加帶來的除濕負荷，並非一般機台發熱。\n人員會自動帶入；製程只算散入室內的水氣。\n採 2501 kJ/kg：1 kg/h ≈ 0.695 kW；1 kW ≈ 1.439 kg/h。",
                    wraplength=620,
                    style="Muted.TLabel",
                ).grid(row=len(keys), column=0, sticky="w", pady=7)
                ttk.Label(
                    box,
                    textvariable=self.latent_text,
                    wraplength=620,
                    style="Good.TLabel",
                ).grid(row=len(keys) + 1, column=0, sticky="w", pady=6)
        notes = {
            1: "自動參考：一／二段 ADP 裕度 1 K、露點裕度 1 K；目前值可在進階檢視。MAU 處理外氣，FFU／DCC 為室內循環；FCU／RCU 採入口混合等效模型。",
            2: "利用係數 U=0.6、維護係數 M=0.8、人員顯熱 75 W／潛熱 55 W 是初估起點，實際採用值在進階欄位。未知製程產濕不當成已確認零產濕。",
            3: "PV 三種單位皆為絕壓，切換會換算數字。CMH 在此為標準狀態流量。特氣／PV 僅作流速初估；材質及真空性能需另核。",
            4: "kW 是電力輸入；HP 是軸輸出。切換單位會自動換算並保留原負荷。原專案線表僅初估，接地及保護仍需覆核。",
            5: "已帶入各類排氣初估風速；進階可修改實際上限、物性及風量餘裕。",
            6: "水量可依負荷自動算。UPW／DI／RO 電阻率以 25°C 參考值帶入；水型名稱不能保證水質。自訂規格可覆寫；TOC／DO 仍依製程確認。",
        }
        self.assumption_labels = {}
        for page in range(7):
            if page in notes:
                ttk.Label(
                    self.pages[page].body,
                    text=notes[page],
                    wraplength=650,
                    style="Muted.TLabel",
                ).pack(fill="x", pady=8)
            label = ttk.Label(
                self.pages[page].body, text="", wraplength=650, style="Muted.TLabel"
            )
            label.pack(fill="x", pady=6)
            self.assumption_labels[page] = label
            if page:
                label = ttk.Label(
                    self.pages[page].body,
                    text="等待計算",
                    wraplength=650,
                    style="Good.TLabel",
                    justify="left",
                )
                label.pack(fill="x", pady=12)
                self.result_labels[page] = label

    def build_pd(self):
        b = self.pages[7].body
        ttk.Label(
            b,
            text="先選系統，再填最不利路徑長度。流量、管徑與摩擦自動帶入。",
            wraplength=650,
        ).pack(anchor="w", pady=(0, 10))
        self.grid = ttk.Treeview(
            b, columns=("flow", "v", "dp", "power"), show="tree headings", height=10
        )
        self.grid.heading("#0", text="系統")
        self.grid.column("#0", width=80, stretch=False)
        for k, title in [
            ("flow", "流量 LPM/CMH"),
            ("v", "流速 m/s"),
            ("dp", "壓差 Pa"),
            ("power", "範圍"),
        ]:
            self.grid.heading(k, text=title)
            self.grid.column(k, width=135, anchor="e")
        self.pd_choice = tk.StringVar(value="MCHW")
        pick = ttk.Frame(b)
        pick.pack(fill="x", pady=6)
        ttk.Label(pick, text="選擇系統").pack(side="left")
        chooser = ttk.Combobox(
            pick,
            textvariable=self.pd_choice,
            values=PD_KEYS,
            state="readonly",
            width=12,
        )
        chooser.pack(side="left", padx=10)
        chooser.bind(
            "<<ComboboxSelected>>",
            lambda e: (self.grid.selection_set(self.pd_choice.get()), self.select_pd()),
        )
        self.pd_quick = ttk.Label(b, text="", wraplength=650, style="Good.TLabel")
        self.pd_quick.pack(fill="x", pady=8)
        self.grid.pack(fill="x")
        self.grid.bind("<<TreeviewSelect>>", self.select_pd)
        for k in PD_KEYS:
            self.grid.insert("", "end", iid=k, text=k, values=("—", "—", "—", "—"))
        self.pd_hint = ttk.Label(b, text="", wraplength=650, style="Muted.TLabel")
        self.pd_hint.pack(fill="x", pady=8)
        self.pd_box = ttk.LabelFrame(b, text="MCHW 最不利路徑", padding=14)
        self.pd_box.pack(fill="x", pady=8)
        self.pd_box.columnconfigure(0, weight=1)
        self.selected_pd = "MCHW"
        for row, (key, label, unit) in enumerate(PD_FIELDS):
            line = ttk.Frame(self.pd_box)
            line.grid(row=row, column=0, sticky="ew", pady=4)
            line.columnconfigure(1, weight=1)
            self.pd_rows[key] = line
            if key == "length_m":
                label = "路徑總直管長（水側含供回）"
            ttk.Label(line, text=label).grid(row=0, column=0, sticky="w", padx=(0, 15))
            if isinstance(unit, list):
                w = ttk.Combobox(line, values=unit, state="readonly", width=26)
            else:
                w = ttk.Entry(line, width=26)
                ttk.Label(line, text=unit).grid(row=0, column=2, sticky="w", padx=8)
            w.configure(textvariable=self.pd["MCHW"][key])
            w.grid(row=0, column=1, sticky="ew")
            self.pd_widgets[key] = w
            if key == "allowance_pct":
                buttons = ttk.Frame(line)
                buttons.grid(row=1, column=0, columnspan=3, sticky="w", pady=5)
                for text, value in [
                    ("管件較少 10%", 10),
                    ("一般初估 30%", 30),
                    ("管件較多 50%", 50),
                ]:
                    ttk.Button(
                        buttons,
                        text=text,
                        command=lambda v=value: self.pd[self.selected_pd][
                            "allowance_pct"
                        ].set(str(v)),
                    ).pack(side="left", padx=3)
        ttk.Label(
            b,
            text="簡易公式：直管摩擦 × (1＋管件等效長度餘裕)＋已知設備壓差＋適用靜揚程。\n10／30／50% 只是明示的方案初估，並非管件標準；高阻力閥／濾網等另填設備。\n不知道設備壓差時只報管路小計。詳細 K、L/D、阻力率與效率可切換詳細／進階。",
            wraplength=650,
            style="Muted.TLabel",
        ).pack(fill="x", pady=8)
        self.grid.selection_set("MCHW")

    def build_report(self):
        page = ttk.Frame(self.host, padding=16)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        self.pages[8] = page
        toolbar = ttk.Frame(page)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(toolbar, text="複製全文", command=self.copy_report).pack(side="left")
        ttk.Button(
            toolbar, text="另存完整驗算資料 JSON", command=self.export_audit
        ).pack(side="left", padx=8)
        self.text = tk.Text(
            page,
            wrap="word",
            font=(self.ui_font, 11),
            bg="white",
            fg="#17324a",
            padx=20,
            pady=20,
            state="disabled",
        )
        self.text.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(page, command=self.text.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)

    def render_results(self):
        r = self.result
        s = r["summer"]
        w = r["winter"]
        self.summary.config(
            text=f"夏季負荷摘要｜室內顯熱  {r['qs']:,.1f} kW     產濕  {r['moisture'] * 3600:,.2f} kg/h\n補償外氣  {r['oa_room_cmh']:,.0f} CMH     DCC 夏冬較大需求  {r.get('dcc_design_kw', r['dcc_kw']):,.1f} kW\n照明  {r['light']['qty']} 盞 / {r['light']['kw']:.2f} kW"
        )
        i = r.get("effective_inputs", r["project"]["inputs"])
        p = float(i["atm_kpa"])
        lines = []
        for name, state in [("OA", r["oa"]), ("RA", r["room"])]:
            lines.append(
                f"{name}：濕球 {wetbulb(state['t'], state['rh'], p):.2f}°C／露點 {dewpoint(state['w'], p):.2f}°C／w {state['w'] * 1000:.3f} g/kg乾空氣／h {state['h']:.2f} kJ/kg乾空氣"
            )
        self.psy_label.config(text="\n".join(lines))
        self.topology.config(
            text=(
                "氣流配置：OA → MAU 兩段盤管 → 再熱／加濕 → 室內；室內 → DCC → FFU → 室內。MAU 外氣另需對應排氣／洩壓。"
                if i["sys_type"].startswith("MAU")
                else "氣流配置：OA＋RA → 混合入口 → 盤管 → 再熱／加濕 → SA → 室內；圖上虛線為混風輔助線。"
            )
        )
        self.result_labels[1].config(
            text="設備候選："
            + (
                "；".join(f"{k} {v} 台" for k, v in r["counts"].items() if v)
                or "無需求"
            )
            + f"\n夏季再熱 {s['reheat_kw']:.2f} kW，加濕 {s['humid_kg_h']:.2f} kg/h；冬季加熱 {w['reheat_kw']:.2f} kW，加濕 {w['humid_kg_h']:.2f} kg/h。"
        )
        self.latent_text.set(
            f"人員 {r['latent']['people_kg_h']:.2f}＋製程 {r['latent']['process_kg_h']:.2f}＝室內合計 {r['moisture'] * 3600:.2f} kg/h\n除濕負荷參考 {r['ql']:.2f} kW；外氣水氣由空調盤管另算。"
        )
        self.result_labels[2].config(
            text=f"照明 {r['light']['qty']} 盞／{r['light']['kw']:.3f} kW；室內顯熱 {r['qs']:.3f} kW、產濕 {r['moisture'] * 3600:.3f} kg/h。"
        )
        self.result_labels[3].config(
            text="\n".join(
                (
                    f"{g['type']}：{g['size']}，{g['actual_lpm']:.2f} ALPM｜絕壓 {g['pressure_abs_pa'] / 1000:.3f} kPa｜實速 {g['velocity_mps']:.2f}／上限 {g['velocity_limit_mps']:.2f} m/s"
                    for g in r["gas"].values()
                )
            )
        )
        self.result_labels[4].config(
            text="\n".join(
                (
                    f"{k}：運轉 {e['current_a']:.2f} A／設計 {e['design_current_a']:.2f} A，候選 {e['selected']['nfb_candidate_a']} AT，{e['selected']['runs']}組×{e['selected']['size_mm2']} mm²/相"
                    for k, e in r["electric"].items()
                )
            )
        )
        self.result_labels[5].config(
            text="\n".join(
                (
                    f"{k}：{d['nominal_cmh']:.1f} → {d['flow_cmh']:.1f} CMH（含餘裕），{duct_dimensions(d)}，{d['velocity_mps']:.3f} m/s"
                    for k, d in r["ducts"].items()
                )
            )
        )
        self.result_labels[6].config(
            text="\n".join(
                (
                    f"{k}：{d['lpm']:.2f} LPM，{d['runs']}支×{d['size']}，能力 {d['capacity_kw']:.2f} kW"
                    for k, d in r["water"].items()
                )
            )
            + (
                f"\nUPW：ID {r['upw']['relation']} {r['upw']['id_mm']:.3f} mm"
                if r["upw"]["lpm"]
                else "\nUPW：無需求"
            )
        )
        for k, d in r["pressure"].items():
            self.grid.item(
                k,
                values=(
                    f"{d['flow_m3s'] * (60000 if k in PD_KEYS[:5] else 3600):,.1f}",
                    f"{d['velocity_mps']:.3f}",
                    f"{d['total_pa']:,.1f}",
                    "含設備" if d["equipment_included"] else "未含設備",
                ),
            )

    def show_page(self, n):
        self.current = n
        self.pages[n].tkraise()
        self.title.config(text=PAGES[n])
        self.subtitle.config(text="基本先填現場條件｜F5 重新計算")
        self.update_visibility()
        for j, b in enumerate(self.nav):
            b.config(
                bg="#265270" if n == j else "#11253b",
                fg="white" if n == j else "#d7e5f4",
            )

    def wheel(self, e):
        if e.widget.winfo_toplevel() != self.root:
            return
        w = e.widget
        if isinstance(w, (tk.Text, ttk.Treeview, ttk.Combobox)):
            return
        if self.current == 8:
            return
        page = self.pages[self.current]
        from .platform_support import scroll_units

        step = scroll_units(e)
        if not step:
            return
        page.canvas.yview_scroll(step, "units")
        return "break"

    def set_report(self, t):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", t)
        self.text.configure(state="disabled")

    def sidebar_layout(self, event=None):
        if event is not None and event.widget != self.root:
            return
        compact = self.root.winfo_height() < 720
        if self._compact == compact:
            return
        self._compact = compact
        for w in self._side_order:
            if not isinstance(w, tk.Label):
                continue
            text = str(w.cget("text"))
            hide = "FACILITY" in text or "DESIGNED" in text or bool(w.cget("image"))
            if not hide:
                continue
            if compact:
                w.pack_forget()
            elif not w.winfo_manager():
                opts = {k: v for k, v in self._side_pack[w].items() if k != "in"}
                later = self._side_order[self._side_order.index(w) + 1 :]
                anchor = next((v for v in later if v.winfo_manager()), None)
                if anchor:
                    opts["before"] = anchor
                w.pack(**opts)

    def _configure_theme(self):
        families = set(tkfont.families(self.root))
        from .platform_support import preferred_ui_font

        self.ui_font = preferred_ui_font(families)
        st = ttk.Style(self.root)
        st.theme_use("clam")
        st.configure(
            ".", font=(self.ui_font, 10), background="#f1f5f9", foreground="#17324a"
        )
        st.configure("TFrame", background="#f1f5f9")
        st.configure("TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
        st.configure(
            "TLabelframe.Label",
            background="#f1f5f9",
            font=(self.ui_font, 11, "bold"),
            foreground="#174b69",
        )
        st.configure("TEntry", fieldbackground="white", padding=5)
        st.configure("TCombobox", padding=5)
        st.configure("TButton", padding=(8, 6))
        st.configure("Title.TLabel", font=(self.ui_font, 18, "bold"))
        st.configure("Muted.TLabel", foreground="#5d7083")
        st.configure("Error.TLabel", foreground="#b63437")
        st.configure("Good.TLabel", foreground="#127364")
        st.configure("Accent.TButton", background="#126d80", foreground="white")
        st.map("Accent.TButton", background=[("active", "#0c5368")])
        st.configure("Invalid.TEntry", fieldbackground="#ffeded")
        st.configure(
            "Treeview", rowheight=29, fieldbackground="white", background="white"
        )
        st.configure("Treeview.Heading", font=(self.ui_font, 10, "bold"))

    def configure_style(self):
        self._configure_theme()
        ttk.Style(self.root).configure("Warn.TLabel", foreground="#9a5b0b")

    def _build_dashboard(self):
        b = self.pages[0].body
        condition_boxes = list(b.winfo_children())
        for box in condition_boxes:
            box.pack_forget()
        self.summary = ttk.Label(
            b,
            text="啟動中",
            font=(self.ui_font, 12, "bold"),
            wraplength=650,
            justify="left",
        )
        self.summary.pack(fill="x", pady=12)
        self.psy_label = ttk.Label(b, text="", wraplength=650)
        self.psy_label.pack(fill="x", pady=8)
        row = ttk.Frame(b)
        row.pack(fill="x")
        ttk.Label(row, text="流程圖季節").pack(side="left")
        self.season = tk.StringVar(value="夏季")
        season = ttk.Combobox(
            row,
            textvariable=self.season,
            values=["夏季", "冬季"],
            state="readonly",
            width=20,
        )
        season.pack(side="left", padx=10)
        season.bind("<<ComboboxSelected>>", lambda e: self.draw())
        ttk.Button(
            row,
            text="編輯共同氣候",
            command=lambda: self.pages[0].reveal(self.widgets["oa_t"]),
        ).pack(side="left", padx=8)
        ttk.Button(row, text="另存流程圖 PNG", command=self.save_plot).pack(
            side="right"
        )
        if HAS_PLOT:
            names = {f.name for f in font_manager.fontManager.ttflist}
            if not names.intersection(
                {
                    "Microsoft JhengHei",
                    "Noto Sans CJK JP",
                    "Noto Sans CJK TC",
                    "PingFang TC",
                    "Arial Unicode MS",
                }
            ):
                for path in font_manager.findSystemFonts():
                    if any(
                        (
                            token in Path(path).name.lower()
                            for token in ["notosanscjk", "msjh", "pingfang"]
                        )
                    ):
                        try:
                            font_manager.fontManager.addfont(path)
                        except (OSError, RuntimeError):
                            pass
                names = {f.name for f in font_manager.fontManager.ttflist}
            for name in [
                "Microsoft JhengHei",
                "Noto Sans CJK JP",
                "Noto Sans CJK TC",
                "PingFang TC",
                "Arial Unicode MS",
            ]:
                if name in names:
                    rcParams["font.family"] = [name]
                    break
            rcParams["axes.unicode_minus"] = False
            self.fig = Figure(figsize=(8.5, 5.2), dpi=100)
            self.ax = self.fig.add_subplot(111)
            self.plot = FigureCanvasTkAgg(self.fig, master=b)
            self.plot.get_tk_widget().configure(height=350)
            self.plot.get_tk_widget().pack(fill="x", pady=12)
        else:
            ttk.Label(
                b,
                text="未安裝 matplotlib：數值及報告仍可使用；安裝後可開啟流程圖。",
                style="Muted.TLabel",
            ).pack(pady=20)
        self.topology = ttk.Label(b, text="", wraplength=650, style="Muted.TLabel")
        self.topology.pack(fill="x", pady=10)
        for box in condition_boxes:
            box.pack(fill="x", pady=(12, 16))

    def build_overview(self):
        self._build_dashboard()
        self.quality_label = ttk.Label(
            self.pages[0].body, wraplength=650, justify="left", style="Warn.TLabel"
        )
        self.quality_label.pack(fill="x", before=self.psy_label, pady=8)

    def _draw_process(self):
        if not HAS_PLOT or not self.result:
            return
        r = self.result
        c = r["summer"] if self.season.get() == "夏季" else r["winter"]
        p = float(r["project"]["inputs"]["atm_kpa"])
        outside = r["oa"] if self.season.get() == "夏季" else r["winter_oa"]
        nodes = [
            ("OA", outside),
            ("RA", r["room"]),
            ("IN", c["enter"]),
            ("C1", c["c1"]["outlet"]),
            ("C2", c["c2"]["outlet"]),
            ("HT", c["heat_state"]),
            ("SA", c["supply"]),
        ]
        lo = min((x["t"] for _, x in nodes)) - 5
        hi = max((x["t"] for _, x in nodes)) + 5
        ymax = max((x["w"] * 1000 for _, x in nodes)) * 1.22 + 1
        translated_axes(self.ax).clear()
        temps = [lo + (hi - lo) * j / 149 for j in range(150)]
        for rh in [10, 30, 50, 70, 90, 100]:
            translated_axes(self.ax).plot(
                temps,
                [state_trh(t, rh, p)["w"] * 1000 for t in temps],
                color="#8aa4b7",
                alpha=0.35,
                lw=1 if rh < 100 else 1.7,
            )
        translated_axes(self.ax).plot(
            [outside["t"], r["room"]["t"]],
            [outside["w"] * 1000, r["room"]["w"] * 1000],
            ls="--",
            color="#94a3b8",
            lw=1,
            label="混風輔助線",
        )
        seq = [
            c["enter"],
            c["c1"]["outlet"],
            c["c2"]["outlet"],
            c["heat_state"],
            c["supply"],
        ]
        for j, (a, b) in enumerate(zip(seq, seq[1:])):
            if abs(a["t"] - b["t"]) + abs(a["w"] - b["w"]) * 1000 < 1e-07:
                continue
            translated_axes(self.ax).annotate(
                "",
                xy=(b["t"], b["w"] * 1000),
                xytext=(a["t"], a["w"] * 1000),
                arrowprops={
                    "arrowstyle": "-|>",
                    "color": ["#176e9e", "#176e9e", "#d27623", "#16836c"][j],
                    "lw": 2.2,
                },
            )
        clusters = {}
        for name, s in nodes:
            clusters.setdefault((round(s["t"], 5), round(s["w"] * 1000, 5)), []).append(
                name
            )
        for j, ((t, w), names) in enumerate(clusters.items()):
            translated_axes(self.ax).scatter(t, w, s=35, color="#183e58", zorder=4)
        translated_axes(self.ax).set(
            xlim=(lo, hi),
            ylim=(0, ymax),
            xlabel="乾球溫度 °C",
            ylabel="含濕比 g/kg乾空氣",
            title=self.season.get() + f"｜{p:g} kPa｜IN入口 C1/C2盤管 HT加熱 SA送風",
        )
        translated_axes(self.ax).text(
            0.01,
            0.98,
            "藍：冷卻  橘：加熱  綠：加濕\n灰線：10 / 30 / 50 / 70 / 90 / 100% RH",
            transform=translated_axes(self.ax).transAxes,
            va="top",
            fontsize=8,
            color="#506878",
        )
        translated_axes(self.ax).grid(alpha=0.15)
        self.fig.tight_layout()
        annotate_states(self.ax, clusters)
        self.plot.draw_idle()

    def draw(self):
        if self.result:
            return self._draw_process()
        if self.partial_hvac:
            self.result = self.partial_hvac
            try:
                self._draw_process()
            finally:
                self.result = None
