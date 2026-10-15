"""Display formatting and label placement; never changes engineering states."""


def duct_dimensions(d):
    if d["shape"] == "方管":
        return f"方管 {d['w_mm']:.0f} × {d['h_mm']:.0f} mm"
    return f"圓管 ID {d['diameter_m'] * 1000:.1f} mm"


def engineering_result_rows(result):
    """Explicit display labels and units, without exposing internal variable names."""
    rows = []

    def add(data, definitions, prefix=""):
        for key, label, unit in definitions:
            if key in data:
                value = data[key]
                if value is None:
                    value = "待選型"
                rows.append((prefix + label, value, unit, "需求初估"))

    tool = result["tool"]
    if tool == "cleanroom":
        add(result, [("volume_m3", "室內容積", "m³"), ("ach", "回循環換氣次數", "1/h"),
                     ("dcc_cmh", "DCC 回風循環量", "CMH"), ("leakage_cmh", "正壓洩漏", "CMH"),
                     ("required_oa_cmh", "最低外氣需求", "CMH"), ("oa_cmh", "採用外氣量", "CMH"),
                     ("ffu_total_cmh", "FFU 總設計風量", "CMH"), ("ffu_unit_cmh", "單台 FFU 風量", "CMH"),
                     ("ffu_size", "FFU 模組尺寸", ""), ("ffu_count", "FFU 需求台數", "台"),
                     ("coverage_ratio", "天花板覆蓋率", "%"), ("ffu_fan_kw", "FFU 輸入電功率", "kW")])
    elif tool == "heat_loads":
        add(result, [("q_lighting_kw", "照明顯熱", "kW"), ("q_envelope_kw", "圍護顯熱", "kW"),
                     ("q_people_sensible_kw", "人員顯熱", "kW"), ("q_people_latent_kw", "人員潛熱", "kW"),
                     ("q_equipment_kw", "設備入室顯熱", "kW"), ("q_ffu_kw", "FFU 風機發熱", "kW"),
                     ("q_room_sensible_kw", "室內總顯熱", "kW"), ("q_dcc_kw", "DCC 顯熱需求初估", "kW"),
                     ("q_mau_kw", "MAU 外氣全熱", "kW"), ("q_total_kw", "冰機總冷量", "kW"),
                     ("q_total_rt", "冰機總冷凍噸", "US RT")])
    elif tool == "pumps":
        add(result, [("flow_lpm", "設計流量", "LPM"), ("head_m", "設計揚程", "m"),
                     ("hydraulic_power_kw", "水功率", "kW"), ("shaft_power_kw", "泵軸功率", "kW"),
                     ("motor_input_kw", "馬達輸入電功率", "kW"),
                     ("recommended_motor_kw", "建議馬達銘牌輸出", "kW")])
    elif tool == "electrical":
        add(result, [("current_a", "滿載運轉電流", "A"), ("design_breaker_a", "連續負載斷路器初估電流", "A"),
                     ("design_a", "配線設計電流", "A"), ("recommended_breaker_at", "初估斷路器級距", "AT")])
        if result.get("selected"):
            add(result["selected"], [("nfb_a", "配線保護候選", "AT"), ("size_mm2", "每相導線截面", "mm²"),
                                    ("runs", "並聯組數", "組"), ("drop_pct", "電壓降", "%")])
    elif tool == "water":
        add(result["thermal"], [("lpm", "設計循環水量", "LPM"), ("kw", "冷熱容量", "kW"), ("delta_t", "供回水溫差", "K")])
        add(result["pipe"], [("size", "建議公稱管徑", ""), ("id_mm", "參考內徑", "mm"),
                             ("velocity_mps", "實際管內流速", "m/s"), ("runs", "並聯支數", "支")])
        add(result.get("pressure", {}), [("friction_pa_m", "直管單位壓損", "Pa/m"),
                                        ("loss_pa", "最不利路徑壓損", "Pa"), ("head_m", "路徑損失水頭", "m")])
    elif tool == "duct":
        add(result, [("flow_cmh", "設計風量", "CMH")])
        for key, title in (("rectangle", "方管 "), ("round", "圓管 ")):
            add(result[key], [("w_mm", "寬度", "mm"), ("h_mm", "高度", "mm"),
                              ("velocity_mps", "實際風速", "m/s"), ("equivalent_diameter_m", "等摩擦當量直徑", "m"),
                              ("loss_pa", "路徑壓損", "Pa"), ("pressure_margin_pa", "靜壓餘量", "Pa")], title)
    elif tool == "lighting":
        add(result, [("area_m2", "地板照明面積", "m²"), ("quantity", "需求燈具數量", "盞"),
                     ("illuminance_lux", "平均照度", "Lux"), ("total_kw", "照明輸入電功率", "kW")])
    elif tool == "gas":
        add(result, [("standard_lpm", "標準流量", "SLPM"), ("actual_lpm", "實際流量", "ALPM"),
                     ("absolute_kpa", "管內絕對壓力", "kPa abs"), ("velocity_mps", "管內實際流速", "m/s")])
    elif tool == "air":
        add(result["state"], [("t", "乾球溫度", "°C"), ("rh", "相對濕度", "%RH"),
                              ("h", "比焓", "kJ/kg"), ("wetbulb_c", "濕球溫度", "°C"), ("dewpoint_c", "露點溫度", "°C")])
    elif tool == "units":
        rows = [("換算結果", value, unit, "等值換算") for unit, value in result["values"].items()]
    return rows


def annotate_states(ax, groups, fontsize=9):
    """Place exact point labels greedily in screen space after axis layout."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.transforms import Bbox

    renderer = ax.figure.canvas.get_renderer()
    bounds = ax.get_window_extent(renderer)
    occupied = []
    font = FontProperties(size=fontsize)
    candidates = [
        (8, 12),
        (8, -24),
        (-65, 12),
        (-65, -24),
        (12, 30),
        (-65, 30),
        (12, -44),
        (-65, -44),
        (35, 55),
        (-100, 55),
        (35, -64),
        (-100, -64),
    ]
    for (temperature, moisture), names in groups.items():
        from .i18n import translate

        label = translate("/".join(names))
        width, height, _ = renderer.get_text_width_height_descent(label, font, False)
        x, y = ax.transData.transform((temperature, moisture))
        best = None
        for dx, dy in candidates:
            px = min(max(x + dx, bounds.x0 + 4), bounds.x1 - width - 4)
            py = min(max(y + dy, bounds.y0 + 4), bounds.y1 - height - 4)
            box = Bbox.from_bounds(px - 3, py - 3, width + 6, height + 8)
            score = (
                sum(box.overlaps(other) for other in occupied) * 10000
                + (px - x) ** 2
                + (py - y) ** 2
            )
            if best is None or score < best[0]:
                best = score, px, py, box
        _, px, py, box = best
        occupied.append(box)
        ax.annotate(
            label,
            (temperature, moisture),
            xytext=((px - x) * 72 / ax.figure.dpi, (py - y) * 72 / ax.figure.dpi),
            textcoords="offset points",
            fontsize=fontsize,
            va="bottom",
            ha="left",
            bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=1.2),
            arrowprops=dict(arrowstyle="-", color="#718096", lw=0.5),
        )
