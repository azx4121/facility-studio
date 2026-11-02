"""Optional project inputs, editable in the production workbench."""

# Existing projects remain explicit manual-property / velocity-only projects.
# New assumptions are adopted only by this editor or by a new project.
SETTINGS = {
    "c2_bf_min": ("冷卻盤管 BF 下限（廠商資料；留空未提供）", "", (0, .5)),
    "coil_pinch_min_k": ("盤管最小端差 K", "0.5", (0, 20)),
    "winter_ffu_ratio": ("冬季 FFU 發熱比例 %", "100", (0, 100)),
    "winter_mau_max_t": ("冬季 MAU 送風上限 °C", "40", (15, 60)),
    "winter_terminal_heat_source": ("冬季室內末端熱源", "未配置", ["未配置", "HW"]),
    "water_sizing_basis": ("水管自動選型", "流速上限", ["流速上限", "流速與摩擦壓損"]),
    "water_friction_limit": ("水管摩擦壓損警戒／選型上限 Pa/m", "400", (1, 10000)),
    "duct_friction_limit": ("風管摩擦壓損警戒 Pa/m", "1.5", (.01, 100)),
    "chiller_capacity_basis": ("冰水主機容量邊界", "本案空調同時峰值",
                               ["本案空調同時峰值", "獨立冷源水路包絡（確認無重複）"]),
    "np_auto_mode": ("NP 本案設備連動", "手動填列", ["手動填列", "自動加總本案（手填為額外負荷）"]),
    "main_fan_input_kw": ("本案 MAU／AHU 風機總輸入 kW（0 未提供）", "0", (0, 100000)),
    "ffu_input_w": ("單台 FFU 電氣輸入 W（與入室發熱分開）", "0", (0, 100000)),
    "motor_input_efficiency": ("水泵／排氣風機馬達效率", "0.9", (.1, 1)),
    "main_reheat_source": ("本案再熱熱源", "未確認", ["未確認", "電熱", "熱水（不列電熱）"]),
    "main_reheat_efficiency": ("電熱入空氣效率", "1", (.1, 1)),
    "main_humidifier_input_kw": ("本案加濕器輸入 kW（0 未提供）", "0", (0, 100000)),
    "chiller_power_scope": ("冰機用電盤別邊界", "外部供冷（不列NP）", ["外部供冷（不列NP）", "本案冰機列NP"]),
    "chiller_input_kw_rt": ("冰機整機輸入 kW/US RT（0 未提供）", "0", (0, 5)),
}
for loop in ("mchw", "chw", "dccw", "pcw", "hw"):
    SETTINGS.update({
        loop + "_property_source": (loop.upper() + " 物性來源", "沿用手動物性",
                                     ["沿用手動物性", "CoolProp 純水溫壓"]),
        loop + "_property_t": (loop.upper() + " 純水計算溫度 °C", "20", (.1, 150)),
        loop + "_property_p": (loop.upper() + " 純水絕對壓力 kPa", "300", (1, 10000)),
    })


