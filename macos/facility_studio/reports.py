from .gas_catalog import gas_label, CUSTOM_GAS
from .i18n import localized_report, verbatim
from .engine import pv_to_torr
from .schema import VERSION
from .version import REPORT_VERSION
from .utils import US_RT_KW, dewpoint
from .errors import InputError
from html import escape
import math
import re


SUMMARY_TITLE = "★ 核心工程設計量與設備選型總覽（Executive Design Summary）"
NOT_CALCULATED = "尚未計算"


def _numeric(value):
    """Accept finite result numbers without converting absent values into zero."""
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _num(row, *keys):
    for key in keys:
        value = _numeric(row.get(key))
        if value is not None:
            return value
    return None


def _fmt(value, unit="", digits=2):
    value = _numeric(value)
    if value is None:
        return NOT_CALCULATED
    number = f"{value:,.{digits}f}".rstrip("0").rstrip(".") if digits else f"{value:,.0f}"
    return number + (" " + unit if unit else "")


def _row(equipment, demand=NOT_CALCULATED, selection=NOT_CALCULATED,
         status="待資料", tone="warning"):
    return dict(equipment=equipment, demand=demand, selection=selection,
                status=status, tone=tone)


def _coil_kw(season):
    coils = [season.get(tag, {}) for tag in ("c1", "c2")]
    values = [_num(coil, "water_kw") for coil in coils]
    return sum(values) if all(v is not None for v in values) else None


