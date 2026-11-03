"""Pressure-aware dry-bulb / humidity-ratio chart using native Tk Canvas."""

import math
try:
    from .localized_tk import tk
    _Canvas = tk.Canvas
except ImportError:
    tk = None
    _Canvas = object

from .utils import MW_RATIO, sat_pa


def chart_data(state, comparison=None):
    pressure = state["pressure_kpa"]
    temperature = state["t"]
    temperatures = [temperature] + ([comparison["t"]] if comparison else [])
    low = max(-60, min(-10, math.floor((min(temperatures) - 12) / 10) * 10))
    high = min(90, max(50, math.ceil((max(temperatures) + 12) / 10) * 10))
    maximum = max(30.0, max(state["w"], comparison["w"] if comparison else 0) * 1000 * 1.3)
    step = 5 * 10 ** max(0, math.floor(math.log10(maximum / 30)))
    maximum = math.ceil(maximum / step) * step
    curves = []
    for rh in range(10, 101, 10):
        points = []
        for index in range(241):
            t = low + (high - low) * index / 240
            pw = sat_pa(t) * rh / 100
            if pw >= pressure * 1000:
                continue
            w = MW_RATIO * pw / (pressure * 1000 - pw) * 1000
            if 0 <= w <= maximum * 1.03:
                points.append((t, w))
        curves.append({"rh": rh, "points": points})
    enthalpy_lines, wetbulb_lines = [], []
    samples = [low + (high - low) * j / 240 for j in range(241)]

    def physical(t, w):
        pw = sat_pa(t)
        return (0 <= w * 1000 <= maximum and
                (pw >= pressure * 1000 or w <= MW_RATIO * pw / (pressure * 1000 - pw)))

    hmax = 1.006 * high + maximum / 1000 * (2501 + 1.86 * high)
    hstep = max(10, math.ceil(hmax / 160) * 10)
    for h in range(math.ceil(1.006 * low / hstep) * hstep, math.ceil(hmax), hstep):
        points = [(t, (h - 1.006*t)/(2501+1.86*t)*1000) for t in samples
                  if physical(t, (h - 1.006*t)/(2501+1.86*t))]
        if len(points) > 1:
            enthalpy_lines.append(dict(value=h, points=points))
    # Same liquid-water / ice equations as engine.wetbulb, without iterative inversion.
    for wb in range(math.ceil(low / 5)*5, math.floor(high)+1, 5):
        pw = sat_pa(wb)
        if pw >= pressure * 1000:
            continue
        ws = MW_RATIO * pw / (pressure * 1000 - pw)
        points = []
        for t in samples:
            if t < wb:
                continue
            w = (((2501-2.326*wb)*ws - 1.006*(t-wb))/(2501+1.86*t-4.186*wb)
                 if wb >= 0 else ((2830-.24*wb)*ws-1.006*(t-wb))/(2830+1.86*t-2.1*wb))
            if physical(t, w):
                points.append((t, w*1000))
        if len(points) > 1:
            wetbulb_lines.append(dict(value=wb, points=points))
    return {
        "t_min": low,
        "t_max": high,
        "w_max_gkg": maximum,
        "pressure_kpa": pressure,
        "curves": curves,
        "enthalpy_lines": enthalpy_lines,
        "wetbulb_lines": wetbulb_lines,
        "point": (temperature, state["w"] * 1000),
    }