def open_settings(app):
    from .localized_tk import tk, ttk, messagebox
    from .optional_inputs import validate_optional_inputs
    from .field_state import main_inactive, optional_inactive
    from .main_view import ScrollPage
    from .errors import InputError
    win = tk.Toplevel(app.root)
    owner_project = app.project_id
    win.title("進階工程設定")
    win.geometry("840x720")
    win.minsize(720, 500)
    ttk.Label(win, text="本案計算直接採用的模型與工程假設", font=("", 16, "bold"),
              padding=12).pack(fill="x")
    ttk.Label(win, text="警戒值是本案設定，不代表通用法規。純水物性必須填實際溫度與絕壓；乙二醇／混合液請保留手動物性。\n"
              "水路包絡模式限各迴路為獨立供冷負荷；主／次側同一負荷不可重複相加。", wraplength=780,
              padding=(12, 0, 12, 10)).pack(fill="x")
    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=12)
    win.fusion_notebook = notebook
    pages = {}
    scrollers = []
    for title in ("空調與冬季", "水路物性與選管", "NP 設備用電"):
        page = ScrollPage(notebook)
        notebook.add(page, text=title)
        scrollers.append(page.canvas)
        pages[title] = page.body
    def wheel(event):
        if not hasattr(event.widget, "winfo_class") or event.widget.winfo_class() == "TCombobox":
            return
        from .platform_support import scroll_units
        step = scroll_units(event)
        if step:
            scrollers[notebook.index(notebook.select())].yview_scroll(step, "units")
            return "break"
    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        win.bind(sequence, wheel)
    counts = {title: 0 for title in pages}
    current = app.snapshot()["inputs"]
    values = {}
    win.fusion_values = values
    widgets = {}
    groups = {}
    for key, (label, default, limit) in SETTINGS.items():
        title = ("水路物性與選管" if key.startswith(("water_", "duct_", "mchw_", "chw_", "dccw_", "pcw_", "hw_")) or key == "chiller_capacity_basis"
                 else "空調與冬季" if key.startswith(("c2_", "coil_", "winter_")) else "NP 設備用電")
        frame = pages[title]
        row = counts[title]
        counts[title] += 1
        groups[key] = list(pages).index(title)
        values[key] = tk.StringVar(value=current.get(key, default))
        ttk.Label(frame, text=label, wraplength=390).grid(row=row, column=0, sticky="w", padx=12, pady=5)
        widget = (ttk.Combobox(frame, textvariable=values[key], values=limit, state="readonly", width=31)
                  if isinstance(limit, list) else ttk.Entry(frame, textvariable=values[key], width=33))
        widget.grid(row=row, column=1, sticky="ew", padx=12, pady=5)
        widgets[key] = widget
        frame.columnconfigure(1, weight=1)
    def refresh_enabled(*args):
        conditions = dict(app.snapshot()["inputs"], **{k: v.get() for k, v in values.items()})
        off = optional_inactive(conditions)
        for key, widget in widgets.items():
            options = SETTINGS[key][2]
            widget.configure(state="disabled" if key in off else "readonly" if isinstance(options, list) else "normal")
    for key, variable in values.items():
        if isinstance(SETTINGS[key][2], list):
            variable.trace_add("write", refresh_enabled)
    refresh_enabled()
    win.bind("<FocusIn>", refresh_enabled, add="+")
    def apply():
        if app.project_id != owner_project:
            messagebox.showerror("設定未採用", "主案已切換，請關閉並重新開啟工程模型設定。", parent=win)
            return
        proposed = dict(app.snapshot()["inputs"])
        for key, variable in values.items():
            value = variable.get().strip()
            if key == "c2_bf_min" and not value:
                proposed.pop(key, None)
            else:
                proposed[key] = value
        try:
            off = main_inactive(proposed)
            validate_optional_inputs(proposed, off, optional_inactive(proposed, off))
            # Verify every adopted automatic fluid state before changing inputs.
            from .engine import water_properties
            from .field_state import effective_main
            effective = effective_main(proposed)
            for loop in ("MCHW", "CHW", "DCCW", "PCW", "HW"):
                water_properties(effective, loop)
        except (InputError, ValueError) as error:
            field = getattr(error, "field_name", None)
            if field in groups:
                notebook.select(groups[field])
                widgets[field].focus_set()
            messagebox.showerror("設定未採用", str(error), parent=win)
            return
        app.remember_main_undo()
        for key in SETTINGS:
            if key in proposed:
                app.extra_inputs[key] = proposed[key]
            else:
                app.extra_inputs.pop(key, None)
        app.changed()
        app.recalculate()
        win.destroy()
    footer = ttk.Frame(win, padding=12)
    footer.pack(fill="x")
    ttk.Button(footer, text="取消", command=win.destroy).pack(side="right", padx=6)
    ttk.Button(footer, text="採用並重新計算", command=apply).pack(side="right")
    win.apply_fusion_settings = apply
    return win
