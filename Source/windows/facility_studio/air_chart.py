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
            52,
            text="含濕比 g/kg乾空氣",
            anchor="e",
            font=(self.family, 9),
            fill="#18334d",
        )
        self.create_text(left, 35, text="綠虛線：等焓｜褐虛線：等濕球",
                         anchor="w", fill="#587084", font=(self.family, 8), tags="legend")
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
            self.create_text(left, height-9, anchor="w",
                             text=f"A−B：Δh={state['h']-b['h']:.3f} kJ/kg｜Δw={(state['w']-b['w'])*1000:.3f} g/kg",
                             fill="#18334d", font=(self.family, 9, "bold"), tags="comparison_delta")
        if self.stale:
            self.create_text((left + right) / 2, top + 12,
                             text="上次有效結果｜待重算", fill="#b45309",
                             font=(self.family, 11, "bold"), tags="stale_label")