def executive_summary(result):
    """Seven procurement rows for a full project or explicit quick-tool pipeline.

    A summary may describe a partial pipeline, but never invents a common water
    header, a main breaker, motor efficiency, or an equipment nameplate rating.
    Full-project exports still pass the strict completeness check in ``report``.
    """
    if not isinstance(result, dict):
        raise InputError("設計總覽需要計算結果。", code="incomplete_result")
    r = result
    if any(key in r for key in ("project", "effective_inputs", "zones")):
        _validate_full_result(r)
    pipeline = r.get("pipeline", r)
    if not isinstance(pipeline, dict):
        raise InputError("設計總覽需要計算結果。", code="incomplete_result")
    main = isinstance(r.get("project"), dict) and isinstance(r.get("summer"), dict)
    cr = r if main else pipeline.get("cleanroom", {})
    heat = r if main else pipeline.get("heat_loads", {})
    if r.get("tool") in ("cleanroom", "heat_loads"):
        cr = r if r["tool"] == "cleanroom" else cr
        heat = r if r["tool"] == "heat_loads" else heat
    cr = cr if isinstance(cr, dict) else {}
    heat = heat if isinstance(heat, dict) else {}
    inputs = r.get("effective_inputs", r.get("project", {}).get("inputs", {})) if main else cr
    inputs = inputs if isinstance(inputs, dict) else {}
    is_mau = not main or str(inputs.get("sys_type", "")).startswith("MAU")
    rows = []

    # FFU sizing keeps design airflow separate from installed capacity.
    ffu_flow = _num(cr, "ffu_total_cmh")
    count = _num(cr, "ffu_count")
    if count is None:
        count = _num(heat, "ffu_count")
    if main and count is None:
        count = _num(r.get("counts", {}), "FFU")
    unit_flow = _num(cr, "ffu_unit_cmh")
    if unit_flow is None and main:
        unit_flow = _num(inputs, "ffu_cmh")
    coverage = _num(cr, "coverage_ratio", "ffu_coverage_pct")
    limit = _num(cr, "coverage_limit_pct")
    size = cr.get("ffu_size", inputs.get("ffu_size"))
    if not is_mau:
        rows.append(_row("FFU 循環風機濾網組", "此系統未採用 FFU", "不適用", "不適用", "neutral"))
    else:
        ffu_demand = "總風量 " + _fmt(ffu_flow, "CMH")
        selection = "單台 " + (_fmt(unit_flow, "CMH") if unit_flow is not None else NOT_CALCULATED)
        selection += "；" + (str(size) if size else "尺寸尚未計算")
        selection += "；需求 " + _fmt(count, "台", 0) + "；覆蓋率 " + _fmt(coverage, "%")
        if main and count is not None and _num(inputs, "ffu_w") is not None:
            _fw = _num(inputs, "ffu_w")
            selection += "；單台發熱 " + _fmt(_fw, "W", 0) + "（FFU 顯熱 " + _fmt(count * _fw / 1000.0, "kW") + "）"
        for key in ("ffu_topology", "ffu_airflow_basis"):
            if key == "ffu_airflow_basis" and cr.get("ffu_topology", inputs.get("ffu_topology")) == "獨立FFU循環（MAU直接入室）":
                continue
            basis = cr.get(key, inputs.get(key))
            if basis:
                selection += "；" + str(basis)
        exceeded = bool(cr.get("coverage_exceeded")) or (
            coverage is not None and limit is not None and coverage > limit)
        if limit is not None:
            selection += "（本案配置上限 " + _fmt(limit, "%") + "）"
        topology = cr.get("ffu_topology", inputs.get("ffu_topology"))
        oa_value = _num(cr, "oa_cmh", "oa_room_cmh")
        feasible = cr.get("airflow_feasible") is not False and not (
            topology == "MAU入靜壓箱經FFU送風" and ffu_flow is not None
            and oa_value is not None and ffu_flow < oa_value - 1e-6)
        rows.append(_row("FFU 循環風機濾網組", ffu_demand, selection,
                         "氣流配置不可行" if not feasible else "結構空間超限" if exceeded else "配置初估" if count is not None else "待資料",
                         "danger" if exceeded or not feasible else "success" if count is not None else "warning"))

    oa = _num(cr, "oa_cmh", "oa_room_cmh", "required_oa_cmh")
    if oa is None:
        oa = _num(heat, "oa_cmh")
    mau_kw = _num(heat, "q_mau_kw")
    if mau_kw is None and main:
        mau_kw = _coil_kw(r["summer"])
    mau_demand = "設計外氣 " + _fmt(oa, "CMH") + "；冷卻除濕 " + _fmt(mau_kw, "kW")
    if mau_kw is not None:
        mau_demand += " / " + _fmt(mau_kw / US_RT_KW, "US RT")
    if not is_mau:
        rows.append(_row("MAU 外氣空調箱", "此系統於空調入口混合外氣；未配置獨立 MAU",
                         "不適用", "不適用", "neutral"))
    else:
        mau_sel = "依風量、送風露點及盤管工況選型" if oa is not None else NOT_CALCULATED
        if main and mau_kw is not None and r.get("room", {}).get("v_da") and r.get("oa", {}).get("v_da"):
            _sf_val = _num(r, "sf") or 1.0
            _inlet_cmh = r["oa_mass"] * r["oa"]["v_da"] * 3600
            mau_sel = (
                "含餘裕目標 " + _fmt(mau_kw * _sf_val, "kW") + " / " + _fmt(mau_kw * _sf_val / US_RT_KW, "US RT")
                + "；外氣入口實際風量 " + _fmt(_inlet_cmh, "CMH")
                + "（換算風量不改變同一質量流率的冷量）；" + mau_sel
            )
        rows.append(_row("MAU 外氣空調箱", mau_demand, mau_sel,
                         "需求初估" if oa is not None else "待資料"))

    dcc_flow = _num(cr, "dcc_design_cmh", "dcc_cmh", "recirculation_cmh", "circulation_cmh")
    dcc_kw = (_num(heat, "dcc_design_kw", "dcc_sensible_kw", "dcc_kw") if main else
              _num(heat, "q_dcc_kw", "dcc_sensible_kw", "dcc_design_kw", "dcc_kw"))
    if dcc_kw is None:
        dcc_kw = _num(heat, "q_room_sensible_kw")
    if not is_mau:
        rows.append(_row("DCC 室內乾冷盤管", "此系統未採用 DCC", "不適用", "不適用", "neutral"))
    else:
        dcc_selection = "盤管表面須高於室內露點；依水溫及風量選型" if dcc_kw is not None else NOT_CALCULATED
        dcc_count = _num(r.get("counts", {}), "DCC") if main else None
        if dcc_count is not None:
            _unit_rt = _num(inputs, "en_dcc_rt")
            _avg_cmh = (dcc_flow / dcc_count) if (dcc_flow and dcc_flow > 0 and dcc_count > 0) else None
            _dcc_extra = ""
            if _unit_rt is not None:
                _dcc_extra += "（單台 " + _fmt(_unit_rt, "RT")
                if _avg_cmh is not None:
                    _dcc_extra += "，平均每台風量 " + _fmt(_avg_cmh, "CMH", 0)
                _dcc_extra += "）"
            dcc_selection = "DCC 需求 " + _fmt(dcc_count, "台", 0) + _dcc_extra + "；" + dcc_selection
        rows.append(_row("DCC 室內乾冷盤管", "循環回風 " + _fmt(dcc_flow, "CMH") + "；顯熱 " + _fmt(dcc_kw, "kW"),
                         dcc_selection,
                         "氣流配置不可行" if dcc_flow is not None and dcc_flow < 0 else "需求初估" if dcc_kw is not None else "待資料",
                         "danger" if dcc_flow is not None and dcc_flow < 0 else "warning"))

    total_kw = _num(heat, "q_total_kw")
    if total_kw is None and main and mau_kw is not None:
        # Actual coil water loads are already the system cooling demand.
        actual_dcc = _num(r, "dcc_kw")
        total_kw = mau_kw + actual_dcc if actual_dcc is not None else None
    total_demand = _fmt(total_kw, "kW")
    if main:
        basis_label = str(r.get("q_total_basis", "夏冬同時峰值冷量（未加餘裕）"))
        total_demand = basis_label + " " + total_demand
    if total_kw is not None:
        total_demand += " / " + _fmt(total_kw / US_RT_KW, "US RT")
    sf = _num(r, "sf") if main else None
    design_kw = (
        total_kw * sf
        if total_kw is not None and sf is not None
        else None
    )
    selection = ("同時峰值容量目標 " + _fmt(design_kw, "kW") + " / " + _fmt(design_kw / US_RT_KW, "US RT")
                 + "（含本案容量餘裕，原廠額定待確認）") if design_kw is not None else (
                     "依設計冷量及實際供回水工況選型" if total_kw is not None else NOT_CALCULATED)
    rows.append(_row("中央冰水主機 Chiller", total_demand, selection,
                     "冷量初估" if total_kw is not None else "待資料"))

    water_rows = []
    pump_rows = []
    if main:
        # Distinct temperature loops cannot be described as a single header.
        for key in ("MCHW", "CHW", "DCCW"):
            pipe = r.get("water", {}).get(key, {})
            loss = r.get("pressure", {}).get(key, {})
            if _num(pipe, "lpm") is None:
                continue
            size = str(pipe.get("size", NOT_CALCULATED))
            size += " × " + _fmt(pipe.get("runs"), "並聯", 0) if pipe.get("runs", 1) > 1 else ""
            rate = _num(loss, "friction_pa_m")
            if rate is None:
                length = _num(r.get("project", {}).get("pressure_drop", {}).get(key, {}), "length_m")
                friction = _num(loss, "friction_pa")
                rate = friction / length if friction is not None and length and length > 0 else None
            water_rows.append((key + " " + _fmt(pipe.get("lpm"), "LPM"), key + " " + size
                               + "；" + _fmt(pipe.get("velocity_mps"), "m/s") + "；" + _fmt(rate, "Pa/m")
                               + "；路徑壓差 " + _fmt(loss.get("total_pa"), "Pa")))
            pump_rows.append(key + " " + _fmt(pipe.get("lpm"), "LPM") + "；揚程 " + _fmt(loss.get("head_m"), "m")
                             + "；軸功率 " + _fmt(loss.get("shaft_kw"), "kW"))
        # MCHW / CHW / DCCW flows are sized on the load with the capacity margin (engine: loads = coil kW x sf), unlike the
        # chiller line above which states the peak without margin. Say so, or the two "demand" figures look comparable.
        margin_pct = (sf - 1) * 100 if sf is not None else None
        flow_note = ("（含 " + format(margin_pct, "g") + "% 容量餘裕）" if margin_pct and margin_pct > 1e-9 else "（未加容量餘裕）") if water_rows else ""
        rows.append(_row("冰水主管路規格", "｜".join(row[0] for row in water_rows) + flow_note if water_rows else NOT_CALCULATED,
                         "｜".join(row[1] for row in water_rows) or NOT_CALCULATED,
                         "各溫度迴路分列" if water_rows else "待資料"))
        rows.append(_row("冰水循環泵浦 CHWP", "｜".join(pump_rows) + flow_note if pump_rows else NOT_CALCULATED,
                         "馬達銘牌尚未選型；各迴路須分別選泵", "待選型"))
    else:
        water = pipeline.get("water", r if r.get("tool") == "water" else {})
        water = water if isinstance(water, dict) else {}
        pipe, thermal, loss = (water.get(key, {}) for key in ("pipe", "thermal", "pressure"))
        water_flow = _num(thermal, "lpm")
        if water_flow is None:
            water_flow = _num(pipe, "lpm")
        rows.append(_row("冰水主管路規格", "設計流量 " + _fmt(water_flow, "LPM"),
                         (str(pipe.get("size", NOT_CALCULATED)) + "；" + _fmt(pipe.get("velocity_mps"), "m/s")
                          + "；" + _fmt(loss.get("friction_pa_m"), "Pa/m")) if water else NOT_CALCULATED,
                         "管徑初估" if water else "待資料"))
        pump = pipeline.get("pumps", r if r.get("tool") == "pumps" else {})
        pump = pump if isinstance(pump, dict) else {}
        motor = _num(pump, "recommended_motor_kw")
        demand = "設計流量 " + _fmt(pump.get("flow_lpm"), "LPM") + "；揚程 " + _fmt(pump.get("head_m"), "m")
        demand += "；軸功率 " + _fmt(pump.get("shaft_power_kw"), "kW")
        selection = _fmt(motor, "kW") + " 馬達銘牌（軸輸出額定、含 15% 裕度）" if motor is not None else (
            "需求超出內建馬達級距，須另選規格" if pump else NOT_CALCULATED)
        rows.append(_row("冰水循環泵浦 CHWP", demand, selection,
                         "選型初估" if motor is not None else "超出級距" if pump else "待資料",
                         "warning" if motor is not None or not pump else "danger"))

    if main:
        electric = r.get("electric", {})
        demands, selections = [], []
        for key in ("UP", "NP"):
            panel = electric.get(key, {})
            candidate = panel.get("selected", {})
            demands.append(key + " " + _fmt(panel.get("kw"), "kW") + "；" + _fmt(panel.get("current_a"), "A"))
            selections.append(key + " " + _fmt(candidate.get("nfb_candidate_a"), "AT", 0)
                              + "；" + _fmt(candidate.get("runs"), "組", 0) + " × "
                              + _fmt(candidate.get("size_mm2"), "mm²/相")
                              + "；" + candidate.get("pe_spec", "接地待核"))
        rows.append(_row("主配電斷路器 MCCB", "｜".join(demands), "｜".join(selections)
                         + "；主進線未計算，不將分盤 AT 相加", "分盤候選"))
    else:
        electric = pipeline.get("electrical", r if r.get("tool") == "electrical" else {})
        electric = electric if isinstance(electric, dict) else {}
        candidate = electric.get("selected") or {}
        at = _num(candidate, "nfb_a")
        power = _num(electric, "power_kw", "electrical_input_kw")
        demand = "明列設備有效輸入功率 " + _fmt(power, "kW") + "；運轉電流 " + _fmt(electric.get("current_a"), "A")
        demand += "；配線設計電流 " + _fmt(electric.get("design_a"), "A")
        selection = (_fmt(at, "AT", 0) + "；同迴路導線 " + _fmt(candidate.get("size_mm2"), "mm²/相")
                     + " × " + _fmt(candidate.get("runs"), "組", 0)
                     + "；" + candidate.get("pe_spec", "接地待核")
                     + "；主進線未計算，啟動、短路及上下游保護協調另核") if at is not None else (
            "無用電需求" if power == 0 else "需求超出內建斷路器級距，須另選規格" if electric else NOT_CALCULATED)
        rows.append(_row("配電斷路器 NFB（本次迴路）" if electric else "主配電斷路器 MCCB", demand, selection,
                         "同迴路配線候選" if at is not None else "無需求" if power == 0 else "超出級距" if electric else "待資料",
                         "neutral" if power == 0 else "warning" if at is not None or not electric else "danger"))
    return rows


