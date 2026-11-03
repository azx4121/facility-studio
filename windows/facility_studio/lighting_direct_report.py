"""Self-contained reports and CSV for calculated direct-light grids only."""

import csv
from html import escape
from io import StringIO
import math

from .i18n import localized_report, verbatim
from .lighting_direct import METHOD, contour_segments
from .version import REPORT_VERSION


UI_ENGLISH = {
    "直接照度計算報告": "Direct illuminance report",
    "僅直接光／點光源近似": "Direct only / point-source approximation",
    "非 DIALux 等價結果；未計算反射、遮擋陰影、日光與 UGR。": "Not DIALux-equivalent; reflections, obstruction shadows, daylight and UGR are not calculated.",
    "直接光平均照度（格點）": "Mean direct illuminance (samples)",
    "直接光最小照度（格點）": "Minimum direct illuminance (samples)",
    "直接光最大照度（格點）": "Maximum direct illuminance (samples)",
    "平面配置與直接光等照度線": "Layout and direct isolux lines",
    "色階為格心計算值；等照度線為格點間線性內插，僅繪至取樣範圍。": "Colours show cell-centre calculations; isolux lines are linear interpolations within the sample hull.",
    "坐標與計算條件": "Coordinates and calculation conditions",
    "工作面（距地面）": "Workplane height above floor",
    "邊緣內縮": "Boundary inset",
    "格心取樣": "Cell-centre samples",
    "維護係數（只乘一次）": "Maintenance factor (applied once)",
    "初始直接光平均照度": "Initial mean direct illuminance",
    "維護後直接光平均照度": "Maintained mean direct illuminance",
    "每盞位置與朝向": "Luminaire positions and orientation",
    "光度資料 ID": "Photometry ID",
    "光輸出倍率": "Light-output multiplier",
    "光度來源與追溯": "Photometric sources and traceability",
    "來源檔名": "Source filename",
    "光度格式": "Photometric format",
    "燈具名稱": "Luminaire name",
    "檔案光通量": "File luminous flux",
    "檔案輸入功率": "File input power",
    "來源內容 SHA256": "Source content SHA256",
    "解析與縮放紀錄": "Parsing and scaling record",
    "計算範圍與限制": "Calculation scope and limitations",
    "全部燈具垂直向下。yaw=0 時檔案 C0 指向 +x、C90 指向 +y；正 yaw 由上往下看逆時針轉向 +y。C0 不一定是燈具外殼的正面。": "All luminaires face downward. At yaw=0 the file C0 axis points along +x and C90 along +y; positive yaw rotates counter-clockwise toward +y as seen from above. C0 need not be the housing front.",
    "照度統計是所選格點的結果，不代表連續空間極值或法規符合。": "Statistics describe the selected samples, not continuous-space extrema or compliance.",
    "光輸出倍率不推估調光後的耗電；未採用照明利用係數 U。": "Light-output multipliers do not estimate dimmed electrical power; no utilization factor U is applied.",
    "此報告依本次匯入光度資料及配置計算，未讀取來源檔案的後續變更。": "This report uses the imported photometry and adopted layout; later source-file changes are not read into this result.",
    "未計算（零照度）": "Not calculated (zero illuminance)",
}


def _check(result):
    if not isinstance(result, dict) or result.get("method") != METHOD:
        raise ValueError("A calculated direct-light result is required")
    grid = result["grid"]
    if len(grid["lux"]) != len(grid["y_m"]) or any(len(row) != len(grid["x_m"]) for row in grid["lux"]):
        raise ValueError("Calculated grid dimensions are inconsistent")
    if not all(math.isfinite(v) and v >= 0 for row in grid["lux"] for v in row):
        raise ValueError("Calculated grid must be finite and nonnegative")


def grid_csv(result):
    _check(result)
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("x_m", "y_m", "workplane_m", "direct_initial_lux", "direct_maintained_lux"))
    grid = result["grid"]
    for j, y in enumerate(grid["y_m"]):
        for i, x in enumerate(grid["x_m"]):
            writer.writerow((f"{x:.9g}", f"{y:.9g}", f"{result['scene']['workplane_m']:.9g}",
                             f"{grid['initial_lux'][j][i]:.12g}", f"{grid['lux'][j][i]:.12g}"))
    return stream.getvalue()


def colour(value, low, high):
    t = min(1, max(0, (value - low) / (high - low))) if high > low else .5
    stops = ((49, 54, 149), (69, 117, 180), (116, 173, 209), (171, 217, 233),
             (255, 255, 191), (253, 174, 97), (244, 109, 67), (165, 0, 38))
    index = min(len(stops) - 2, int(t * (len(stops) - 1)))
    fraction = t * (len(stops) - 1) - index
    return "#" + "".join(f"{round(a + (b - a) * fraction):02x}" for a, b in zip(stops[index], stops[index + 1]))


