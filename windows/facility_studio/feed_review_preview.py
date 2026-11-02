"""Traditional Chinese, additive engineering-verification workbench."""

import copy
from .engineering_verification import (
    BUILD,
    UNIT_GROUPS,
    compare_defaults,
    compare_file,
    compare_inputs,
    convert_units,
    export_report,
    metadata,
    pipe_calculate,
    report_text,
)

PIPE_DEFAULTS = {
    "flow_lpm": "100",
    "runs": "1",
    "id_mm": "50",
    "temperature_c": "20",
    "pressure_kpa": "200",
    "length_m": "30",
    "roughness_mm": "0.045",
    "sum_k": "4",
    "equipment_pa": "0",
    "boundary": "閉式循環",
    "static_m": "0",
}


class VerificationWindow:
    def __init__(self, parent, ahu_provider=None, water_provider=None, host=None,
                 initial_tab="ahu", on_close=None):
        import tkinter as tk
        from tkinter import ttk, font as tkfont
        from .platform_support import preferred_ui_font
        from .flow_toolbar import FlowToolbar

        self.tk, self.ttk = tk, ttk
        self.family = preferred_ui_font(set(tkfont.families(parent)))
        self.ahu_provider, self.water_provider = ahu_provider, water_provider
        self.results, self.texts, self.summaries, self.source_snapshot = {}, {}, {}, None
        self.water_snapshot = None
        self.embedded = host is not None
        self.win = host if self.embedded else tk.Toplevel(parent)
        if not self.embedded:
            self.win.configure(background="#eef3f8")
            self.win.title("設計檢核中心｜" + BUILD)
            self.win.geometry(
                f"{min(1120, parent.winfo_screenwidth() - 60)}x{min(820, parent.winfo_screenheight() - 100)}"
            )
            self.win.minsize(720, 520)
        self.status = tk.StringVar(self.win, "請選功能；所有結果都會標示採用條件。")
        ttk.Label(
            self.win,
            text="設計檢核中心｜計算 → 獨立核對 → 匯出證據",
            font=(self.family, 16, "bold"),
        ).pack(anchor="w", padx=14, pady=(14, 4))
        ttk.Label(self.win, textvariable=self.status, wraplength=680).pack(
            anchor="w", padx=14, pady=4
        )
        self.nb = ttk.Notebook(self.win)
        self.nb.pack(fill="both", expand=True, padx=12, pady=8)
        self.frames = {}
        for key, title in [
            ("ahu", "AHU 濕空氣與熱量"),
            ("pipe", "液態水管壓損"),
            ("units", "工程單位換算"),
        ]:
            f = ttk.Frame(self.nb, padding=8)
            self.nb.add(f, text=title)
            self.frames[key] = f
        bar = FlowToolbar(self.frames["ahu"])
        bar.pack(fill="x", pady=(0, 8))
        for label, command in [
            ("載入合成示範", lambda: self.run("ahu", compare_defaults)),
            ("讀取目前 AHU", self.load_current_ahu),
            ("開啟單機專案", self.load_file),
        ]:
            b = ttk.Button(bar, text=label, command=command)
            b.pack(side="left", padx=3)
            if label == "讀取目前 AHU" and ahu_provider is None:
                b.configure(state="disabled")
        self.make_text("ahu")
        pipe_form = ttk.Frame(self.frames["pipe"])
        pipe_form.pack(fill="x")
        self.pipe_vars = {
            key: tk.StringVar(self.win, value) for key, value in PIPE_DEFAULTS.items()
        }
        labels = {
            "flow_lpm": "總循環水量 LPM",
            "runs": "等流量並聯支數",
            "id_mm": "實際內徑 mm",
            "temperature_c": "水溫 °C",
            "pressure_kpa": "水絕對壓力 kPa",
            "length_m": "直管長度 m",
            "roughness_mm": "絕對粗糙度 mm",
            "sum_k": "管件 K 加總",
            "equipment_pa": "設備壓降 Pa（0 未納入）",
            "boundary": "系統邊界",
            "static_m": "開式靜揚程 m",
        }
        for n, (key, label) in enumerate(labels.items()):
            row, col = divmod(n, 2)
            col *= 2
            ttk.Label(pipe_form, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=3
            )
            if key == "boundary":
                w = ttk.Combobox(
                    pipe_form,
                    textvariable=self.pipe_vars[key],
                    values=("閉式循環", "開式系統"),
                    state="readonly",
                    width=15,
                )
            else:
                w = ttk.Entry(pipe_form, textvariable=self.pipe_vars[key], width=16)
            w.grid(row=row, column=col + 1, sticky="ew", padx=4, pady=3)
            self.pipe_vars[key].trace_add(
                "write", lambda *args: self.invalidate("pipe")
            )
        pipe_form.columnconfigure(1, weight=1)
        pipe_form.columnconfigure(3, weight=1)
        ttk.Label(
            self.frames["pipe"],
            text="純水、單相、同徑等流量支路；水溫／壓力請另行確認，不推測未提供資料。",
            wraplength=680,
        ).pack(anchor="w", pady=5)
        pipe_bar = FlowToolbar(self.frames["pipe"])
        pipe_bar.pack(fill="x", pady=4)
        ttk.Button(
            pipe_bar,
            text="計算與比較",
            command=self.calculate_pipe,
        ).pack(side="left", padx=3)
        b = ttk.Button(pipe_bar, text="帶入目前冷熱水工具", command=self.load_water)
        b.pack(side="left", padx=3)
        if water_provider is None:
            b.configure(state="disabled")
        ttk.Button(pipe_bar, text="改用手動輸入", command=self.detach_water).pack(side="left", padx=3)
        self.make_text("pipe")
        form = FlowToolbar(self.frames["units"])
        form.pack(fill="x", pady=4)
        self.group = tk.StringVar(self.win, "體積流量")
        self.unit = tk.StringVar(self.win, "CMH")
        self.value = tk.StringVar(self.win, "1000")
        ttk.Combobox(
            form,
            textvariable=self.group,
            values=tuple(UNIT_GROUPS),
            state="readonly",
            width=12,
        ).pack(side="left", padx=3)
        ttk.Entry(form, textvariable=self.value, width=15).pack(side="left", padx=3)
        self.unit_picker = ttk.Combobox(
            form,
            textvariable=self.unit,
            values=tuple(UNIT_GROUPS["體積流量"]),
            state="readonly",
            width=14,
        )
        self.unit_picker.pack(side="left", padx=3)
        ttk.Button(form, text="換算", command=self.convert).pack(side="left", padx=3)
        self.group.trace_add("write", self.change_group)
        self.unit.trace_add("write", lambda *args: self.invalidate("units"))
        self.value.trace_add("write", lambda *args: self.invalidate("units"))
        self.make_text("units")
        footer = FlowToolbar(self.win)
        footer.pack(fill="x", padx=12, pady=(0, 12))
        self.export_button = ttk.Button(
            footer, text="匯出本頁報告", command=self.export_current, state="disabled"
        )
        self.export_button.pack(side="left", padx=3)
        ttk.Button(footer, text="返回工程快算" if self.embedded else "關閉",
                   command=on_close or self.win.destroy).pack(
            side="right", padx=3
        )
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.sync_export())
        # Open on a live AHU snapshot when the command is invoked from that AHU.
        if ahu_provider:
            self.load_current_ahu()
        else:
            self.run("ahu", compare_defaults)
        self.nb.select(self.frames[initial_tab])
        self.win.verification = self

    def make_text(self, key):
        from tkinter import scrolledtext

        self.summaries[key] = self.tk.StringVar(self.win, "尚未計算")
        summary = self.ttk.Label(
            self.frames[key], textvariable=self.summaries[key], padding=10,
            font=(self.family, 12, "bold"), foreground="#16364c",
            background="#e2edf4", wraplength=660,
        )
        summary.pack(fill="x", pady=(6, 0))
        summary.bind("<Configure>", lambda e: summary.configure(wraplength=max(100, e.width - 24)))
        self.ttk.Label(self.frames[key], text="計算依據、適用條件與逐項對照").pack(
            anchor="w", pady=(6, 0)
        )
        text = scrolledtext.ScrolledText(
            self.frames[key],
            wrap="word",
            font=(self.family, 13),
            foreground="#202938",
            background="white",
            padx=10,
            pady=10,
            height=10,
        )
        text.pack(fill="both", expand=True, pady=(6, 0))
        text.configure(state="disabled")
        self.texts[key] = text

    def current(self):
        return list(self.frames)[self.nb.index("current")]

    def sync_export(self):
        if hasattr(self, "export_button"):
            self.export_button.configure(
                state="normal" if self.current() in self.results else "disabled"
            )

    def display(self, key, content):
        t = self.texts[key]
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("1.0", content)
        t.configure(state="disabled")

    def invalidate(self, key):
        self.results.pop(key, None)
        if key in self.summaries:
            self.summaries[key].set("輸入已變更｜請重新計算；舊結果不可採用或匯出")
        if key in self.texts:
            self.display(key, "輸入已變更；請重新計算，舊結果不可匯出。")
        self.sync_export()

    def run(self, key, fn):
        self.results.pop(key, None)
        if key == "ahu":
            self.source_snapshot = None
        try:
            r = fn()
            content = report_text(r)
            self.results[key] = copy.deepcopy(r)
            self.display(key, content)
            if key == "ahu":
                n, q = r["numerical_summary"], r["model_quality"]
                self.summaries[key].set(
                    f"資料：{r['case']}\n數值對照 {n['within_limit']}/{n['checks']} 在內部門檻內｜工程狀態：{q['status']}\n"
                    f"工程未達 {q['failed']} 項、待資料 {q['pending']} 項；數值一致不代表工程設計通過。"
                )
            elif key == "pipe":
                self.summaries[key].set(
                    f"總壓差 {r['total_pa']/1000:.3f} kPa｜揚程 {r['head_m']:.3f} m｜流速 {r['velocity_m_s']:.3f} m/s\n"
                    f"{r['regime']}｜{r['runs']} 支等流量支路｜水物性 CoolProp・摩擦因子 fluids"
                )
            else:
                self.summaries[key].set(
                    f"{r['inputs']['group']}｜{r['inputs']['value']} {r['inputs']['unit']} → {len(r['values'])} 種單位\n"
                    "採 Pint 同物理量換算；溫度為絕對溫度。"
                )
            self.status.set("計算完成；請核對工程品質明細、數值門檻與採用條件。")
        except Exception as error:
            # Clear stale outputs before presenting any input/dependency failure.
            self.display(
                key,
                "無法執行：" + str(error) + "\n請確認輸入格式、單位及適用範圍後重試。",
            )
            self.status.set("本次計算未完成；本頁報告已停用。")
            self.summaries[key].set("輸入或計算有誤｜沒有可採用的結果")
        self.sync_export()

    def load_current_ahu(self):
        if not self.ahu_provider:
            return

        def calculate():
            self._candidate = copy.deepcopy(self.ahu_provider())
            return compare_inputs(
                self._candidate, "目前 AHU 的輸入快照（變更後須重新讀取）"
            )

        self.run("ahu", calculate)
        if "ahu" in self.results:
            self.source_snapshot = self._candidate

    def load_file(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            parent=self.win,
            title="選擇 AHU 單機專案",
            filetypes=[("JSON 專案", "*.json")],
        )
        if path:
            self.run("ahu", lambda: compare_file(path))

    def pipe_data(self):
        return {k: v.get() for k, v in self.pipe_vars.items()}

    def refresh_sources(self):
        for key, snapshot, provider in (("ahu", self.source_snapshot, self.ahu_provider),
                                        ("pipe", self.water_snapshot, self.water_provider)):
            if key not in self.results or snapshot is None or provider is None:
                continue
            try:
                unchanged = provider() == snapshot
            except Exception:
                unchanged = False
            if not unchanged:
                self.invalidate(key)
                self.status.set("原始條件已變更；請重新讀取 AHU 或帶入冷熱水，再計算與匯出。")

    def calculate_pipe(self):
        def calculate():
            if self.water_snapshot is not None and self.water_provider() != self.water_snapshot:
                raise ValueError("上游冷熱水條件已變更；請重新帶入或明確改用手動輸入。")
            return pipe_calculate(self.pipe_data())
        self.run("pipe", calculate)

    def calculate_current(self):
        key = self.current()
        if key == "pipe":
            return self.calculate_pipe()
        if key == "units":
            return self.convert()
        if self.ahu_provider:
            return self.load_current_ahu()
        self.status.set("請選擇合成示範或開啟 AHU 單機專案後，再核對計算。")

    def detach_water(self):
        self.water_snapshot = None
        self.invalidate("pipe")
        self.status.set("已保留欄位並改為獨立手動輸入；請確認全部條件後重新計算。")

    def load_water(self):
        try:
            values = self.water_provider()
            for key, value in values.items():
                self.pipe_vars[key].set(value)
            self.invalidate("pipe")
            self.water_snapshot = copy.deepcopy(values)
            self.status.set(
                "已帶入目前水量、選定內徑及路徑；請確認水溫、絕對壓力與系統邊界，再計算。"
            )
        except Exception as error:
            self.invalidate("pipe")
            self.status.set("無法帶入：" + str(error))

    def change_group(self, *args):
        choices = tuple(UNIT_GROUPS[self.group.get()])
        self.unit_picker.configure(values=choices)
        self.unit.set(choices[0])
        self.invalidate("units")

    def convert(self):
        self.run(
            "units",
            lambda: {
                "build": BUILD,
                "kind": "unit_conversion",
                "inputs": {
                    "group": self.group.get(),
                    "value": self.value.get(),
                    "unit": self.unit.get(),
                },
                "values": convert_units(
                    self.value.get(), self.group.get(), self.unit.get()
                ),
                "versions": metadata(),
                "scope": "Pint 同物理量換算；美制冷凍噸採 US RT。溫度為絕對溫度，非溫差。",
            },
        )

    def export_current(self):
        from tkinter import filedialog

        key = self.current()
        if key not in self.results:
            return
        if key == "pipe" and self.water_snapshot is not None:
            try:
                unchanged = self.water_provider() == self.water_snapshot
            except Exception:
                unchanged = False
            if not unchanged:
                self.invalidate("pipe")
                self.status.set("上游冷熱水條件已變更，請重新帶入後再計算與匯出。")
                return
        if key == "ahu" and self.source_snapshot is not None and self.ahu_provider:
            try:
                unchanged = self.ahu_provider() == self.source_snapshot
            except Exception:
                unchanged = False
            if not unchanged:
                self.invalidate("ahu")
                self.status.set("目前 AHU 已變更，請重新讀取後再匯出。")
                return
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="另存新的驗證報告",
            defaultextension=".html",
            filetypes=[
                ("網頁報告", "*.html"),
                ("文字報告", "*.txt"),
                ("可重現資料", "*.json"),
            ],
        )
        if path:
            try:
                digest = export_report(self.results[key], path)
                self.status.set("報告已儲存；SHA-256：" + digest[:16] + "…")
            except (OSError, ValueError) as error:
                self.status.set("匯出未完成：" + str(error))


def open_preview(parent, ahu_provider=None, water_provider=None, initial_tab="ahu"):
    return VerificationWindow(parent, ahu_provider, water_provider,
                              initial_tab=initial_tab).win
