"""Explicit photometric schedules and sampled direct horizontal illuminance.

No sample photometry or layout is loaded implicitly. The export fingerprint uses
raw form values and every imported source, including unused sources.
"""
import csv
import io
import json
import math
import tkinter as native_tk
from pathlib import Path

from .localized_tk import tk, ttk, filedialog, messagebox, attach_window
from . import i18n

UI_ENGLISH = {
    "直接照度配置": "Direct illuminance layout",
    "僅計算向下燈具的點光源水平面直接照度；不含反射、遮蔽、UGR，亦非 DIALux 等效結果。": "Down-facing point-source direct horizontal illuminance only; excludes reflections, obstructions and UGR. Not equivalent to DIALux.",
    "匯入 IES／LDT": "Import IES / LDT", "移除選取來源": "Remove selected source",
    "請匯入 1–32 個有效配光來源。": "Import 1–32 valid photometry sources.",
    "來源 ID": "Source ID", "格式": "Format", "燈具／檔案": "Luminaire / file",
    "來源 SHA-256": "Source SHA-256", "房間與取樣": "Room and sampling",
    "長度 (m)": "Length (m)", "寬度 (m)": "Width (m)",
    "工作面高度 (m)": "Workplane height (m)", "取樣邊界內縮 (m)": "Sampling inset (m)",
    "X 方向取樣數": "X sample count", "Y 方向取樣數": "Y sample count",
    "維護係數 (0–1)": "Maintenance factor (0–1)",
    "明確產生規則排列（會取代下方配置）": "Generate explicit regular layout (replaces schedule below)",
    "配光 ID": "Photometry ID", "列數 (Y)": "Rows (Y)", "欄數 (X)": "Columns (X)",
    "安裝高度 (m)": "Mounting height (m)", "產生可編輯配置": "Generate editable schedule",
    "燈具配置 CSV：ID,x,y,z,yaw,scale（m、度；scale 為 0–1 配光倍率）": "Fixture CSV: ID,x,y,z,yaw,scale (m, degrees; scale is a 0–1 photometry multiplier)",
    "原點在左下；所有燈具朝下，不支援傾斜。yaw 由上往下看逆時針；yaw=0 時檔案 C0 朝 +X、C90 朝 +Y；檔案軸向不一定對應燈殼正面。": "Origin at lower left; all fixtures face down, without tilt. Yaw is counterclockwise from above; file C0 points toward +X and C90 toward +Y at yaw=0. File axes need not match the housing front.",
    "計算直接照度": "Calculate direct illuminance", "匯出 HTML": "Export HTML",
    "匯出 CSV": "Export CSV", "匯出 JSON": "Export JSON",
    "請匯入配光、填寫房間與燈具配置後計算。": "Import photometry and enter room and fixture schedule before calculating.",
    "輸入已變更；請重新計算後匯出。": "Inputs changed; recalculate before exporting.",
    "尚無有效計算結果。": "No valid calculation result.", "操作失敗": "Operation failed",
    "已匯出": "Exported", "維護後取樣直接照度": "Maintained sampled direct illuminance",
    "初始平均": "Initial average",
    "平均": "Average", "最小": "Minimum", "最大": "Maximum",
    "等照度線": "Isolux contours", "格心取樣；色塊僅供視覺化": "Cell-centre samples; colored cells are visualization only",
    "配置／取樣輸入必須是有限數值。": "Layout / sampling inputs must be finite numbers.",
    "長寬須介於 0.1–1000 m，工作面介於 0–100 m，內縮須小於短邊的一半。": "Length and width must be 0.1–1000 m, workplane 0–100 m; inset less than half the shorter side.",
    "維護係數必須介於 0 與 1。": "Maintenance factor must be between 0 and 1.",
    "取樣數須為 2–80 的整數。": "Sample counts must be integers from 2 to 80.",
    "請至少匯入一個有效配光來源。": "Import at least one valid photometry source.",
    "每筆燈具配置須有六欄：ID,x,y,z,yaw,scale。": "Each fixture row requires six columns: ID,x,y,z,yaw,scale.",
    "燈具引用了不存在的配光 ID。": "A fixture references an unknown photometry ID.",
    "燈具須位於房間內、至少高於工作面 0.01 m，倍率須介於 0 與 1。": "Fixtures must be inside the room, at least 0.01 m above the workplane, with scale between 0 and 1.",
    "燈具數須為 1–200，且取樣點數乘以燈具數不得超過 2000000。": "Use 1–200 fixtures and at most 2000000 sample-fixture pairs.",
    "請選擇有效配光 ID，列／欄須為正整數且總燈具數不超過 200。": "Select a valid source ID and positive integer rows / columns, with at most 200 fixtures.",
}

