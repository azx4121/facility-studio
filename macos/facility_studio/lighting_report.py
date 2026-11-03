"""Traceable FEED presentation for the existing single-type lumen method.

This module does not calculate a photometric grid. Unknown results stay None
in the structured report and are labelled explicitly in every presentation.
"""

from html import escape
import math

from .errors import ValidationError
from .i18n import localized_report, verbatim
from .version import REPORT_VERSION


CONTEXT_FIELDS = (
    ("report_project", "報告專案名稱"),
    ("report_room", "報告空間名稱"),
    ("report_fixture", "燈具廠牌／型號"),
    ("report_reference", "型錄／配光資料來源"),
    ("report_basis", "設計基準／U、M依據"),
)
SCOPE_NOTICE = "FEED 流明法初估；未計算逐點照度、均勻度、等照度線、直接／反射光或 UGR，不代表 DIALux 模擬或法規符合。"
UNKNOWN = "未計算"
MISSING = "未提供"


def capture_context(data):
    context = {}
    for key, _ in CONTEXT_FIELDS:
        value = data.get(key, "")
        if not isinstance(value, str) or len(value) > 500:
            raise ValidationError("報告欄位需為不超過 500 字的文字。", key)
        context[key] = value.strip()
    return context


def report_data(result):
    """Use calculated values only; never infer a room shape from area alone."""
    if result.get("tool") != "lighting":
        raise ValueError("Lighting report requires a lighting result")
    required = ("area_m2", "quantity", "watts", "lumens_per_lamp", "utilization",
                "maintenance", "illuminance_lux", "total_kw")
    for key in required:
        value = result.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Lighting report requires finite calculated values: " + key)
    if result["area_m2"] <= 0:
        raise ValueError("Lighting report requires a positive area")
    lux = result["illuminance_lux"]
    power_density = result["total_kw"] * 1000 / result["area_m2"]
    return {
        "method": "lumen_method", "scope": "FEED_estimate",
        "context": dict(result.get("report_context", {})),
        "average_lux": lux,
        "minimum_lux": None, "maximum_lux": None,
        "uniformity_min_avg": None, "uniformity_min_max": None,
        "direct_lux": None, "reflected_lux": None, "ugr": None,
        "grid": None, "isolux": None,
        "length_m": result.get("length_m"), "width_m": result.get("width_m"),
        "power_density_w_m2": power_density,
        "power_density_per_100_lux": power_density * 100 / lux if lux > 0 else None,
        "luminaire_flux_lm": result["lumens_per_lamp"],
        "total_luminaire_flux_lm": result["lumens_per_lamp"] * result["quantity"],
        "lamp_flux_lm": None,
    }


def _value(value, unit="", decimals=2):
    return MISSING if value is None else f"{value:,.{decimals}f}" + (" " + unit if unit else "")


def report_sections(result):
    """One source for TXT, standalone HTML and combined HTML sections."""
    data = report_data(result)
    context = data["context"]
    identity = [(label, verbatim(context[key]) if context.get(key) else MISSING)
                for key, label in CONTEXT_FIELDS]
    dimensions = (f"{data['length_m']:g} × {data['width_m']:g} m"
                  if data["length_m"] is not None and data["width_m"] is not None else MISSING)
    geometry = [
        ("計算面積", _value(result["area_m2"], "m²")),
        ("實際長×寬", dimensions),
        ("空間淨高（體積換算採用）", _value(result.get("room_height_m"), "m")),
        ("燈具安裝高度（K檢核採用）", _value(result.get("mount_h_m"), "m")),
        ("工作面高度（K檢核採用）", _value(result.get("work_h_m"), "m")),
        ("室指數 K", _value(result.get("room_index_k"), decimals=3)),
        ("照明利用率 U", f"{result['utilization']:g}"),
        ("維護係數 M", f"{result['maintenance']:g}"),
        ("反射率（天花板／牆／地板）", MISSING),
        ("計算網格／邊緣區", UNKNOWN),
    ]
    surface_rows = [
        ("計算範圍（流明法）", f"{data['average_lux']:,.1f}", UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN),
        ("地板", UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN),
        ("天花板", UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN),
        ("牆壁", UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN),
    ]
    fixture = context.get("report_fixture")
    fixtures = [("1", str(result["quantity"]), verbatim(fixture) if fixture else MISSING,
                 f"{data['luminaire_flux_lm']:,.1f}", MISSING, f"{result['watts']:g}",
                 f"{result['total_kw'] * 1000:,.1f}")]
    return data, identity, geometry, surface_rows, fixtures