def executive_summary_text(result):
    lines = ["╔" + "═" * 66 + "╗", SUMMARY_TITLE,
             "【計算需求值】與【建議選型規格】分列；缺值保留尚未計算。"]
    for row in executive_summary(result):
        lines.extend(["", row["equipment"] + "｜" + row["status"],
                      "  【計算需求值】" + row["demand"],
                      "  【建議選型規格】" + row["selection"]])
    lines.append("╚" + "═" * 66 + "╝")
    return "\n".join(lines)


def executive_summary_html(result):
    """Escaped HTML fragment; the document wrapper performs localization."""
    rows = executive_summary(result)
    def kpi(row, index):
        source = row["selection"] if index == 0 else row["demand"]
        pattern = r"[\d,]+(?:\.\d+)?\s*台" if index == 0 else r"[\d,]+(?:\.\d+)?\s*(?:CMH|kW|LPM|A)(?![A-Za-z])"
        matched = re.search(pattern, source)
        if index == 3:
            matched = re.search(r"[\d,]+(?:\.\d+)?\s*US RT", source)
        if index == 2:
            matched = re.search(r"[\d,]+(?:\.\d+)?\s*kW", source)
        if index == 4 and "project" in result:
            return row["demand"]
        if index == 5:
            matched = re.search(r"[\d,]+(?:\.\d+)?\s*kW", row["selection"])
        if index == 6:
            if "project" in result:
                return " / ".join(re.findall(r"(?:UP|NP) [\d,]+ AT", row["selection"])) or row["status"]
            matched = re.search(r"[\d,]+(?:\.\d+)?\s*AT", row["selection"])
        return matched.group() if matched else ("不適用" if row["status"] == "不適用" else row["status"])

    cards = "".join(
        '<article class="kpi-card"><p class="kpi-label">' + escape(row["equipment"])
        + '</p><p class="kpi-value">' + escape(kpi(row, index))
        + '</p><span class="badge ' + row["tone"] + '">' + escape(row["status"])
        + '</span></article>' for index, row in enumerate(rows))
    table = "".join(
        "<tr><th scope=\"row\">" + escape(row["equipment"]) + "</th><td>" + escape(row["demand"])
        + "</td><td>" + escape(row["selection"]) + '</td><td><span class="badge ' + row["tone"]
        + '">' + escape(row["status"]) + "</span></td></tr>" for row in rows)
    return ('<section class="executive-summary" aria-labelledby="executive-title"><h2 id="executive-title">'
            + SUMMARY_TITLE + '</h2><div class="kpi-grid">' + cards
            + '</div><div class="table-scroll"><table class="selection-table"><thead><tr>'
            + '<th scope="col">設備／系統</th><th scope="col">計算需求值</th><th scope="col">建議選型規格</th>'
            + '<th scope="col">狀態</th></tr></thead><tbody>' + table + '</tbody></table></div></section>')


def nm_summary_rows(result):
    """Actual single-unit boundaries, without implying a whole-facility design."""
    i = result.get("inputs", {})
    summer = result.get("summer", {})
    winter = result.get("winter", {})
    cooling = _coil_kw(summer)
    target = summer.get("sa", {})
    flow = i.get("summer_flow") if i.get("target_mode") == "主案分季需求" else i.get("flow")
    humid = winter.get("steam", {}).get("kg_h") if "蒸汽" in i.get("humidifier", "") else winter.get("evap_kg_h")
    return [
        ("MAU 設計風量", _fmt(flow, "CMH"), str(i.get("flow_basis", ""))),
        ("夏季盤管水側冷量", _fmt(cooling, "kW"), _fmt(cooling / US_RT_KW, "US RT") if cooling is not None else NOT_CALCULATED),
        ("夏季送風狀態", _fmt(target.get("t"), "°C"), _fmt(target.get("rh"), "%RH")),
        ("風機需求輸入電力", _fmt(result.get("fan_required_kw"), "kW"), "依已填壓差與效率估算"),
        ("啟用設備名目電力", _fmt(result.get("active_installed_electric_kw"), "kW"), "未含未提供的循環泵與附屬設備"),
        ("冬季加濕需求", _fmt(humid, "kg/h"), "依加濕型式分列"),
    ]