class AirChart(_Canvas):
    def __init__(self, parent, family="TkDefaultFont"):
        super().__init__(parent, height=360, bg="white", highlightthickness=0)
        self.family = family
        self.stale = False
        self.state = None
        self.comparison = None
        self.plot_data = None
        self.point_xy = None
        self.bind("<Configure>", lambda event: self.redraw())
        self.clear()

    def clear(self):
        self.stale = False
        self.state = None
        self.comparison = None
        self.plot_data = None
        self.point_xy = None
        self.delete("all")
        self.create_text(
            25,
            25,
            text="填入有效溫濕度後，線圖會即時標示目前狀態。",
            anchor="nw",
            fill="#587084",
            font=(self.family, 10),
        )

    def set_state(self, state, comparison=None):
        self.stale = False
        self.state = dict(state)
        self.comparison = dict(comparison) if comparison else None
        self.plot_data = chart_data(state, comparison)
        self.redraw()

    def separate_labels(self, top, bottom, left=None, right=None, shortened=False):
        """Move the A / B text blocks apart vertically when they would cover each other."""
        a, b = self.bbox("state_label_bg"), self.bbox("comparison_label_bg")
        if not a or not b or a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]:
            return
        upper, lower = ("state_label", "comparison_label") if a[1] <= b[1] else ("comparison_label", "state_label")
        ub, lb = (a, b) if upper == "state_label" else (b, a)
        gap = ub[3] - lb[1] + 3
        # A few pixels beyond the plot box are free: the caption above and the axis ticks below sit further out.
        if lb[3] + gap <= bottom + 4:
            self.move(lower, 0, gap), self.move(lower + "_bg", 0, gap)
        elif ub[1] - gap >= top - 2:
            self.move(upper, 0, -gap), self.move(upper + "_bg", 0, -gap)
        elif left is not None and right is not None:
            # No vertical room (smallest window, wider native fonts): put the lower caption beside the upper one.
            to_right = ub[2] - lb[0] + 6
            to_left = lb[2] - ub[0] + 6
            if lb[2] + to_right <= right:
                self.move(lower, to_right, 0), self.move(lower + "_bg", to_right, 0)
            elif lb[0] - to_left >= left:
                self.move(lower, -to_left, 0), self.move(lower + "_bg", -to_left, 0)
            elif not shortened:
                # Neither direction has room: keep the temperature / humidity line and drop the enthalpy line
                # (A-B enthalpy difference stays in the line below the chart), then separate again.
                first_line = str(self.itemcget(lower, "text")).split("\n")[0]
                self.itemconfigure(lower, text=first_line)
                self.coords(lower + "_bg", *self.bbox(lower))
                self.separate_labels(top, bottom, left, right, True)

    def mark_stale(self):
        if self.state is None:
            self.clear()
        else:
            self.stale = True
            self.redraw()

    def redraw(self):
        if self.state is None:
            self.clear()
            return
        self.delete("all")
        data = self.plot_data
        width, height = max(self.winfo_width(), 320), max(self.winfo_height(), 200)
        left, top, right, bottom = 52, 70, width - 22, height - 55
        for index in range(48):
            fraction=index/47
            color='#'+''.join(f'{round(a+(b-a)*fraction):02x}' for a,b in zip((238,246,255),(244,238,250)))
            self.create_rectangle(0,height*index/48,width,height*(index+1)/48+1,
                                  fill=color,outline=color,tags="glass_background")
        self.create_rectangle(left,top,right,bottom,fill="#FAFCFF",outline="#DAE3F0",tags="plot_background")

        def xy(t, w):
            return (
                left
                + (t - data["t_min"])
                / (data["t_max"] - data["t_min"])
                * (right - left),
                bottom - w / data["w_max_gkg"] * (bottom - top),
            )

        self.create_text(
            left,
            13,
            text=f"空氣線圖  P={data['pressure_kpa']:g} kPa(abs)",
            anchor="w",
            font=(self.family, 10, "bold"),
            fill="#18334d",
        )
        for index in range(7):
            value = data["w_max_gkg"] * index / 6
            _, y = xy(data["t_min"], value)
            self.create_line(left, y, right, y, fill="#e4ebf0")
            self.create_text(
                left - 7,
                y,
                text=f"{value:.3g}",
                anchor="e",
                font=(self.family, 8),
                fill="#587084",
            )
        ticks = list(
            range(
                math.ceil(data["t_min"] / 10) * 10,
                math.floor(data["t_max"] / 10) * 10 + 1,
                10,
            )
        )
        for value in ticks:
            x, _ = xy(value, 0)
            self.create_line(x, top, x, bottom, fill="#e4ebf0")
            self.create_text(
                x, bottom + 12, text=str(value), font=(self.family, 8), fill="#587084"
            )
        for curve in data["curves"]:
            points = [xy(*point) for point in curve["points"]]
            if len(points) < 2:
                continue
            saturated = curve["rh"] == 100
            self.create_line(
                *[v for point in points for v in point],
                fill="#2668a6" if saturated else "#a8becb",
                width=2 if saturated else 1,
                tags=("curve", f"rh_{curve['rh']}"),
            )
            if curve["rh"] in (20, 40, 60, 80, 100):
                label = points[min(len(points) - 1, int(len(points) * 0.80))]
                self.create_text(
                    *label,
                    text=f"{curve['rh']}%",
                    anchor="sw",
                    font=(self.family, 8),
                    fill="#2668a6",
                    tags="curve_label",
                )
        for key, color, tag, prefix in (("enthalpy_lines", "#94b5a3", "enthalpy", "h="),
                                        ("wetbulb_lines", "#c6bba2", "wetbulb", "WB=")):
            for line in data[key]:
                points = [xy(*point) for point in line["points"]]
                self.create_line(*[v for point in points for v in point], fill=color,
                                 dash=(2, 5), tags=tag)
                if width >= 650 and line["value"] % (20 if key == "enthalpy_lines" else 10) == 0:
                    label = points[int(len(points)*(.65 if key == "enthalpy_lines" else .35))]
                    self.create_text(*label, text=prefix+str(line["value"]), fill=color,
                                     font=(self.family, 8), tags=tag+"_label")
        self.create_line(left, top, left, bottom, right, bottom, fill="#587084")
        self.create_text(
            (left + right) / 2,
            height - 28,
            text="乾球溫度（°C）",
            font=(self.family, 9),
            fill="#18334d",
        )
        self.create_text(
            right,
            60,
            text="含濕比 g/kg乾空氣",
            anchor="e",
            font=(self.family, 9),
            fill="#18334d",
        )
        self.create_text(left, 27, text="綠虛線：等焓｜褐虛線：等濕球", anchor="nw", width=max(120, width - left - 10),
                         fill="#587084", font=(self.family, 8), tags="legend")
        x, y = xy(*data["point"])
        self.point_xy = x, y
        self.create_line(
            x, y, x, bottom, fill="#c33e50", dash=(3, 3), tags="point_guide"
        )
        self.create_line(left, y, x, y, fill="#c33e50", dash=(3, 3), tags="point_guide")
        self.create_oval(
            x - 5,
            y - 5,
            x + 5,
            y + 5,
            fill="#c33e50",
            outline="white",
            width=1.5,
            tags="state_point",
        )
        state = self.state
        label = ("上次有效結果" if self.stale else "A" if self.comparison else "目前") + f" {state['t']:g}°C / {state['rh']:g}%RH\nw={state['w']*1000:.3f} g/kg，h={state['h']:.2f} kJ/kg"
        anchor = "se" if x > (left + right) / 2 else "sw"
        label_x = x - 10 if anchor == "se" else x + 10
        label_y = max(top + 45, min(bottom - 5, y - 9))
        self.create_text(
            label_x,
            label_y,
            text=label,
            anchor=anchor,
            font=(self.family, 9, "bold"),
            fill="#a7283a",
            tags="state_label",
        )
        self.create_rectangle(*self.bbox("state_label"), fill="white", outline="white", tags="state_label_bg")
        self.tag_lower("state_label_bg", "state_label")
        if self.comparison:
            b = self.comparison
            xb, yb = xy(b["t"], b["w"] * 1000)
            self.create_line(x, y, xb, yb, fill="#6b7280", dash=(5, 4), arrow="last", tags="comparison_line")
            self.tag_lower("comparison_line", "state_point")
            self.create_oval(xb-5, yb-5, xb+5, yb+5, fill="#047c88", outline="white", tags="comparison_point")
            self.create_text(max(left+60, min(right-60, xb)), max(top+15, min(bottom-42, yb+12)),
                             text=f"B {b['t']:g}°C / {b['rh']:g}%RH\nh={b['h']:.2f} kJ/kg", anchor="n",
                             fill="#047c88", font=(self.family, 9, "bold"), tags="comparison_label")
            self.create_rectangle(*self.bbox("comparison_label"), fill="white", outline="white", tags="comparison_label_bg")
            self.tag_lower("comparison_label_bg", "comparison_label")
            self.separate_labels(top, bottom, left, right)
            self.create_text(left, height-9, anchor="w",
                             text=f"A−B：Δh={state['h']-b['h']:.3f} kJ/kg｜Δw={(state['w']-b['w'])*1000:.3f} g/kg",
                             fill="#18334d", font=(self.family, 9, "bold"), tags="comparison_delta")
        if self.stale:
            self.create_text((left + right) / 2, top + 12,
                             text="上次有效結果｜待重算", fill="#b45309",
                             font=(self.family, 11, "bold"), tags="stale_label")