LIMITATION = "僅計算向下燈具的點光源水平面直接照度；不含反射、遮蔽、UGR，亦非 DIALux 等效結果。"
FIELDS = (
    ("length_m", "長度 (m)", ""), ("width_m", "寬度 (m)", ""),
    ("workplane_m", "工作面高度 (m)", "0.8"), ("edge_m", "取樣邊界內縮 (m)", "0"),
    ("nx", "X 方向取樣數", "20"), ("ny", "Y 方向取樣數", "20"),
    ("maintenance", "維護係數 (0–1)", "1"),
)


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("配置／取樣輸入必須是有限數值。") from None
    if not math.isfinite(value):
        raise ValueError("配置／取樣輸入必須是有限數值。")
    return value


def parse_room(fields):
    """Parse visible room fields without touching Tk or photometric modules."""
    scene = {key: _number(fields.get(key, "")) for key, _, _ in FIELDS}
    length, width, edge = scene["length_m"], scene["width_m"], scene["edge_m"]
    if not (.1 <= length <= 1000 and .1 <= width <= 1000 and 0 <= scene["workplane_m"] <= 100) or edge < 0 or 2 * edge >= min(length, width):
        raise ValueError("長寬須介於 0.1–1000 m，工作面介於 0–100 m，內縮須小於短邊的一半。")
    if not 0 <= scene["maintenance"] <= 1:
        raise ValueError("維護係數必須介於 0 與 1。")
    for key in ("nx", "ny"):
        if not scene[key].is_integer() or not 2 <= scene[key] <= 80:
            raise ValueError("取樣數須為 2–80 的整數。")
        scene[key] = int(scene[key])
    return scene


def parse_scene(fields, fixture_text, source_ids):
    """Return the engine scene; reject malformed or unbounded user inputs."""
    scene = parse_room(fields)
    if not isinstance(fixture_text, str) or len(fixture_text) > 200000:
        raise ValueError("Fixture schedule exceeds the supported text size")
    if not source_ids:
        raise ValueError("請至少匯入一個有效配光來源。")
    fixtures = []
    reader = csv.reader(io.StringIO(fixture_text), strict=True)
    try:
        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue
            row = [cell.strip() for cell in row]
            if not fixtures and row == ["ID", "x", "y", "z", "yaw", "scale"]:
                continue
            if len(row) != 6:
                raise ValueError("每筆燈具配置須有六欄：ID,x,y,z,yaw,scale。")
            if row[0] not in source_ids:
                raise ValueError("燈具引用了不存在的配光 ID。")
            x, y, z, yaw, scale = map(_number, row[1:])
            if not (0 <= x <= scene["length_m"] and 0 <= y <= scene["width_m"] and z - scene["workplane_m"] >= .01 and 0 <= scale <= 1 and z <= 200 and abs(yaw) <= 36000):
                raise ValueError("燈具須位於房間內、至少高於工作面 0.01 m，倍率須介於 0 與 1。")
            fixtures.append(dict(photometry=row[0], x_m=x, y_m=y, z_m=z, yaw_deg=yaw, multiplier=scale))
            if len(fixtures) > 200:
                raise ValueError("燈具數須為 1–200，且取樣點數乘以燈具數不得超過 2000000。")
    except csv.Error:
        raise ValueError("每筆燈具配置須有六欄：ID,x,y,z,yaw,scale。") from None
    if not fixtures or scene["nx"] * scene["ny"] * len(fixtures) > 2000000:
        raise ValueError("燈具數須為 1–200，且取樣點數乘以燈具數不得超過 2000000。")
    scene["fixtures"] = fixtures
    return scene