def nm_summary_html(result):
    cards = "".join('<article class="kpi-card"><p class="kpi-label">' + escape(title)
                    + '</p><p class="kpi-value">' + escape(value) + '</p><span class="badge warning">'
                    + escape(note) + '</span></article>' for title, value, note in nm_summary_rows(result))
    return '<section><h2>MAU 單機核心設計量</h2><div class="kpi-grid">' + cards + '</div></section>'


def _validate_full_result(r):
    # Independent-domain results are useful in the UI, but cannot be exported
    # as a complete project report. Zero-demand rows still have result records.
    required = {"gas": ("1", "2", "3", "4"), "electric": ("UP", "NP")}
    report_keys = set("project effective_inputs quality sf summer winter zones light "
                      "minimum_oa_cmh oa_room_cmh extra_relief_cmh qs ql moisture latent "
                      "supply_room_cmh circulation_cmh room rt_kw dcc_kw counts water "
                      "pressure ducts gas electric upw warnings dcc_design_kw "
                      "coverage_exceeded coverage_limit_pct coverage_ratio dcc_cmh "
                      "dcc_sensible_kw ffu_airflow_basis ffu_area_each ffu_count ffu_size "
                      "ffu_total_cmh ffu_unit_cmh leakage_cmh q_mau_kw "
                      "q_room_sensible_kw q_total_kw q_total_rt q_total_basis q_loop_envelope_kw q_loop_envelope_rt required_oa_cmh "
                      "dcc_return_cmh dcc_design_cmh dcc_design_season "
                      "terminal_cooling_kw terminal_cooling_season".split())
    if isinstance(r, dict) and isinstance(r.get("effective_inputs"), dict) and "ffu_topology" in r["effective_inputs"]:
        report_keys.add("ffu_topology")
    mappings = "project effective_inputs quality summer winter zones light latent room counts water pressure ducts gas electric upw".split()
    if not isinstance(r, dict) or not report_keys <= r.keys() or any(
        not isinstance(r.get(key), dict) or not r[key] for key in mappings
    ) or not isinstance(r.get("warnings"), list) or any(
        not isinstance(r.get(domain), dict)
        or any(not isinstance(r[domain].get(key), dict) or not r[domain][key]
               for key in keys)
        for domain, keys in required.items()
    ):
        raise InputError(
            "完整報告需要空調、氣體與電氣的完整計算結果；目前結果不完整，請修正未通過的項目並重新計算。",
            code="incomplete_result",
        )
    from .schema import DEFAULTS

    if (not isinstance(r["project"].get("inputs"), dict)
            or not set(DEFAULTS) <= r["project"]["inputs"].keys()
            or not {"status", "items"} <= r["quality"].keys()
            or not isinstance(r["quality"]["items"], list)
            or any(not isinstance(r[season].get(coil), dict) or not r[season][coil]
                   for season in ("summer", "winter") for coil in ("c1", "c2"))):
        raise InputError(
            "完整報告需要空調、氣體與電氣的完整計算結果；目前結果不完整，請修正未通過的項目並重新計算。",
            code="incomplete_result",
        )