def _nice_step(span, target):
    """Human-readable interval with a bounded number of grid lines."""
    raw = span / target
    power = 10 ** math.floor(math.log10(raw))
    return next(x * power for x in (1, 2, 5, 10) if x * power >= raw)


def _ticks(low, high, step):
    start, end = math.ceil(low / step - 1e-9), math.floor(high / step + 1e-9)
    return [round(i * step, 10) for i in range(start, end + 1)]


def full_chart_data(state, comparison=None):
    """SI chart geometry, clipped to the unsaturated domain at the actual pressure.

    w is displayed in g/kg dry air. h and v use kg dry air. The wet-bulb
    liquid/ice branches match engine.wetbulb, and are NOT constant-enthalpy
    approximations. Equations: ASHRAE Fundamentals / PsychroLib SI functions.
    https://psychrometrics.github.io/psychrolib/api_docs.html
    """
    pressure = float(state["pressure_kpa"])
    if not math.isfinite(pressure) or not 60 <= pressure <= 120:
        raise ValueError("Chart pressure must be within 60–120 kPa(abs)")
    if comparison and not math.isclose(comparison["pressure_kpa"], pressure, abs_tol=1e-9):
        raise ValueError("Both chart states must use the same pressure")
    states = [state] + ([comparison] if comparison else [])
    for item in states:
        if (not math.isfinite(item["t"]) or not -60 <= item["t"] <= 90 or
                not math.isfinite(item["w"]) or not 0 <= item["w"] <= 1):
            raise ValueError("Chart state is outside the supported model range")
    low = max(-60, min(-10, math.floor((min(s["t"] for s in states) - 5) / 5) * 5))
    high = min(90, max(55, math.ceil((max(s["t"] for s in states) + 5) / 5) * 5))
    maximum = max(35, max(s["w"] for s in states) * 1000 * 1.15)
    w_step = _nice_step(maximum, 35)
    maximum = min(1000, math.ceil(maximum / (5 * w_step)) * 5 * w_step)
    p_pa = pressure * 1000

    def saturation(t):
        pw = sat_pa(t)
        return MW_RATIO * pw / (p_pa - pw) * 1000 if pw < p_pa else math.inf

    for item in states:
        if item["w"] * 1000 > saturation(item["t"]) + 1e-6:
            raise ValueError("Chart state cannot be supersaturated")

    def margin(t, w):
        return min(w, maximum - w, saturation(t) - w)

    def clipped(fn, start=low, end=high, seeds=()):
        """Sample each monotone line and solve its physical-domain crossings.

        Endpoints are evaluated on the original equation, not clamped to a
        different curve. A single connected interval is valid for these line
        families. A numerical gap is never bridged across invalid samples.
        """
        if start >= end:
            return []
        samples = sorted(set([start + (end - start) * j / 480 for j in range(481)] +
                             [x for x in seeds if start <= x <= end]))
        result = []
        previous = None
        for t in samples:
            w = fn(t)
            valid = math.isfinite(w) and margin(t, w) >= -1e-9
            if previous is not None:
                pt, pw, was_valid = previous
                if valid != was_valid:
                    outside, inside = (pt, t) if valid else (t, pt)
                    for _ in range(45):
                        mid = (outside + inside) / 2
                        mw = fn(mid)
                        if math.isfinite(mw) and margin(mid, mw) >= 0:
                            inside = mid
                        else:
                            outside = mid
                    edge = (inside, fn(inside))
                    if not result or math.dist(result[-1], edge) > 1e-8:
                        result.append(edge)
                    if was_valid:
                        break
            if valid and (not result or math.dist(result[-1], (t, w)) > 1e-8):
                result.append((t, w))
            previous = t, w, valid
        return result if len(result) > 1 else []

    curves = []
    for rh in range(10, 101, 10):
        def ratio(t, rh=rh):
            pw = sat_pa(t) * rh / 100
            return MW_RATIO * pw / (p_pa - pw) * 1000 if pw < p_pa else math.inf
        curves.append(dict(rh=rh, points=clipped(ratio)))
    hmin = 1.006 * low
    hmax = 1.006 * high + maximum / 1000 * (2501 + 1.86 * high)
    h_step = max(5, _nice_step(hmax - hmin, 32))
    enthalpy_lines = []
    for h in _ticks(hmin, hmax, h_step):
        points = clipped(lambda t: (h - 1.006 * t) / (2501 + 1.86 * t) * 1000,
                         seeds=(h / 1.006,))
        if points:
            enthalpy_lines.append(dict(value=h, points=points))
    wetbulb_lines = []
    wb_step = max(1, _nice_step(high - low, 65))
    for wb in _ticks(low, high, wb_step):
        ws = saturation(wb) / 1000
        if not math.isfinite(ws):
            continue
        def ratio(t):
            if wb >= 0:
                return ((2501 - 2.326 * wb) * ws - 1.006 * (t - wb)) / (2501 + 1.86 * t - 4.186 * wb) * 1000
            return ((2830 - .24 * wb) * ws - 1.006 * (t - wb)) / (2830 + 1.86 * t - 2.1 * wb) * 1000
        points = clipped(ratio, max(low, wb))
        if points:
            wetbulb_lines.append(dict(value=wb, points=points))
    # v = R_da * (T + 273.15) * (1 + w / MW_RATIO) / P[kPa].
    vmin = .287042 * (low + 273.15) / pressure
    vmax = .287042 * (high + 273.15) * (1 + maximum / 1000 / MW_RATIO) / pressure
    v_step = max(.01, _nice_step(vmax - vmin, 26))
    volume_lines = []
    for v in _ticks(vmin, vmax, v_step):
        points = clipped(lambda t: MW_RATIO * (v * pressure / (.287042 * (t + 273.15)) - 1) * 1000,
                         seeds=(v * pressure / .287042 - 273.15,))
        if points:
            volume_lines.append(dict(value=v, points=points))
    drybulb_lines = [dict(value=t, points=[(t, 0), (t, min(maximum, saturation(t)))])
                    for t in _ticks(low, high, max(1, _nice_step(high - low, 80)))]
    humidity_lines = []
    for w in _ticks(0, maximum, w_step):
        points = clipped(lambda t: w)
        if points:
            humidity_lines.append(dict(value=w, points=points))
    return dict(t_min=low, t_max=high, w_max_gkg=maximum, pressure_kpa=pressure,
                curves=curves, enthalpy_lines=enthalpy_lines,
                wetbulb_lines=wetbulb_lines, volume_lines=volume_lines,
                drybulb_lines=drybulb_lines, humidity_lines=humidity_lines,
                w_step=w_step, h_step=h_step, wb_step=wb_step, v_step=v_step,
                point=(state["t"], state["w"] * 1000))