def regular_schedule(fields, source_id, rows, columns, height, source_ids):
    """Explicit full-room cell-centre fixture layout, not a lighting design."""
    scene = parse_room(fields)
    nr, nc, z = _number(rows), _number(columns), _number(height)
    if source_id not in source_ids or not nr.is_integer() or not nc.is_integer() or min(nr, nc) < 1 or nr * nc > 200:
        raise ValueError("請選擇有效配光 ID，列／欄須為正整數且總燈具數不超過 200。")
    if z - scene["workplane_m"] < .01 or z > 200:
        raise ValueError("燈具須位於房間內、至少高於工作面 0.01 m，倍率須介於 0 與 1。")
    lines = ["ID,x,y,z,yaw,scale"]
    for iy in range(int(nr)):
        for ix in range(int(nc)):
            x, y = (ix + .5) * scene["length_m"] / nc, (iy + .5) * scene["width_m"] / nr
            lines.append(f"{source_id},{x:.12g},{y:.12g},{z:.12g},0,1")
    return "\n".join(lines) + "\n"


class DirectLightingWindow:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        attach_window(self.win)
        self.win.title("直接照度配置")
        self.win.geometry("1180x850")
        self.win.minsize(950, 730)
        self.sources, self.result, self.result_fingerprint = {}, None, None
        self.next_source_id = 1
        self.variables, self.generator_vars, self.export_buttons = {}, {}, []
        self.status = tk.StringVar(value="請匯入配光、填寫房間與燈具配置後計算。")
        self.summary = tk.StringVar(value="尚無有效計算結果。")
        self.win.columnconfigure(0, weight=1)
        self.win.rowconfigure(2, weight=1)
        ttk.Label(self.win, text=LIMITATION, wraplength=1100).grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        self._build_sources()
        body = ttk.Panedwindow(self.win, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew", padx=10)
        form, view = ttk.Frame(body, padding=5), ttk.Frame(body, padding=5)
        body.add(form, weight=1)
        body.add(view, weight=2)
        self._build_form(form)
        view.columnconfigure(0, weight=1)
        view.rowconfigure(1, weight=1)
        ttk.Label(view, textvariable=self.summary, wraplength=550).grid(row=0, column=0, sticky="ew", pady=5)
        self.canvas = tk.Canvas(view, background="#f4f7fa", highlightthickness=0, width=550, height=380)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda event: self.draw())
        ttk.Label(view, text="格心取樣；色塊僅供視覺化").grid(row=2, column=0, sticky="w")
        self.warnings = tk.Text(view, height=4, wrap="word", state="disabled")
        self.warnings.grid(row=3, column=0, sticky="ew", pady=5)
        actions = ttk.Frame(self.win, padding=8)
        actions.grid(row=3, column=0, sticky="ew")
        ttk.Button(actions, text="計算直接照度", command=lambda: self.guard(self.calculate)).pack(side="left", padx=3)
        for extension, label in (("html", "匯出 HTML"), ("csv", "匯出 CSV"), ("json", "匯出 JSON")):
            button = ttk.Button(actions, text=label, state="disabled", command=lambda ext=extension: self.guard(lambda: self.export(ext)))
            button.pack(side="left", padx=3)
            self.export_buttons.append(button)
        ttk.Label(self.win, textvariable=self.status, wraplength=1100).grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))
        for var in (*self.variables.values(), *self.generator_vars.values()):
            var.trace_add("write", lambda *args: self.invalidate())

    def _build_sources(self):
        box = ttk.Frame(self.win, padding=8)
        box.grid(row=1, column=0, sticky="ew")
        box.columnconfigure(1, weight=1)
        buttons = ttk.Frame(box)
        buttons.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        ttk.Button(buttons, text="匯入 IES／LDT", command=lambda: self.guard(self.import_source)).pack(fill="x", pady=3)
        ttk.Button(buttons, text="移除選取來源", command=lambda: self.guard(self.remove_source)).pack(fill="x", pady=3)
        self.source_tree = ttk.Treeview(box, columns=("id", "format", "model", "hash"), show="headings", height=3, selectmode="browse")
        for key, label, width in (("id", "來源 ID", 65), ("format", "格式", 65), ("model", "燈具／檔案", 260), ("hash", "來源 SHA-256", 470)):
            self.source_tree.heading(key, text=label)
            self.source_tree.column(key, width=width, minwidth=width, stretch=(key == "model"))
        self.source_tree.grid(row=0, column=1, sticky="ew")
        scroll = ttk.Scrollbar(box, orient="horizontal", command=self.source_tree.xview)
        scroll.grid(row=1, column=1, sticky="ew")
        self.source_tree.configure(xscrollcommand=scroll.set)
        vscroll = ttk.Scrollbar(box, orient="vertical", command=self.source_tree.yview)
        vscroll.grid(row=0, column=2, sticky="ns")
        self.source_tree.configure(yscrollcommand=vscroll.set)

    def _build_form(self, form):
        form.columnconfigure(0, weight=1)
        form.rowconfigure(4, weight=1)
        room = ttk.LabelFrame(form, text="房間與取樣", padding=5)
        room.grid(row=0, column=0, sticky="ew")
        room.columnconfigure(1, weight=1)
        for row, (key, label, initial) in enumerate(FIELDS):
            self.variables[key] = tk.StringVar(value=initial)
            ttk.Label(room, text=label).grid(row=row, column=0, sticky="w", padx=3)
            ttk.Entry(room, textvariable=self.variables[key], width=12).grid(row=row, column=1, sticky="ew", pady=2)
        gen = ttk.LabelFrame(form, text="明確產生規則排列（會取代下方配置）", padding=5)
        gen.grid(row=1, column=0, sticky="ew", pady=5)
        for row, (key, label) in enumerate((("source", "配光 ID"), ("rows", "列數 (Y)"), ("cols", "欄數 (X)"), ("height", "安裝高度 (m)"))):
            var = self.generator_vars[key] = tk.StringVar(value="")
            ttk.Label(gen, text=label).grid(row=row, column=0, sticky="w")
            if key == "source":
                self.source_choice = ttk.Combobox(gen, textvariable=var, values=(), state="readonly", width=12)
                self.source_choice.grid(row=row, column=1, sticky="ew")
            else:
                ttk.Entry(gen, textvariable=var, width=12).grid(row=row, column=1, sticky="ew", pady=1)
        ttk.Button(gen, text="產生可編輯配置", command=lambda: self.guard(self.generate)).grid(row=4, column=0, columnspan=2, sticky="ew", pady=3)
        ttk.Label(form, text="燈具配置 CSV：ID,x,y,z,yaw,scale（m、度；scale 為 0–1 配光倍率）", wraplength=370).grid(row=2, column=0, sticky="w")
        ttk.Label(form, text="原點在左下；所有燈具朝下，不支援傾斜。yaw 由上往下看逆時針；yaw=0 時檔案 C0 朝 +X、C90 朝 +Y；檔案軸向不一定對應燈殼正面。", wraplength=370).grid(row=3, column=0, sticky="w", pady=3)
        # Editable CSV must never be rewritten by a language switch.
        self.schedule = native_tk.Text(form, height=5, width=44, wrap="none", undo=True)
        self.schedule.grid(row=4, column=0, sticky="nsew")
        self.schedule.bind("<<Modified>>", self.schedule_changed)
        scroll = ttk.Scrollbar(form, orient="vertical", command=self.schedule.yview)
        scroll.grid(row=4, column=1, sticky="ns")
        self.schedule.configure(yscrollcommand=scroll.set)
        xscroll = ttk.Scrollbar(form, orient="horizontal", command=self.schedule.xview)
        xscroll.grid(row=5, column=0, sticky="ew")
        self.schedule.configure(xscrollcommand=xscroll.set)

    def fields(self):
        return {key: var.get() for key, var in self.variables.items()}

    def fingerprint(self):
        return (tuple(sorted(self.fields().items())), self.schedule.get("1.0", "end-1c"),
                tuple(sorted((key, var.get()) for key, var in self.generator_vars.items())),
                tuple(sorted((key, source.source_sha256) for key, source in self.sources.items())))

    def invalidate(self):
        self.result = self.result_fingerprint = None
        self.summary.set("尚無有效計算結果。")
        self.status.set("輸入已變更；請重新計算後匯出。")
        for button in self.export_buttons:
            button.configure(state="disabled")
        if hasattr(self, "canvas"):
            self.canvas.delete("all")
        if hasattr(self, "warnings"):
            self.warnings.configure(state="normal")
            self.warnings.delete("1.0", "end")
            self.warnings.configure(state="disabled")

    def schedule_changed(self, event=None):
        if self.schedule.edit_modified():
            self.schedule.edit_modified(False)
            self.invalidate()

    def guard(self, action):
        try:
            return action()
        except Exception as error:
            self.invalidate()
            self.status.set(str(error))
            messagebox.showerror("操作失敗", str(error), parent=self.win)

    def import_source(self):
        path = filedialog.askopenfilename(parent=self.win, title="匯入 IES／LDT", filetypes=[("IES / LDT", "*.ies *.IES *.ldt *.LDT"), ("All files", "*")])
        if not path:
            return
        self.invalidate()
        from .photometry import load_photometry
        source = load_photometry(path)
        existing = next((key for key, item in self.sources.items() if item.source_sha256 == source.source_sha256), None)
        if existing is not None:
            self.source_tree.selection_set(existing)
            self.source_tree.see(existing)
            return
        from .lighting_direct import MAX_TOTAL_PHOTOMETRIC_SAMPLES
        samples = sum(len(item.c_angles_deg) * len(item.gamma_angles_deg) for item in self.sources.values())
        samples += len(source.c_angles_deg) * len(source.gamma_angles_deg)
        if samples > MAX_TOTAL_PHOTOMETRIC_SAMPLES:
            raise ValueError("Combined imported photometry exceeds the sample budget")
        key = f"P{self.next_source_id}"
        if len(self.sources) >= 32:
            raise ValueError("請匯入 1–32 個有效配光來源。")
        self.next_source_id += 1
        self.sources[key] = source
        self.source_tree.insert("", "end", iid=key, values=(key, source.format, i18n.verbatim(f"{source.luminaire} / {source.source_name}"), source.source_sha256))
        self.source_tree.selection_set(key)
        self.source_choice.configure(values=tuple(self.sources))

    def remove_source(self):
        selected = self.source_tree.selection()
        if not selected:
            return
        self.invalidate()
        for key in selected:
            self.sources.pop(key, None)
            self.source_tree.delete(key)
        self.source_choice.configure(values=tuple(self.sources))
        if self.generator_vars["source"].get() not in self.sources:
            self.generator_vars["source"].set("")

    def generate(self):
        self.invalidate()
        values = {key: var.get() for key, var in self.generator_vars.items()}
        text = regular_schedule(self.fields(), values["source"], values["rows"], values["cols"], values["height"], self.sources)
        self.schedule.delete("1.0", "end")
        self.schedule.insert("1.0", text)
        self.schedule.edit_modified(False)

    def calculate(self):
        self.invalidate()
        # Consume a pending Text modified event before publishing a fresh result.
        self.schedule.edit_modified(False)
        from .lighting_direct import calculate_direct
        scene = parse_scene(self.fields(), self.schedule.get("1.0", "end-1c"), self.sources)
        signature = self.fingerprint()
        result = calculate_direct(dict(self.sources), scene)
        if signature != self.fingerprint():
            raise ValueError("輸入已變更；請重新計算後匯出。")
        self.result, self.result_fingerprint = result, signature
        s = result["summary"]
        uniformity = lambda key: "N/A" if s[key] is None else f"{s[key]:.3f}"
        self.summary.set(f"維護後取樣直接照度\n平均 {s['average_lux']:.2f} lx  |  最小 {s['minimum_lux']:.2f} lx  |  最大 {s['maximum_lux']:.2f} lx\n初始平均 {s['initial_average_lux']:.2f} lx\nEmin/Eavg: {uniformity('uniformity_min_avg')}  |  Emin/Emax: {uniformity('uniformity_min_max')}")
        self.warnings.configure(state="normal")
        self.warnings.insert("1.0", "\n".join(map(str, result.get("warnings", ()))))
        self.warnings.configure(state="disabled")
        self.status.set(LIMITATION)
        self.draw()
        for button in self.export_buttons:
            button.configure(state="normal")

    def export(self, extension):
        if self.result is None or self.result_fingerprint != self.fingerprint():
            raise ValueError("輸入已變更；請重新計算後匯出。")
        result, signature = self.result, self.result_fingerprint
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension="." + extension, initialfile="direct_lighting." + extension, filetypes=[(extension.upper(), "*." + extension)])
        if not path:
            return
        # Save dialogs run a nested event loop: inputs can change while open.
        if self.result is not result or self.result_fingerprint != signature or signature != self.fingerprint():
            raise ValueError("輸入已變更；請重新計算後匯出。")
        from .lighting_direct_report import direct_html, grid_csv
        content = direct_html(result) if extension == "html" else grid_csv(result) if extension == "csv" else json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        from .utils import atomic_text
        atomic_text(path, content)
        self.status.set("已匯出: " + i18n.verbatim(Path(path).name))

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")
        if self.result is None:
            return
        if self.result_fingerprint != self.fingerprint():
            self.invalidate()
            return
        from .lighting_direct import contour_segments
        from .lighting_direct_report import colour, contour_levels
        result, scene = self.result, self.result["scene"]
        width, height = max(canvas.winfo_width(), 100), max(canvas.winfo_height(), 100)
        scale = min(max(width - 110, 1) / scene["length_m"], max(height - 95, 1) / scene["width_m"])
        left, bottom = 48, height - 50
        def point(x, y):
            return left + x * scale, bottom - y * scale
        grid = result["grid"]
        xs, ys, lux = grid["x_m"], grid["y_m"], grid["lux"]
        maximum = result["summary"]["maximum_lux"]
        minimum = result["summary"]["minimum_lux"]
        dx = (scene["length_m"] - 2 * scene["edge_m"]) / scene["nx"]
        dy = (scene["width_m"] - 2 * scene["edge_m"]) / scene["ny"]
        for iy, y in enumerate(ys):
            for ix, x in enumerate(xs):
                color = colour(lux[iy][ix], minimum, maximum)
                canvas.create_rectangle(*point(x - dx / 2, y - dy / 2), *point(x + dx / 2, y + dy / 2), fill=color, outline="")
        levels = contour_levels(result)
        for level, segments in contour_segments(result, levels).items():
            for a, b in segments:
                canvas.create_line(*point(*a), *point(*b), fill="#fff", width=1)
        canvas.create_rectangle(*point(0, 0), *point(scene["length_m"], scene["width_m"]), outline="#263342", width=2)
        for number, fixture in enumerate(scene["fixtures"], 1):
            x, y = point(fixture["x_m"], fixture["y_m"])
            canvas.create_oval(x-4, y-4, x+4, y+4, fill="#fff", outline="#111", width=1)
            yaw = math.radians(fixture["yaw_deg"])
            canvas.create_line(x, y, x+12*math.cos(yaw), y-12*math.sin(yaw), fill="#111", arrow="last")
            if len(scene["fixtures"]) <= 40:
                canvas.create_text(x+5, y-7, text=f"{number}:{fixture['photometry']}", anchor="sw", fill="#111")
        canvas.create_text(left, bottom+15, text="(0, 0)", anchor="w")
        canvas.create_text(left+scene["length_m"]*scale, bottom+15, text=f"X {scene['length_m']:g} m", anchor="e")
        canvas.create_text(left, bottom-scene["width_m"]*scale-12, text=f"Y {scene['width_m']:g} m", anchor="w")
        canvas.create_text(left, height-10, text=f"{minimum:.1f} → {maximum:.1f} lx   |   等照度線: " + ", ".join(f"{level:.1f}" for level in levels) + " lx", anchor="w")


def open_direct_lighting(parent):
    """Open an independent explicit-input direct lighting workspace."""
    return DirectLightingWindow(parent)