@localized_report
def report(r):
    _validate_full_result(r)
    i = dict(r["project"]["inputs"])
    from .schema import DEFAULTS

    i["project_name"] = verbatim(i["project_name"], DEFAULTS["project_name"])
    i.update({k: r["effective_inputs"][k] for k in r.get("inactive_fields", {})})
    lines = []
    a = lines.append
    sf = r["sf"]
    s = r["summer"]
    w = r["winter"]
    a(i["project_name"] + "｜設計條件與計算摘要")
    a("系統：" + i["sys_type"] + "｜V" + REPORT_VERSION + "｜需求初估")
    a(
        "整體狀態："
        + r["quality"]["status"]
        + "；設備台數為需求候選，未達條件不可直接選用。"
    )
    for q in r["quality"]["items"]:
        if q["status"] != "通過":
            a("[" + q["status"] + "] " + q["name"] + "：" + q["detail"])
    for rec in r.get("source_receipts", []):
        if rec["status"] != "已由手動或其他來源取代":
            a(
                "來源："
                + verbatim(rec["source_name"])
                + "；帶入 "
                + rec["captured_at"]
                + "；"
                + rec["status"]
            )
    a("\n" + executive_summary_text(r))
    a("\n一、設計條件")
    demand = r.get("demand_summary")
    if demand and demand["sources"]:
        a("已納入需求來源：" + "；".join(verbatim(x["name"]) for x in demand["sources"]))
        a("水量彙整：同迴路夏／冬各自求和，設計=max(Σ夏季LPM, Σ冬季LPM)；不同供回水／介質／群組分列。")
        for group in demand["water"]:
            a(f"{group['loop']} {verbatim(group['circuit'])} {group['supply']:g}/{group['return']:g}°C：夏 {group['summer_lpm']:.2f}，冬 {group['winter_lpm']:.2f}，設計 {group['design_lpm']:.2f} LPM；" + ("主案採用" if group["adopted"] else "獨立迴路，未映射主案水力列"))
    a(
        f"大氣壓 {i['atm_kpa']} kPa；夏季 {i['oa_t']}°C / {i['oa_rh']}%RH；冬季 {i['ow_t']}°C / {i['ow_rh']}%RH；室內 {i['ra_t']}°C / {i['ra_rh']}%RH（精確目標）。"
    )
    for z, d in r["zones"].items():
        mode_detail = (
            f"截面風速 {i['face_' + z]} m/s（覆蓋率 {i['coverage_' + z]}%）"
            if i["mode_" + z] != "ACH"
            else f"ACH {i['en_ach_' + z]}"
        )
        a(
            f"{z} 區 {d['area']:.1f} m²、{d['volume']:.1f} m³；{mode_detail} 需求 {d['cmh']:.1f} CMH；正壓 {i['en_p_' + z]} Pa；潔淨紀錄 {i['c_' + z.lower()]}。"
        )
    a(
        f"正壓洩漏 {r['leakage_cmh']:.2f} CMH（{i['leak_method']}）；補償外氣下限 {r['minimum_oa_cmh']:.2f} CMH；採用 {r['oa_room_cmh']:.2f} CMH；额外洩壓需求 {r['extra_relief_cmh']:.2f} CMH（均以室內狀態基準）。"
    )
    a(
        f"照明 {r['light']['qty']} 盞／{r['light']['kw']:.3f} kW；室內顯熱 {r['qs']:.3f} kW；潛熱參考 {r['ql']:.3f} kW；產濕 {r['moisture'] * 3600:.3f} kg/h。"
    )
    parts = r.get("parts", {})
    if parts:
        a(
            f"顯熱組成：設備淨熱 {parts.get('equipment_net', parts.get('設備淨熱', 0)):.3f}（PCW帶走 {parts.get('pcw_removed', parts.get('PCW帶走', 0)):.3f}、排氣帶走 {parts.get('exhaust_removed', parts.get('排氣帶走', 0)):.3f}）、人員顯熱 {parts.get('people', parts.get('人員顯熱', 0)):.3f}、照明 {parts.get('lighting', parts.get('照明', 0)):.3f}、外牆 {parts.get('wall', parts.get('外牆', 0)):.3f}、樓板 {parts.get('floor', parts.get('樓板', 0)):.3f}、烤箱 {parts.get('oven', parts.get('烤箱', 0)):.3f}、日射 {parts.get('solar', parts.get('日射', 0)):.3f}、風機與FFU {parts.get('fan', parts.get('風機與FFU', 0)):.3f} kW。"
        )
    if float(i["en_wall"]) > 0 or float(i["en_floor"]) > 0:
        a(
            f"圍護條件：外牆 {float(i['en_wall']):g} m²×U {float(i['wall_u']):g}、樓板 {float(i['en_floor']):g} m²×U {float(i['floor_u']):g}（U 值單位 {i['u_unit']}）。"
        )
    a(
        f"產濕來源：人員 {r['latent']['people_kg_h']:.3f}＋額外製程 {r['latent']['process_kg_h']:.3f} kg/h；製程方式：{i['latent_mode']}。外氣水氣由盤管另算，不重複加進室內。"
    )
    a("\n二、空調分工與狀態")
    single_coil = i["pre_mode"] == "單盤管（一般空調箱）"
    c1_desc = (
        f"一段旁通（備用ΔT {i['chw1_dt']} K）"
        if i["pre_mode"] == "停用／旁通"
        else f"一段供水 {i['chw1_in']}°C／ΔT {i['chw1_dt']} K（{i['pre_mode']}，目標 {i['pre_t']}°C）"
    )
    dcc_desc = (
        f"DCCW {i['dccw_in']}°C／ΔT {i['dt_dccw']} K"
        if i["sys_type"].startswith("MAU")
        else f"無 DCC 迴路（備用ΔT {i['dt_dccw']} K）"
    )
    a(
        (f"單盤管：冰水 {i['chw2_in']}°C／ΔT {i['dt_chw']} K；" if single_coil else f"{c1_desc}；二段 {i['chw2_in']}°C／ΔT {i['dt_chw']} K；") + f"{dcc_desc}；容量餘裕 {i['sf']}%（冷凍噸基準：{i['rt_type']}）。"
    )
    a(
        f"處理風量 {r['supply_room_cmh']:.2f} CMH（室內基準）；{('FFU 循環另計 ' + format(r['circulation_cmh'], '.2f') + ' CMH' if i['sys_type'].startswith('MAU') else '外氣於空調入口混合')}。"
    )
    a("點位             乾球°C    RH%       w(g/kg乾空氣)       h(kJ/kg乾空氣)")
    for title, state in [
        ("入口", s["enter"]),
        *(([] if single_coil else [("一段出口", s["c1"]["outlet"])])),
        ("冷卻盤管出口" if single_coil else "二段出口", s["c2"]["outlet"]),
        ("最終送風", s["supply"]),
        ("室內", r["room"]),
    ]:
        a(
            f"{title:<10} {state['t']:9.3f} {state['rh']:8.3f} {state['w'] * 1000:16.6f} {state['h']:18.6f}"
        )
    for c in ([s["c2"]] if single_coil else [s["c1"], s["c2"]]):
        adp_bf = (
            f"（所需 ADP {c['adp_req_c']:.2f}°C／BF {c['bf_req']:.3f}）"
            if c.get("adp_req_c") is not None and c.get("bf_req") is not None
            else ""
        )
        a(
            f"{c['name']}{adp_bf}：空氣側 {c['air_kw']:.3f} kW；水側 {c['water_kw']:.3f} kW；含餘裕 {c['water_kw'] * sf / r['rt_kw']:.3f} RT；凝結水 {c['condensate_kg_s'] * 3600:.3f} kg/h。"
        )
    a(
        f"DCC 顯熱 {r['dcc_kw']:.3f} kW；夏季再熱 {s['reheat_kw']:.3f} kW；加濕 {s['humid_kg_h']:.3f} kg/h（空氣側 {s['humid_air_kw']:.3f} kW）。"
    )
    a(
        "設備初估："
        + (
            "；".join((f"{k} {v} 台" for k, v in r["counts"].items() if v))
            or "無設備需求"
        )
    )
    if i["sys_type"].startswith(("FCU", "RCU")) and r.get("terminal_cooling_kw") is not None:
        a(
            f"末端冷卻選型基準：夏季 {_coil_kw(s):.3f} kW／冬季 {_coil_kw(w):.3f} kW；"
            f"夏冬較大值 × {sf:g}＝{r['terminal_cooling_kw'] * sf:.3f} kW。FCU 同時核對風量。"
        )
        design_kw = r["terminal_cooling_kw"] * sf
        if i["sys_type"].startswith("RCU"):
            unit_rt = float(i["en_rcu_rt"])
            unit_kw = unit_rt * r["rt_kw"]
            a(f"RCU 單台額定：{unit_rt:g} RT／{unit_kw:.6f} kW；冷量需求台數 {design_kw / unit_kw:.6f}，向上取整 {r['counts']['RCU']} 台。")
        else:
            unit_rt, unit_flow = float(i["fcu_rt"]), float(i["en_fcu_cmh"])
            unit_kw = unit_rt * r["rt_kw"]
            cooling_count, airflow_count = design_kw / unit_kw, r["supply_room_cmh"] / unit_flow
            governing = "風量" if airflow_count > cooling_count else "冷量"
            a(f"FCU 單台額定：{unit_rt:g} RT／{unit_kw:.6f} kW；單台風量 {unit_flow:g} CMH。")
            a(f"FCU 台數比較：冷量 {cooling_count:.6f}／風量 {airflow_count:.6f}；主導條件：{governing}；較大值向上取整 {r['counts']['FCU']} 台。")
    elif i["sys_type"].startswith("MAU"):
        unit_rt = float(i["en_dcc_rt"])
        unit_kw = unit_rt * r["rt_kw"]
        a(f"DCC 單台額定：{unit_rt:g} RT／{unit_kw:.6f} kW；夏冬較大顯熱 × {sf:g}＝{r['dcc_design_kw'] * sf:.6f} kW；需求台數 {r['dcc_design_kw'] * sf / unit_kw:.6f}，向上取整 {r['counts']['DCC']} 台。")
    if r.get("winter_room"):
        wr = r["winter_room"]
        term_note = (
            f"、室內加熱需求 {wr['terminal_heat_kw']:.3f}"
            + (" kW（已計入 HW）" if wr.get("terminal_heat_source") == "HW" else " kW（未配置熱源，待指定；未計入 HW 或 NP）")
            if wr.get("terminal_heat_kw", 0.0) > 1e-6
            else ""
        )
        a(
            f"冬季室內熱濕平衡：顯熱 {wr['sensible_kw']:.3f} kW；送風 {w['supply']['t']:.3f}°C／{w['supply']['rh']:.3f}%RH；加熱 {w['reheat_kw']:.3f} kW{term_note}、加濕 {w['humid_kg_h']:.3f} kg/h。"
        )
        a(
            f"DCC 夏冬較大需求 {r['dcc_design_kw']:.3f} kW；冬季為明列負荷的穩態估算，非逐時建築模擬。"
        )
    else:
        a(
            f"冬季外氣處理基準：同設計質量流量處理至室內 T/RH，未扣冬季室內得熱；加熱 {w['reheat_kw']:.3f} kW、加濕 {w['humid_kg_h']:.3f} kg/h。"
        )
    a("\n三、管路／流速／壓差")
    for k, d in r["water"].items():
        if d["lpm"]:
            a(
                f"{k}：{d['lpm']:.3f} LPM，ΔT {d['delta_t']:.2f} K，{d['runs']} 支×{d['size']}／ID {d['id_mm']:.1f} mm，{d['velocity_mps']:.3f} m/s；壓差 {r['pressure'][k]['total_pa']:.3f} Pa。"
            )
            if d.get("reference"):
                ref = d["reference"]
                a(f"  採用碳鋼STD參考：外徑 {ref['outside_mm']:g}mm／壁厚 {ref['wall_mm']:g}mm；依實供管材核對。")
            fluid = d["fluid_properties"]
            a(f"  採用物性：ρ {fluid['rho']:g} kg/m³；cp {fluid['cp']:g} kJ/(kg·K)；μ {fluid['mu']:g} Pa·s；來源 {fluid['source']}。")
            a("  " + r["pressure"][k]["static_note"])
    for k, d in r["ducts"].items():
        if d["flow_cmh"]:
            dims = (
                f"{d['w_mm']}×{d['h_mm']} mm"
                if d["shape"] == "方管"
                else f"ID {d['diameter_m'] * 1000:.1f} mm"
            )
            a(
                f"{k}：{d['nominal_cmh']:.2f}→{d['flow_cmh']:.2f} CMH，{d['shape']} {dims}，{d['velocity_mps']:.3f} m/s；壓差 {r['pressure'][k]['total_pa']:.3f} Pa。"
            )
    for k, g in r["gas"].items():
        if g["standard_lpm"]:
            a(
                f"{verbatim(g['custom_name']) if g['type'] == CUSTOM_GAS else gas_label(g['type']) if g['type'] != 'PV' else 'PV'}：{g['standard_lpm']:.2f} SLPM→{g['actual_lpm']:.2f} ALPM（{g['pressure_abs_pa'] / 1000:.3f} kPa abs），{g['size']}／ID {g['selected_id_mm']:.1f} mm；{g['velocity_mps']:.3f} m/s。"
            )
    for j in (1, 2, 3):
        g = r["gas"][str(j)]
        if g["standard_lpm"]:
            a(
                f"特氣 {j} 定寸：管內表壓 {(g['pressure_abs_pa'] / 1000 - float(i['atm_kpa'])) / 100:.3f} bar(g)，絕壓 {g['pressure_abs_pa'] / 1000:.3f} kPa；設計流速上限 {g['velocity_limit_mps']:.3f} m/s。"
            )
    a(f"PV 設計流速上限 {r['gas']['4']['velocity_limit_mps']:.3f} m/s。")
    a(
        f"氣體標準體積：{i['gas_std_t']}°C／{i['gas_std_kpa']} kPa；管內 {i['gas_temp']}°C，Z 比 {i['gas_z_ratio']}；僅流速初估。"
    )
    if float(i["pv_q"]):
        a(
            f"PV 壓力輸入：{i['pv_torr']} {i['pv_pressure_unit']}（絕壓）；等值 {pv_to_torr(i['pv_torr'], i['pv_pressure_unit']):.6f} Torr。"
        )
    if r["upw"]["lpm"]:
        a(
            f"{i['upw_type']}：{i['upw_q']} LPM，{i['upw_v_mode']} {i['upw_v']} m/s ⇒ ID {r['upw']['relation']} {r['upw']['id_mm']:.3f} mm；{i['upw_mat']}。"
        )
        a(
            f"水質規格紀錄：{r['upw']['resistivity']}，TOC {i['upw_toc']}，DO {i['upw_do']}，溫度 {i['upw_temp']}°C。"
        )
    simple = [
        f"{k} {d['allowance_pct']:g}%"
        for k, d in r["pressure"].items()
        if d["flow_m3s"] and d["estimate_mode"] == "簡易估算"
    ]
    if simple:
        a(
            "壓損簡易初估："
            + "、".join(simple)
            + " 管件等效長度餘裕；Δp＝直管摩擦×(1＋餘裕)＋已知設備壓差＋適用靜揚程。"
        )
    a("\n四、配電候選")
    a(
        f"{i['e_volt']}；PF {i['e_pf']}；HP 換算效率 {i['e_eff']}；{i['e_wire']}；端子 {i['e_terminal_c']}°C；單程 {i['e_length_m']} m；排序 {i['e_sort']}。"
    )
    a(f"本工作台降載採下拉區間：環溫 {i['e_temp']}；同管載流導線 {i['e_pipe']}。")
    for k, e in r["electric"].items():
        c = e["selected"]
        a(f"  {k} 採用環溫 {e['ambient_c']:g}°C，溫度係數 {e['dt']:g}，同管係數 {e['dp']:g}。")
        a(
            f"{k}：運轉 {e['current_a']:.3f} A，設計 {e['design_current_a']:.3f} A；NFB 候選 {c['nfb_candidate_a']} AT，{c['runs']} 組×{c['size_mm2']} mm²/相，Iz {c['iz_a']:.3f} A，壓降 {c['voltage_drop_pct']:.3f}%；動力設備接地 {c.get('pe_spec', '待核')}；接地覆核紀錄：{i['e_' + k.lower() + '_ground']}。"
        )
        if i.get("e_" + k.lower() + "_pf_mode") == "本盤獨立 PF":
            a(f"  {k} 採用獨立 PF={e['pf']:.6g}；匯入設計電流下限 {i['e_' + k.lower() + '_design_floor']} A。")
        if e["kind"] == "連續負載":
            a("  連續負載採總運轉電流×1.25；最大馬達草稿不參與計算。")
        elif e["has_motor"]:
            a(
                f"  最大馬達 {e['largest_hp']:g} HP：設計電流採總電流＋最大馬達估算電流×0.25。"
                if e["largest_hp"] > 0 else
                "  最大馬達未知：保守採總運轉電流×1.25。"
            )
    from .grounding import PE_BASIS
    a(PE_BASIS)
    a("\n五、主要公式與簡短說明")
    if r["light"].get("room_index_k") is not None:
        a(
            f"照明 K={r['light']['room_index_k']:.2f}，U(K)={r['light']['u']:.4f}；N=ceil(E×A/(Φ×U×M))=ceil({i['light_lux']}×{r['light']['area_m2']:g}/({i['light_lm']}×{r['light']['u']:.4f}×{i['light_m']}))={r['light']['qty']} 盞。"
        )
    else:
        a(
            f"照明 N=ceil(E×A/(Φ×U×M))=ceil({i['light_lux']}×{r['light']['area_m2']:g}/({i['light_lm']}×{i['light_u']}×{i['light_m']}))={r['light']['qty']} 盞。"
        )
    a(
        f"室內顯熱 Qs=m_da(1.006+1.86ws)(Tr−Ts)+QDCC={r['qs']:.3f} kW；產濕 G=3600×m_da(wr−ws)={r['moisture'] * 3600:.3f} kg/h。"
    )
    a(
        "h=1.006T+w(2501+1.86T)；盤管 Qair=m_da(hin−hout)；Qwater=Qair−m凝結水×cp水×T凝結水。"
    )
    a(
        "水量 LPM=60000Q/(ρcpΔT)；方管 A=WH、Dh=2WH/(W+H)；並聯 v=V̇/(nA)；Δp=f(L/Dh)ρv²/2+管件+設備壓差。"
    )
    a(
        "三相 I=1000P/(√3VLL·PF)；HP 為軸輸出，先乘 0.7456999/η 換輸入 kW；一般候選需滿足設計電流≤AT≤有效載流與小線保護上限。"
    )
    a(
        "盤管為需求／ADP 近似，非廠商性能選定；電纜沿用專案表並加保守條件，端子、短路、接地及馬達啟動仍需覆核。"
    )
    if r["warnings"]:
        a("\n本案待確認：")
        for msg in r["warnings"]:
            a("• " + msg)
    a(
        "資料依據：隨附版本化工程表為初估參考，並非已確認適用的法規載流表。參數來源另存於專案 JSON／HTML 附錄。"
    )
    return "\n".join(lines).replace("额外", "額外").replace("侧", "側") + "\n"