def lighting_text_sections(result):
    data, identity, geometry, surfaces, fixtures = report_sections(result)
    lines = ["照明設計報告｜FEED 初估", SCOPE_NOTICE, "", "報告識別"]
    lines += [label + "：" + value for label, value in identity]
    lines += ["", "空間與計算條件"] + [label + "：" + value for label, value in geometry]
    lines += ["", "表面照度摘要", "表面｜Eavg [lx]｜Emin [lx]｜Emax [lx]｜Emin/Eavg｜Emin/Emax"]
    lines += ["｜".join(row) for row in surfaces]
    lines += ["", "燈具明細", "編號｜數量｜廠牌／型號｜完整燈具 [lm/盞]｜光源 [lm/盞]｜輸入 [W/盞]｜合計 [W]"]
    lines += ["｜".join(row) for row in fixtures]
    lines += ["完整燈具總光通量：" + _value(data["total_luminaire_flux_lm"], "lm", 1),
              "照明功率密度：" + _value(data["power_density_w_m2"], "W/m²"),
              "每 100 lx 功率密度：" + (_value(data["power_density_per_100_lux"], "W/m²/100 lx")
                                       if data["power_density_per_100_lux"] is not None else "不適用（平均照度為零）"),
              "", "尚需資料與後續檢核", *_requirements()]
    return "\n".join(lines)


def _requirements():
    return [
        "流明法平均值不是網格平均；不由平均照度推造最小值、最大值或均勻度。",
        "需提供原廠 IES／LDT 光度檔、每盞位置／方向、房間幾何、計算面與網格，才能進行逐點照度計算。",
        "需提供表面反射率並採用反射計算模型，才能取得直接／反射光與各表面結果。",
        "未讀取光度檔；型錄來源僅為文字記錄。完整燈具流明與光源流明不可混用。",
        "U、M與光效須另核對來源；目標照度比較不代表法規、眩光或均勻度符合。",
    ]


def lighting_html_sections(result, *, include_inputs=True):
    from .html_report import _table
    from .simple_reports import input_rows

    data, identity, geometry, surfaces, fixtures = report_sections(result)
    content = '<section class="lighting-identity"><h2>報告識別</h2>' + _table(identity) + '</section>'
    content += '<section><h2>空間與計算條件</h2>' + _table(geometry, ("項目", "採用條件")) + '</section>'
    content += '<section><h2>表面照度摘要</h2>' + _table(surfaces, ("表面", "Eavg [lx]", "Emin [lx]", "Emax [lx]", "Emin/Eavg", "Emin/Emax"))
    content += '<p class="muted">流明法平均值不是網格平均；不由平均照度推造最小值、最大值或均勻度。</p></section>'
    content += '<section><h2>燈具明細</h2>' + _table(fixtures, ("編號", "數量", "廠牌／型號", "完整燈具 [lm/盞]", "光源 [lm/盞]", "輸入 [W/盞]", "合計 [W]"))
    content += '<p>完整燈具總光通量：' + _value(data["total_luminaire_flux_lm"], "lm", 1) + '</p>'
    normalized = (_value(data["power_density_per_100_lux"], "W/m²/100 lx")
                  if data["power_density_per_100_lux"] is not None else "不適用（平均照度為零）")
    content += '<p>照明功率密度：' + _value(data["power_density_w_m2"], "W/m²") + '；每 100 lx 功率密度：' + normalized + '</p></section>'
    content += '<section><h2>尚需資料與後續檢核</h2><ul>' + ''.join('<li>' + escape(item) + '</li>' for item in _requirements()) + '</ul></section>'
    if include_inputs:
        conditions = input_rows(result)
        content += '<section><h2>採用輸入與公式</h2>'
        content += (_table(conditions, ("項目", "採用條件")) if conditions else '<p>採用輸入條件未附於此結果，請附原始輸入資料。</p>')
        content += '<pre>' + escape(str(result.get("formula", ""))) + '</pre></section>'
    return content


@localized_report
def lighting_html(result):
    from .html_report import _document
    from .simple_reports import presentation

    cards, _ = presentation(result)
    content = '<p class="status">' + escape(SCOPE_NOTICE) + '</p>'
    content += '<div class="kpi-grid">' + ''.join(
        '<div class="kpi-card"><p class="kpi-label">' + escape(label) + '</p><p class="kpi-value">' + escape(value) + '</p></div>'
        for label, value in cards) + '</div>'
    content += lighting_html_sections(result)
    if result.get("warnings"):
        content += '<section><h2>需確認的條件</h2><ul>' + ''.join('<li>' + escape(str(item)) + '</li>' for item in result["warnings"]) + '</ul></section>'
    document = _document("照明設計報告｜FEED 初估", "V" + REPORT_VERSION + "｜流明法／單一燈具型式", content)
    # Override the general landscape report only for this lighting document.
    css = '<style>main{max-width:980px}.kpi-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.lighting-identity td:first-child{width:28%}@media(max-width:650px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media print{body{font-size:9pt}.report-header{padding-bottom:8px}.report-header h1{font-size:19pt}section{margin-bottom:10px;padding:8px}h2{font-size:12pt;margin-bottom:6px}.kpi-grid{gap:6px;margin:8px 0}.kpi-card{padding:7px}.kpi-value{font-size:11pt;margin-bottom:0}th,td{padding:4px 6px}section{break-inside:avoid}h2{break-after:avoid}@page{size:A4 portrait;margin:13mm}}</style>'
    return document.replace('</head>', css + '</head>')