class FullAirChart(AirChart):
    """Detailed chart with one aspect-preserving viewport for every line family.

    The caller owns snapshot semantics. The dictionaries are copied by
    set_state, so later changes to the source cannot move A/B silently.
    """
    SHEET_WIDTH, SHEET_HEIGHT = 1440, 900

    def __init__(self, parent, family="TkDefaultFont"):
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0
        self._drag_origin = None
        super().__init__(parent, family)
        self.configure(cursor="hand2")
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self.zoom_at(1.2, e.x, e.y))
        self.bind("<Button-5>", lambda e: self.zoom_at(1 / 1.2, e.x, e.y))
        self.bind("<ButtonPress-1>", self._start_pan)
        self.bind("<B1-Motion>", self._pan)
        self.bind("<ButtonRelease-1>", self._end_pan)
        self.bind("<Double-Button-1>", lambda e: self.fit_view())

    def set_state(self, state, comparison=None):
        snapshot = dict(state)
        comparison_snapshot = dict(comparison) if comparison else None
        data = full_chart_data(snapshot, comparison_snapshot)
        self.stale = False
        self.state, self.comparison = snapshot, comparison_snapshot
        self.plot_data = data
        self.fit_view()

    def view_transform(self):
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        scale = min(width / self.SHEET_WIDTH, height / self.SHEET_HEIGHT) * self.zoom
        return (scale, (width - self.SHEET_WIDTH * scale) / 2 + self.pan_x,
                (height - self.SHEET_HEIGHT * scale) / 2 + self.pan_y)

    def fit_view(self):
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0
        self.redraw()
        return "break"

    def zoom_at(self, factor, x=None, y=None):
        width, height = self.winfo_width(), self.winfo_height()
        x, y = (width / 2 if x is None else x), (height / 2 if y is None else y)
        old = self.zoom
        self.zoom = max(1, min(6, self.zoom * factor))
        ratio = self.zoom / old
        self.pan_x = (self.pan_x + width / 2 - x) * ratio - width / 2 + x
        self.pan_y = (self.pan_y + height / 2 - y) * ratio - height / 2 + y
        if self.zoom == 1:
            self.pan_x = self.pan_y = 0.0
        self.redraw()
        return "break"

    def _wheel(self, event):
        if event.delta:
            self.zoom_at(1.2 if event.delta > 0 else 1 / 1.2, event.x, event.y)
        return "break"

    def _start_pan(self, event):
        self._drag_origin = event.x, event.y
        return "break"

    def _pan(self, event):
        if self._drag_origin:
            self.pan_x += event.x - self._drag_origin[0]
            self.pan_y += event.y - self._drag_origin[1]
            self._drag_origin = event.x, event.y
            self.redraw()
        return "break"

    def _end_pan(self, event):
        self._drag_origin = None
        return "break"

    def redraw(self):
        if self.state is None:
            self.clear()
            return
        self.delete("all")
        data = self.plot_data
        scale, ox, oy = self.view_transform()
        left, top, right, bottom = 115, 175, 1295, 755
        def screen(x, y):
            return ox + x * scale, oy + y * scale
        def xy(t, w):
            return (left + (t - data["t_min"]) / (data["t_max"] - data["t_min"]) * (right - left),
                    bottom - w / data["w_max_gkg"] * (bottom - top))
        def line(points, color, width=1, tag="", dash=None):
            if len(points) < 2:
                return
            coords = [v for p in points for v in screen(*p)]
            options = dict(fill=color, width=max(.5, width * scale), tags=tag)
            if dash:
                options["dash"] = dash
            self.create_line(*coords, **options)
        def label(x, y, text, color="#253748", size=11, anchor="center", tag="", angle=0, bold=False):
            self.create_text(*screen(x, y), text=text, fill=color, anchor=anchor,
                             font=(self.family, -max(7, round(size * scale)), "bold" if bold else "normal"),
                             tags=tag, angle=angle)
        def family(key, color, width, tag, dash=None):
            for row in data[key]:
                line([xy(*p) for p in row["points"]], color, width, tag, dash)
        # The paper and every label use the same transform, including during pan.
        self.create_rectangle(*screen(0, 0), *screen(self.SHEET_WIDTH, self.SHEET_HEIGHT),
                              fill="white", outline="white", tags="chart_sheet")
        label(65, 35, "完整空氣線圖", size=25, anchor="w", bold=True, tag="chart_title")
        label(65, 68, f"P = {data['pressure_kpa']:g} kPa(abs)  ·  SI", size=14, anchor="w", tag="pressure_label")
        label(1370, 35, "開啟當下快照", size=13, anchor="e", tag="snapshot_label")
        label(1370, 65, "滾輪縮放 · 拖曳平移 · 雙擊適合視窗", size=12, anchor="e")
        legend = [("RH  相對濕度 %", "#334e68"), ("h  焓 kJ/kg乾空氣", "#428064"),
                  ("WB  濕球 °C", "#9b642b"), ("v  比容 m³/kg乾空氣", "#76619a")]
        for index, (text, color) in enumerate(legend):
            x = 95 + index * 335
            line([(x, 107), (x + 25, 107)], color, 1.8)
            label(x + 34, 107, text, color, 13, "w", "legend")
        family("drybulb_lines", "#d5dfe6", .6, "drybulb_grid")
        family("humidity_lines", "#d5dfe6", .6, "humidity_grid")
        for row in data["drybulb_lines"]:
            if row["value"] % 5 == 0:
                line([xy(*p) for p in row["points"]], "#a9b8c4", .8, "major_grid")
        for row in data["humidity_lines"]:
            if abs(row["value"] / data["w_step"] % 5) < 1e-7:
                line([xy(*p) for p in row["points"]], "#a9b8c4", .8, "major_grid")
        family("enthalpy_lines", "#91b19d", .8, "enthalpy")
        family("wetbulb_lines", "#c8ac88", .7, "wetbulb", (3, 4))
        family("volume_lines", "#9d8ab5", .9, "volume", (5, 3))
        for curve in data["curves"]:
            points = [xy(*p) for p in curve["points"]]
            if len(points) < 2:
                continue
            saturated = curve["rh"] == 100
            line(points, "#1c354b" if saturated else "#60778a", 2 if saturated else 1,
                 ("curve", f"rh_{curve['rh']}"))
            pos = points[round((len(points) - 1) * (.78 if saturated else .83))]
            label(pos[0] + 3, pos[1] - 8, f"{curve['rh']}%", "#28465e", 12,
                  "s", "curve_label", bold=True)
        # A separate enthalpy ruler extrapolates each actual h curve outward.
        # Its labels never serve as wet-bulb labels or an assumed SHR scale.
        ruler = []
        for row in data["enthalpy_lines"]:
            points = row["points"]
            x, y = xy(*points[0]); x2, y2 = xy(*points[-1])
            length = math.hypot(x2 - x, y2 - y)
            if length == 0:
                continue
            dx, dy = (x2 - x) / length, (y2 - y) / length
            end = x - dx * 34, y - dy * 34
            ruler.append(end)
            line([(x, y), end], "#428064", .8, "enthalpy_tick")
            label(end[0] - dx * 12, end[1] - dy * 12, f"{row['value']:g}", "#286247", 11,
                  tag="enthalpy_label")
        line(ruler, "#428064", .8, "enthalpy_ruler")
        for row in data["wetbulb_lines"]:
            if row["value"] % 5:
                continue
            x, y = xy(*row["points"][0])
            label(x + 7, y + 7, f"WB {row['value']:g}", "#87551e", 10, "nw", "wetbulb_label")
        for row in data["volume_lines"]:
            points = row["points"]
            # Near the low-w end, separate from saturation and enthalpy labels.
            x, y = xy(*points[round((len(points) - 1) * .78)])
            xa, ya = xy(*points[0]); xb, yb = xy(*points[-1])
            angle = -math.degrees(math.atan2(yb - ya, xb - xa))
            if angle < -90:
                angle += 180
            label(x, y - 4, f"v {row['value']:.2f}", "#695087", 10, "s", "volume_label", angle)
        line([(left, bottom), (right, bottom), (right, top)], "#253748", 1.5, "axes")
        for t in _ticks(data["t_min"], data["t_max"], 5):
            x, y = xy(t, 0)
            line([(x, y), (x, y + 6)], "#253748", 1)
            label(x, bottom + 19, f"{t:g}", size=12, tag="drybulb_tick")
        for w in _ticks(0, data["w_max_gkg"], data["w_step"]):
            _, y = xy(data["t_max"], w)
            line([(right, y), (right + 5, y)], "#253748", .8)
            label(right + 10, y, f"{w:g}", size=10, anchor="w", tag="humidity_tick")
        label((left + right) / 2, bottom + 47, "乾球溫度（°C）", size=14, bold=True)
        label(1380, (top + bottom) / 2, "含濕比 g/kg乾空氣", size=13, angle=90, tag="humidity_axis_label")
        label(left + 150, top + 15, "外側綠色刻度：焓 h", "#286247", 12, "w")
        label(left + 150, top + 38, "褐色刻度：濕球 WB", "#87551e", 12, "w")
        # Small markers only inside the engineering grid; detailed values below.
        states = [(self.state, "A", "#bf3449", "state_point")]
        if self.comparison:
            states.append((self.comparison, "B", "#007c87", "comparison_point"))
            line([xy(*data["point"]), xy(self.comparison["t"], self.comparison["w"] * 1000)],
                 "#525b66", 2, "comparison_line", (5, 4))
        for index, (state, name, color, tag) in enumerate(states):
            x, y = xy(state["t"], state["w"] * 1000)
            if not index:
                self.point_xy = screen(x, y)
            line([(x, y), (x, bottom)], color, .8, "point_guide", (3, 4))
            line([(x, y), (right, y)], color, .8, "point_guide", (3, 4))
            radius = 6 if name == "A" else 4
            self.create_oval(*screen(x - radius, y - radius), *screen(x + radius, y + radius),
                             fill=color, outline="white", width=max(1, scale), tags=tag)
            label(x + (11 if name == "A" else -11), y + (-12 if name == "A" else 12),
                  name, color, 15, tag=tag + "_label", bold=True)
            summary = (f"{name}  {state['t']:g}°C  ·  {state['rh']:g}%RH  ·  "
                       f"w {state['w']*1000:.3f} g/kg  ·  h {state['h']:.2f} kJ/kg  ·  "
                       f"v {state['v_da']:.3f} m³/kg")
            label(80, 832 + index * 24, summary, color, 13, "w", "state_summary")
        label(1370, 883, "A／B連線僅比較端點，非設備過程保證。", size=11, anchor="e")
        if self.stale:
            label(720, 148, "上次有效結果｜待重算", "#b45309", 16, bold=True, tag="stale_label")