def _nm_report_base(r):
    from .ahu_schema import NM_DEFAULTS

    i = dict(r["inputs"])
    i["name"] = verbatim(i["name"], NM_DEFAULTS["name"])
    lines = [
        i["name"] + "｜MAU 分段需求與額定容量校核｜V" + REPORT_VERSION,
        "此表為需求反算；未達額定檢核時，表列目標狀態不代表已配置設備實際可達。",
        f"風量 {i['flow']} CMH，基準：{i['flow_basis']}；大氣 {i['p']} kPa；送風目標 {i['sa_t']}°C／{i['sa_rh']}%RH。",
        f"H1 熱源：{i['h1_source']}；H2 熱源：{i['h2_source']}；回收熱水情境：{i['recovery']}。",
        f"C1 水溫 {i['c1_in']}/{i['c1_out']}°C；C2 {i['c2_in']}/{i['c2_out']}°C；容量餘裕 {i['sf']}%。",
    ]
    if all(i[s + "_c1_mode"] == "旁通" for s in ("summer", "winter")):
        lines[4] = f"單盤管：冰水 {i['c2_in']}/{i['c2_out']}°C；容量餘裕 {i['sf']}%。"
    if i.get("target_mode") == "主案分季需求":
        lines[2] = (
            "分季送風目標："
            + "；".join(
                f"{label} {i[season+'_flow']} CMH（送風狀態）／{i[season+'_sa_t']}°C／{i[season+'_sa_rh']}%RH"
                for season, label in [("summer", "夏季"), ("winter", "冬季")]
            )
            + "；來源主案 "
            + i["linked_main_hash"]
        )
    a = lines.append
    if "水洗" in i["humidifier"]:
        a(f"濕膜有效度 {i['wash_eff']}（初估／待選型）。")
    for key, title in [("summer", "夏季"), ("winter", "冬季")]:
        s = r[key]
        a(
            f"\n{title}：外氣 {s['oa']['t']:.2f}°C／{s['oa']['rh']:.2f}%RH，乾空氣流率 {s['mass']:.5f} kg/s"
        )
        a(
            "段落                    乾球°C      RH%      露點°C       w g/kg      h kJ/kg"
        )
        for name, st in s["nodes"]:
            a(
                f"{name:<19} {st['t']:9.3f} {st['rh']:9.3f} {dewpoint(st['w'], float(i['p'])):10.3f} {st['w'] * 1000:11.6f} {st['h']:12.6f}"
            )
        for h in [s["h1"], s["h2"]]:
            a(
                f"{h['tag']}：{h['inlet']['t']:.3f}°C／{h['inlet']['rh']:.3f}% → {h['outlet']['t']:.3f}°C／{h['outlet']['rh']:.3f}%；總熱需求 {h['air_kw']:.3f} kW；熱水 {h['hw_kw']:.3f} kW／{h['water_lpm']:.3f} LPM；電力需求 {h['electric_kw']:.3f} kW。"
            )
            if h["electric_enabled"]:
                a(f"  電熱全載備援需求 {h['backup_electric_kw']:.3f} kW；本段額定電熱 {h['installed_kw']:.3f} kW。")
            if h["note"]:
                a(h["tag"] + "：" + h["note"])
        for c, delta in [
            (s["c1"], float(i["c1_out"]) - float(i["c1_in"])),
            (s["c2"], float(i["c2_out"]) - float(i["c2_in"])),
        ]:
            adp_bf = (
                f"（所需 ADP {c['adp_req_c']:.2f}°C／BF {c['bf_req']:.3f}）"
                if c.get("adp_req_c") is not None and c.get("bf_req") is not None
                else ""
            )
            a(
                f"{c['name']}{adp_bf}：水側 {c['water_kw']:.3f} kW／{c['water_kw'] / US_RT_KW:.3f} US RT；需水 {c['water_kw'] * 60000 / (1000 * 4.1868 * delta):.3f} LPM；凝結水 {c['condensate_kg_s'] * 3600:.3f} kg/h。"
            )
        if "水洗" in i["humidifier"]:
            a(
                f"水洗蒸發需求 {s['evap_kg_h']:.3f} kg/h（非循環泵流量）；本季水洗{('運轉' if s['wash_on'] else '旁通')}。"
            )
        a(
            "額定／必要條件檢核："
            + "；".join(
                (
                    k + ("：通過初估" if v else "：未達／需修正")
                    for k, v in s["checks"].items()
                )
            )
        )
    if "水洗" in i["humidifier"]:
        a("\n水洗循環")
        a(
            "循環水量："
            + (
                f"{r['circulation_lpm']:.3f} LPM＝有效淋水面積×原廠單位面積水量"
                if r["circulation_lpm"] is not None
                else "待廠商提供有效淋水面積及淋水密度，不套用蒸發量固定倍數。"
            )
        )
        a(
            "循環泵揚程："
            + (
                f"{r['pump_head_m']:.3f} m＝噴頭水頭＋高差＋管路／濾網損失"
                if r["pump_head_m"] is not None
                else "待噴頭工作壓力、高差及管路／濾網阻力，不自動定為 20 m。"
            )
        )
        a(
            f"最大蒸發補水約 {r['evap_makeup_lph']:.3f} L/h；另加輸入的飛水／排污後 {r['makeup_plus_allowance_lph']:.3f} L/h，未包含未提供的排污或啟動補槽量。"
        )
    a("\n風機與選用電力")
    a(
        f"已填空氣側壓差 {r['air_dp_pa']:.1f} Pa（{('資料已標記完整，仍需風機曲線' if r['pressure_complete'] else '資料未完整，不可據以完成選機')}）；EC 配置 {i['fan_qty']}×{i['fan_unit_kw']} kW。"
    )
    a(
        f"按所填壓差／效率的風機電力需求 {r['fan_required_kw']:.3f} kW；選用電熱＋蒸汽＋EC 名目電力 {r['active_installed_electric_kw']:.3f} kW，未含循環泵與附屬設備。"
    )
    if r["pressure_complete"]:
        a(
            "風機電力初估："
            + (
                "未超出名目電力；仍需風機曲線／運轉點"
                if r["fan_capacity_pass"]
                else "超出名目電力，需重選／核對"
            )
        )
    a(
        "\n主要公式：m_da=V(CMH)/(3600×v_da)；Q=m_daΔh；純加熱 w 不變；水洗以 h_out≈h_in、T_out=T_in−ε(T_in−T_as)；蒸發 G=m_daΔw×3600；盤管水侧扣除凝結水液態焓。"
    )
    a(
        "計算限制：濕膜採循環水近似絕熱模型，忽略液態補水顯熱、泵入水熱及水溫調控；不保證飽和或 AMC 去除率。回收盤管能力須由廠商依同工況提供，端差只作必要條件篩選。"
    )
    a(
        "送風 T/RH 是本單機邊界；若它其實是室內設定，須先扣室內產濕求所需送風含濕量。風量基準、膜有效度、C1 出口、風機熱與額定能力需原始送審資料核對。"
    )
    return "\n".join(lines).replace("热", "熱").replace("侧", "側") + "\n"


