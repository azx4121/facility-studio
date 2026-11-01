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
    def __init__(self, parent, ahu_provider=None, water_provider=None):
        import tkinter as tk
        from tkinter import ttk
        from .flow_toolbar import FlowToolbar

        self.tk, self.ttk = tk, ttk
        self.ahu_provider, self.water_provider = ahu_provider, water_provider
        self.results, self.texts, self.source_snapshot = {}, {}, None
        self.win = tk.Toplevel(parent)
        self.win.configure(background="#eef3f8")
        self.win.title("工程驗證沙盒｜" + BUILD)
        self.win.geometry(
            f"{min(1120, parent.winfo_screenwidth() - 60)}x{min(820, parent.winfo_screenheight() - 100)}"
        )
        self.win.minsize(720, 520)
        self.status = tk.StringVar(self.win, "請選功能；所有結果都會標示採用條件。")
        ttk.Label(
            self.win,
            text="工程驗證｜AHU 對照・液態水管・單位換算",
            font=("PingFang TC", 16, "bold"),
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
            ("原版合成案例", lambda: self.run("ahu", compare_defaults)),
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
            "flow_lpm": "循環水量 LPM",
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
            text="純水、單相、圓管；水溫／壓力請另行確認，從原工具帶入時不會猜測。",
            wraplength=680,
        ).pack(anchor="w", pady=5)
        pipe_bar = FlowToolbar(self.frames["pipe"])
        pipe_bar.pack(fill="x", pady=4)
        ttk.Button(
            pipe_bar,
            text="計算與比較",
            command=lambda: self.run("pipe", lambda: pipe_calculate(self.pipe_data())),
        ).pack(side="left", padx=3)
        b = ttk.Button(pipe_bar, text="帶入目前冷熱水工具", command=self.load_water)
        b.pack(side="left", padx=3)
        if water_provider is None:
            b.configure(state="disabled")
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
        ttk.Button(footer, text="關閉", command=self.win.destroy).pack(
            side="right", padx=3
        )
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.sync_export())
        # Open on a live AHU snapshot when the command is invoked from that AHU.
        if ahu_provider:
            self.load_current_ahu()
        else:
            self.run("ahu", compare_defaults)
        self.win.verification = self

    def make_text(self, key):
        from tkinter import scrolledtext

        text = scrolledtext.ScrolledText(
            self.frames[key],
            wrap="word",
            font=("PingFang TC", 13),
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
            self.status.set("計算完成；請核對工程品質明細、數值門檻與採用條件。")
        except Exception as error:
            # Clear stale outputs before presenting any input/dependency failure.
            self.display(
                key,
                "無法執行：" + str(error) + "\n請確認輸入格式、單位及適用範圍後重試。",
            )
            self.status.set("本次計算未完成；本頁報告已停用。")
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

    def load_water(self):
        try:
            values = self.water_provider()
            for key, value in values.items():
                self.pipe_vars[key].set(value)
            self.invalidate("pipe")
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


def open_preview(parent, ahu_provider=None, water_provider=None):
    return VerificationWindow(parent, ahu_provider, water_provider).win
