"""Pressure-aware dry-bulb / humidity-ratio chart using native Tk Canvas."""

import math
from .localized_tk import tk

from .utils import MW_RATIO, sat_pa


def chart_data(state):
    pressure = state["pressure_kpa"]
    temperature = state["t"]
    low = max(-60, min(-10, math.floor((temperature - 12) / 10) * 10))
    high = min(90, max(50, math.ceil((temperature + 12) / 10) * 10))
    maximum = max(30.0, state["w"] * 1000 * 1.3)
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
    return {
        "t_min": low,
        "t_max": high,
        "w_max_gkg": maximum,
        "pressure_kpa": pressure,
        "curves": curves,
        "point": (temperature, state["w"] * 1000),
    }


class AirChart(tk.Canvas):
    def __init__(self, parent, family="TkDefaultFont"):
        super().__init__(parent, height=310, bg="white", highlightthickness=0)
        self.family = family
        self.stale = False
        self.state = None
        self.plot_data = None
        self.point_xy = None
        self.bind("<Configure>", lambda event: self.redraw())
        self.clear()

    def clear(self):
        self.stale = False
        self.state = None
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

    def set_state(self, state):
        self.stale = False
        self.state = dict(state)
        self.plot_data = chart_data(state)
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
        width, height = max(self.winfo_width(), 460), max(self.winfo_height(), 310)
        left, top, right, bottom = 58, 38, width - 40, height - 45

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
        self.create_line(left, top, left, bottom, right, bottom, fill="#587084")
        self.create_text(
            (left + right) / 2,
            height - 10,
            text="乾球溫度（°C）",
            font=(self.family, 9),
            fill="#18334d",
        )
        self.create_text(
            right,
            13,
            text="含濕比 g/kg乾空氣",
            anchor="e",
            font=(self.family, 9),
            fill="#18334d",
        )
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
        label = ("上次有效結果" if self.stale else "目前") + f" {state['t']:g}°C / {state['rh']:g}%RH\nw={state['w']*1000:.3f} g/kg，h={state['h']:.2f} kJ/kg"
        anchor = "ne" if x > (left + right) / 2 else "nw"
        label_x = x - 10 if anchor == "ne" else x + 10
        label_y = max(top + 10, min(bottom - 36, y + 9))
        self.create_text(
            label_x,
            label_y,
            text=label,
            anchor=anchor,
            font=(self.family, 9, "bold"),
            fill="#a7283a",
            tags="state_label",
        )
        if self.stale:
            self.create_text((left + right) / 2, top + 12,
                             text="上次有效結果｜待重算", fill="#b45309",
                             font=(self.family, 11, "bold"), tags="stale_label")