@localized_report
def nm_report(r):
    if not isinstance(r, dict) or not all(isinstance(r.get(key), dict) and r[key]
                                       for key in ("inputs", "summer", "winter", "quality")):
        raise InputError("MAU 報告需要完整單機計算結果。", code="incomplete_result")
    s = _nm_report_base(r)
    i = r["inputs"]
    if r.get("link_status"):
        s = "主案連動：" + r["link_status"] + "\n" + s
    extra = [
        f"\n逐段控制與選用熱源（V{VERSION}）",
        f"H1：{i['h1_source']}；H2：{i['h2_source']}；加濕：{i['humidifier']}。保留的名目電熱欄位不代表停用熱源仍在供熱。",
    ]
    for season, title in [("summer", "夏季"), ("winter", "冬季")]:
        sr = r[season]
        extra.append(title + "：" + sr["control_basis"])
        for tag in ["h1", "c1", "c2", "h2"]:
            k = season + "_" + tag
            mode = i[k + "_mode"]
            extra.append(
                tag.upper()
                + " "
                + mode
                + (f" {i[k + '_t']}°C" if mode.startswith("指定") else "")
                + (f"／{i[k + '_rh']}%RH" if mode == "指定出口 T/RH" else "")
            )
        for tag in ["h1", "h2"]:
            effective = sr[tag].get("effective_water")
            if effective:
                extra.append(
                    f"{tag.upper()} 啟用熱水條件 {effective['hw_in']:g}/{effective['hw_out']:g}°C，端差 {effective['hw_approach']:g} K；本季採計熱量 {sr[tag]['hw_kw']:.3f} kW。"
                )
            if sr[tag]["electric_enabled"]:
                extra.append(f"{tag.upper()} 採用電熱效率 {sr[tag]['effective_electric_eta']:g}。")
            if sr[tag].get("unserved_kw", 0) > 1e-06:
                extra.append(
                    f"{tag.upper()} 尚無已選熱源供應的熱需求：{sr[tag]['unserved_kw']:.3f} kW；圖表該點為未供應的需求點。"
                )
        if "蒸汽" in i["humidifier"]:
            st = sr["steam"]
            extra.append(
                f"蒸汽需求 {st['kg_h']:.3f} kg/h；入空氣熱 {st['air_kw']:.3f} kW；發生器電力 {st['electric_kw']:.3f} kW。"
            )
    extra.append("名目電力未自動加進整廠 NP；需預覽帶入，避免重複。")
    extra.append(
        "蒸汽與水洗分開：Δh_air=ṁsteam×hsteam/ṁda；Psteam=ṁsteam(hsteam−cp水×T補水)/η。電極式需導電水，給水及原廠電導率範圍未確認時不判定合格。"
    )
    header = (
        "整體狀態："
        + r["quality"]["status"]
        + "（通過僅指已知條件的初估，非原廠性能認證）\n"
    )
    for q in r["quality"]["items"]:
        if q["status"] != "通過":
            header += "[" + q["status"] + "] " + q["name"] + "：" + q["detail"] + "\n"
    summary = "MAU 單機核心設計量\n" + "\n".join(
        title + "：" + value + "｜" + note for title, value, note in nm_summary_rows(r))
    return header + summary + "\n\n" + s + "\n".join(extra).replace("需求点", "需求點") + "\n"