def contour_levels(result):
    low, high = result["summary"]["minimum_lux"], result["summary"]["maximum_lux"]
    return [low + (high - low) * index / 6 for index in range(1, 6)] if high > low else []


def plan_svg(result):
    _check(result)
    scene, grid, summary = result["scene"], result["grid"], result["summary"]
    length, width = scene["length_m"], scene["width_m"]
    scale = min(690 / length, 420 / width)
    left, top = 65, 35
    def xy(x, y):
        return left + x * scale, top + (width - y) * scale
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 560" role="img" aria-label="Direct illuminance grid and luminaire layout">',
           '<rect width="840" height="560" fill="white"/>']
    step_x, step_y = (length - 2 * scene["edge_m"]) / scene["nx"], (width - 2 * scene["edge_m"]) / scene["ny"]
    for j, y in enumerate(grid["y_m"]):
        for i, x in enumerate(grid["x_m"]):
            px, py = xy(x - step_x / 2, y + step_y / 2)
            fill = colour(grid["lux"][j][i], summary["minimum_lux"], summary["maximum_lux"])
            svg.append(f'<rect x="{px:.4f}" y="{py:.4f}" width="{step_x * scale + .02:.4f}" height="{step_y * scale + .02:.4f}" fill="{fill}"/>')
    label_boxes = []
    fixture_points = [xy(row["x_m"], row["y_m"]) for row in scene["fixtures"]]
    for level_index, (level, segments) in enumerate(contour_segments(result, contour_levels(result)).items()):
        for a, b in segments:
            ax, ay = xy(*a); bx, by = xy(*b)
            svg.append(f'<path d="M{ax:.3f},{ay:.3f}L{bx:.3f},{by:.3f}" stroke="#111" stroke-width=".9" fill="none"/>')
        if segments:
            text = f"{level:.1f} lx"
            half_width = len(text) * 3.3 + 4
            target = (left + length * scale * (.2 + .15 * level_index), top + width * scale * (.2 if level_index % 2 == 0 else .75))
            candidates = []
            for line in segments[::max(1, len(segments) // 100)]:
                x, y = xy(*line[0])
                box = (x - half_width, y - 9, x + half_width, y + 8)
                if box[0] < left + 3 or box[2] > left + length * scale - 3 or box[1] < top + 3 or box[3] > top + width * scale - 3:
                    continue
                if any(not (box[2] + 6 < other[0] or other[2] + 6 < box[0] or box[3] + 6 < other[1] or other[3] + 6 < box[1]) for other in label_boxes):
                    continue
                if any(abs(x - fx) < half_width + 18 and abs(y - fy) < 25 for fx, fy in fixture_points):
                    continue
                candidates.append(((x - target[0]) ** 2 + (y - target[1]) ** 2, x, y, box))
            if candidates:
                _, x, y, box = min(candidates)
                label_boxes.append(box)
                svg.append(f'<rect x="{box[0]:.2f}" y="{box[1]:.2f}" width="{2 * half_width:.2f}" height="17" fill="white" fill-opacity=".9"/>')
                svg.append(f'<text x="{x:.2f}" y="{y + 4:.2f}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#111">{text}</text>')
    svg.append(f'<rect x="{left}" y="{top}" width="{length * scale:.3f}" height="{width * scale:.3f}" fill="none" stroke="#111" stroke-width="2"/>')
    for index, fixture in enumerate(scene["fixtures"], 1):
        x, y = xy(fixture["x_m"], fixture["y_m"])
        angle = math.radians(fixture["yaw_deg"])
        dx, dy = 15 * math.cos(angle), -15 * math.sin(angle)
        svg.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="white" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<path d="M{x:.3f},{y:.3f}l{dx:.3f},{dy:.3f}" stroke="#111" stroke-width="2"/>')
        if len(scene["fixtures"]) <= 40:
            svg.append(f'<rect x="{x + 5:.3f}" y="{y - 19:.3f}" width="18" height="15" fill="white" fill-opacity=".9"/>')
            svg.append(f'<text x="{x + 14:.3f}" y="{y - 7:.3f}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#111">{index}</text>')
    svg += [f'<text x="{left + length * scale / 2:.2f}" y="{top + width * scale + 25:.2f}" text-anchor="middle" font-size="13">x: {length:g} m</text>',
            f'<text x="{left - 8}" y="{top + width * scale / 2:.2f}" text-anchor="end" font-size="13">{width:g} m</text>',
            '<text x="30" y="20" font-size="13">+y ↑   +x →</text>',
            '<text x="65" y="500" font-size="12">○ luminaire   line = file C0 axis   lx = direct maintained illuminance</text>']
    for index in range(100):
        value = summary["minimum_lux"] + (summary["maximum_lux"] - summary["minimum_lux"]) * index / 99
        svg.append(f'<rect x="{65 + index * 5}" y="515" width="5.1" height="14" fill="{colour(value, summary["minimum_lux"], summary["maximum_lux"])}"/>')
    svg += [f'<text x="65" y="548" font-size="12">{summary["minimum_lux"]:.2f} lx</text>',
            f'<text x="565" y="548" font-size="12" text-anchor="end">{summary["maximum_lux"]:.2f} lx</text>', '</svg>']
    return "".join(svg)


@localized_report
def direct_html(result):
    from .html_report import _document, _table
    import json

    _check(result)
    scene, summary = result["scene"], result["summary"]
    def ratio(key):
        return f"{summary[key]:.4f}" if summary[key] is not None else "未計算（零照度）"
    metrics = [("直接光平均照度（格點）", f"{summary['average_lux']:,.2f} lx"),
               ("直接光最小照度（格點）", f"{summary['minimum_lux']:,.2f} lx"),
               ("直接光最大照度（格點）", f"{summary['maximum_lux']:,.2f} lx"),
               ("Emin/Eavg", ratio("uniformity_min_avg")), ("Emin/Emax", ratio("uniformity_min_max"))]
    content = '<p class="status">僅直接光／點光源近似。非 DIALux 等價結果；未計算反射、遮擋陰影、日光與 UGR。</p>'
    content += '<section>' + _table(metrics, ("項目", "計算結果")) + '</section>'
    content += '<section><h2>平面配置與直接光等照度線</h2>' + plan_svg(result)
    content += '<p>色階為格心計算值；等照度線為格點間線性內插，僅繪至取樣範圍。</p></section>'
    conditions = [("長×寬", f"{scene['length_m']:g} × {scene['width_m']:g} m"),
                  ("工作面（距地面）", f"{scene['workplane_m']:g} m"), ("邊緣內縮", f"{scene['edge_m']:g} m"),
                  ("格心取樣", f"{scene['nx']} × {scene['ny']}"), ("維護係數（只乘一次）", f"{scene['maintenance']:g}"),
                  ("初始直接光平均照度", f"{summary['initial_average_lux']:,.2f} lx"),
                  ("維護後直接光平均照度", f"{summary['average_lux']:,.2f} lx")]
    content += '<section><h2>坐標與計算條件</h2>' + _table(conditions) + '<p>全部燈具垂直向下。yaw=0 時檔案 C0 指向 +x、C90 指向 +y；正 yaw 由上往下看逆時針轉向 +y。C0 不一定是燈具外殼的正面。</p></section>'
    fixtures = [(str(index), verbatim(row["photometry"]), f"{row['x_m']:g}", f"{row['y_m']:g}",
                 f"{row['z_m']:g}", f"{row['yaw_deg']:g}", f"{row['multiplier']:g}")
                for index, row in enumerate(scene["fixtures"], 1)]
    content += '<section><h2>每盞位置與朝向</h2>' + _table(fixtures, ("編號", "光度資料 ID", "x [m]", "y [m]", "z [m]", "yaw [°]", "光輸出倍率")) + '</section>'
    content += '<section><h2>光度來源與追溯</h2>'
    for key, source in result["sources"].items():
        rows = [("光度資料 ID", verbatim(key)), ("來源檔名", verbatim(source["source_name"])),
                ("光度格式", verbatim(source["format"])), ("燈具名稱", verbatim(source["luminaire"])),
                ("檔案光通量", str(source["luminaire_lumens"]) + " lm" if source["luminaire_lumens"] is not None else "未提供"),
                ("檔案輸入功率", str(source["input_watts"]) + " W" if source["input_watts"] is not None else "未提供"),
                ("來源內容 SHA256", verbatim(source["source_sha256"])),
                ("解析與縮放紀錄", verbatim(json.dumps(source["metadata"], ensure_ascii=False, sort_keys=True)))]
        content += _table(rows)
    content += '</section><section><h2>計算範圍與限制</h2><p>照度統計是所選格點的結果，不代表連續空間極值或法規符合。</p><p>光輸出倍率不推估調光後的耗電；未採用照明利用係數 U。</p><p>此報告依本次匯入光度資料及配置計算，未讀取來源檔案的後續變更。</p><ul>'
    content += ''.join('<li>' + escape(text) + '</li>' for text in result.get("limitations", []) + result.get("warnings", []))
    content += '</ul><pre>E_initial = Σ I(C, gamma) × cos(gamma) / r² × multiplier\nE_maintained = E_initial × maintenance\nr [m], I [cd], E [lx]\nmethod: ' + METHOD + '</pre></section>'
    document = _document("直接照度計算報告", "V" + REPORT_VERSION + "｜僅直接光／點光源近似", content)
    css = '<style>main{max-width:980px}svg{display:block;width:100%;height:auto}section{break-inside:avoid}@media print{body{font-size:9pt}h2{font-size:12pt}section{margin-bottom:12px;padding:8px}th,td{padding:4px 6px}@page{size:A4 portrait;margin:13mm}}</style>'
    return document.replace('</head>', css + '</head>')
