"""Explicit, bounded FEED capacity screening. Not a network or protection solver.

Coincident cases are summed before taking a peak. Capacity is compared only at
identical service boundaries and conditions. Unknown values never become zero.
"""
import copy
import math
from collections import defaultdict

from .errors import ValidationError
from .i18n import localized_report, verbatim
from .json_io import read_json_file
from .utils import project_hash

UNITS = {"ELECTRIC": "kW", "CHW": "LPM", "PCW": "LPM", "EXHAUST": "CMH"}
CONDITIONS = {
    "ELECTRIC": ("voltage_v", "phases", "frequency_hz"),
    "CHW": ("fluid", "supply_c", "return_c", "rho_kg_m3", "cp_kj_kgk"),
    "PCW": ("fluid", "supply_c", "return_c", "rho_kg_m3", "cp_kj_kgk"),
    "EXHAUST": ("exhaust_type", "temperature_c", "absolute_kpa", "required_static_pa"),
}
LIMITATION = ("僅為同邊界、同工況的容量初篩，不是完整 FEED 或工程核准；"
              "未驗證電力 kVA／啟動／短路／保護、管網揚程、風機曲線、共因失效及切換能力。"
              "N−1 只扣除最大單台降額容量，假設其餘設備可同時供應；此假設須由設計者確認。")


def new_plan(name="容量與擴建規劃"):
    return dict(kind="facility_capacity_plan", version=2, name=name,
                cases=["summer", "winter"], scope="", scope_confirmed=False,
                additional_margin_pct=0.0, margin_reason="", synthetic=False,
                binding=None, demands=[], capacities=[], alternatives=[])


def new_row(kind, ident, system="ELECTRIC", cases=("summer", "winter")):
    if kind not in ("demand", "capacity") or system not in UNITS:
        raise ValidationError("不支援的容量列種類／系統")
    row = dict(id=ident, asset_id=ident, name=ident, system=system, boundary="",
               conditions={key: None for key in CONDITIONS[system]}, quantity=1,
               values={case: None for case in cases}, source=dict(reference="", revision="", fingerprint=""),
               notes=[], pending=[])
    if kind == "demand":
        row.update(phase="current", coincidence=1.0, included_margin_pct=0.0, demand_complete=False)
    else:
        row.update(derating=None)
    return row


def _text(value, label, blank=False, limit=1000):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValidationError(label + " 文字不合法")
    if not blank and not value.strip():
        raise ValidationError(label + " 不可空白")


def _number(value, label, lo=0, hi=1e9, unknown=False):
    if value is None and unknown:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi or not math.isfinite(value):
        raise ValidationError(label + " 數值不合法；未知請填 null，不可填零代替")


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != set(new_plan()) or plan.get("kind") != "facility_capacity_plan" or type(plan.get("version")) is not int or plan["version"] not in (1, 2):
        raise ValidationError("不支援的容量計畫格式")
    d = copy.deepcopy(plan)
    if d["version"] == 1:
        d["version"] = 2
        # The old schema never recorded explicit complete-demand confirmation.
        # Preserve numeric source values, but do not infer completeness from text.
        if isinstance(d["demands"], list):
            for row in d["demands"]:
                if isinstance(row, dict) and set(row) == set(new_row("demand", "row")) - {"demand_complete"}:
                    row["demand_complete"] = False
                    if isinstance(row["pending"], list) and len(row["pending"]) < 100:
                        row["pending"].append("舊版計畫未記錄需求完整性；已保留數值為已知小計，請另行核對完整需求。")
    _text(d["name"], "計畫名稱")
    _text(d["scope"], "服務範圍", blank=True)
    _text(d["margin_reason"], "額外裕度依據", blank=True)
    if type(d["scope_confirmed"]) is not bool or type(d["synthetic"]) is not bool:
        raise ValidationError("範圍確認／合成案例標記必須為布林值")
    _number(d["additional_margin_pct"], "額外裕度", hi=100)
    d["additional_margin_pct"] = float(d["additional_margin_pct"])
    if not isinstance(d["cases"], list) or not 1 <= len(d["cases"]) <= 12:
        raise ValidationError("需有 1 至 12 個同時運轉工況")
    for case in d["cases"]:
        _text(case, "工況", limit=80)
    if len(set(d["cases"])) != len(d["cases"]):
        raise ValidationError("工況識別碼重複")
    if d["binding"] is not None:
        if not isinstance(d["binding"], dict) or set(d["binding"]) != {"project_id", "fingerprint"}:
            raise ValidationError("主案來源綁定格式不符")
        for value in d["binding"].values():
            _text(value, "主案來源綁定", limit=100)
    for kind, field in (("demand", "demands"), ("capacity", "capacities")):
        if not isinstance(d[field], list) or len(d[field]) > 500:
            raise ValidationError("容量計畫來源過多或格式不符")
        seen = set()
        for row in d[field]:
            if not isinstance(row, dict) or set(row) != set(new_row(kind, "row")):
                raise ValidationError("容量計畫列欄位不完整")
            for key in ("id", "asset_id", "name"):
                _text(row[key], key, limit=100)
            _text(row["boundary"], "供應邊界", blank=True, limit=200)
            if row["id"] in seen:
                raise ValidationError("列識別碼重複；更新相同 ID 應取代，不可再加一列")
            seen.add(row["id"])
            if row["system"] not in UNITS:
                raise ValidationError("不支援的公用系統")
            if not isinstance(row["conditions"], dict) or set(row["conditions"]) != set(CONDITIONS[row["system"]]):
                raise ValidationError("系統工況欄位不完整")
            for key, value in row["conditions"].items():
                if key in ("fluid", "exhaust_type"):
                    if value is not None:
                        _text(value, key, limit=100)
                else:
                    lo, hi = (-100, 300) if key.endswith("_c") else (0, 1e7)
                    if key == "rho_kg_m3":
                        lo, hi = 1, 3000
                    if key == "cp_kj_kgk":
                        lo, hi = .01, 20
                    _number(value, key, lo, hi, unknown=True)
                    if value is not None and key in ("voltage_v", "frequency_hz", "absolute_kpa") and value <= 0:
                        raise ValidationError(key + " 必須大於零")
                    if key == "phases" and value is not None and value not in (1, 3):
                        raise ValidationError("相數只接受 1 或 3")
            c = row["conditions"]
            if row["system"] in ("CHW", "PCW") and c["supply_c"] is not None and c["return_c"] is not None and c["return_c"] <= c["supply_c"]:
                raise ValidationError("冷卻迴路回水溫度必須高於供水溫度")
            if type(row["quantity"]) is not int or not 1 <= row["quantity"] <= 10000:
                raise ValidationError("台數需為 1 至 10000 的整數")
            if not isinstance(row["values"], dict) or set(row["values"]) != set(d["cases"]):
                raise ValidationError("每列需明列所有同時工況；未知值請填 null")
            for value in row["values"].values():
                _number(value, "單台需求／容量", unknown=True)
            if not isinstance(row["source"], dict) or set(row["source"]) != {"reference", "revision", "fingerprint"}:
                raise ValidationError("來源需有文件、版次及快照指紋欄位")
            for value in row["source"].values():
                _text(value, "來源", blank=True)
            for key in ("notes", "pending"):
                if not isinstance(row[key], list) or len(row[key]) > 100:
                    raise ValidationError("來源說明格式不符")
                for value in row[key]:
                    _text(value, "來源說明")
            if kind == "demand":
                if type(row["demand_complete"]) is not bool:
                    raise ValidationError("需求完整性確認必須為布林值")
                if row["phase"] not in ("current", "expansion"):
                    raise ValidationError("需求需標示現有或擴建")
                _number(row["coincidence"], "同時率", hi=1, unknown=True)
                _number(row["included_margin_pct"], "來源已含裕度", hi=1000, unknown=True)
            else:
                _number(row["derating"], "容量降額係數", hi=1, unknown=True)
    if not isinstance(d["alternatives"], list) or len(d["alternatives"]) > 50:
        raise ValidationError("替代方案格式不符")
    ids = set()
    for alt in d["alternatives"]:
        if not isinstance(alt, dict) or set(alt) != {"id", "name", "demand_ids", "capacity_ids"}:
            raise ValidationError("方案欄位不完整")
        for key in ("id", "name"):
            _text(alt[key], key, limit=100)
        if alt["id"] in ids:
            raise ValidationError("方案識別碼重複")
        ids.add(alt["id"])
        for key, field in (("demand_ids", "demands"), ("capacity_ids", "capacities")):
            values = alt[key]
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values) or len(values) != len(set(values)) or set(values) - {r["id"] for r in d[field]}:
                raise ValidationError("方案來源重複或已不存在")
    return d


def upsert_row(plan, kind, row):
    """Return a validated copy; same stable ID replaces, never adds twice."""
    if kind not in ("demand", "capacity"):
        raise ValidationError("不支援的容量列種類")
    d = copy.deepcopy(plan)
    field = "demands" if kind == "demand" else "capacities"
    d[field] = [r for r in d[field] if r["id"] != row["id"]] + [copy.deepcopy(row)]
    return validate_plan(d)


def _group_key(row):
    # Numeric spelling (7 versus 7.0) is not a different physical condition.
    c = {k: float(v) if isinstance(v, (int, float)) else v for k, v in row["conditions"].items()}
    return row["system"], row["boundary"], project_hash(c)


def _total(values):
    return None if any(v is None for v in values) else sum(values)


def evaluate_plan(plan, current_binding=None):
    p = validate_plan(plan)
    global_issues = []
    if not p["scope"].strip() or not p["scope_confirmed"]:
        global_issues.append("服務範圍與需求／供應清單完整性尚未明確確認")
    if p["additional_margin_pct"] and not p["margin_reason"].strip():
        global_issues.append("額外裕度尚未提供依據")
    stale = p["binding"] is not None and p["binding"] != current_binding
    if stale:
        global_issues.append("主案來源已變更或目前無法核對；舊快照不可判定容量足夠，請重新擷取並覆核")
    alternatives = p["alternatives"] or [dict(id="all", name="目前全部列", demand_ids=[r["id"] for r in p["demands"]], capacity_ids=[r["id"] for r in p["capacities"]])]
    results = []
    for alt in alternatives:
        demand = [r for r in p["demands"] if r["id"] in alt["demand_ids"]]
        capacity = [r for r in p["capacities"] if r["id"] in alt["capacity_ids"]]
        issues = list(global_issues)
        if not demand:
            issues.append("方案未列任何需求，不能把空清單當成零負荷")
        for rows in (demand, capacity):
            identities = [(r["system"], r["asset_id"]) for r in rows]
            if len(identities) != len(set(identities)):
                raise ValidationError("同一方案重複計入相同系統／實體來源；替代設備請分開方案，不可加總")
        groups = defaultdict(lambda: {"demands": [], "capacities": []})
        for rows, field in ((demand, "demands"), (capacity, "capacities")):
            for row in rows:
                groups[_group_key(row)][field].append(row)
        group_results = []
        for (system, boundary, _), group in groups.items():
            rows = group["demands"] + group["capacities"]
            c = rows[0]["conditions"]
            pending = list(issues)
            if not boundary.strip() or any(v is None for v in c.values()):
                pending.append("供應邊界或同工況資料未知，不可合併為已核對容量")
            if not group["demands"]:
                pending.append("此供應條件沒有相符需求；不同條件不可互抵")
            if not group["capacities"]:
                pending.append("沒有同邊界同工況的供應容量；缺資料不是零容量")
            for row in rows:
                pending.extend(row["pending"])
                if not row["source"]["reference"].strip() or not row["source"]["revision"].strip():
                    pending.append(row["id"] + " 來源文件／版次待補")
                if row in group["demands"] and not row["demand_complete"]:
                    pending.append(row["id"] + " 需求完整性尚未確認；數值只列已知小計，不推算完整需求餘量。")
                if row in group["demands"] and row["included_margin_pct"] is None:
                    pending.append(row["id"] + " 來源已含裕度未知；不得誤認為未含裕度")
            cases = []
            for case in p["cases"]:
                amounts = {phase: [] for phase in ("current", "expansion")}
                known_amounts = []
                for row in group["demands"]:
                    v, f = row["values"][case], row["coincidence"]
                    amount = None if v is None or f is None else v * row["quantity"] * f
                    known_amounts.append(amount)
                    amounts[row["phase"]].append(amount if row["demand_complete"] else None)
                current, expansion = (_total(amounts[phase]) for phase in ("current", "expansion"))
                combined = _total([current, expansion]) if group["demands"] else None
                design = None if combined is None else combined * (1 + p["additional_margin_pct"] / 100)
                units, installed = [], []
                for row in group["capacities"]:
                    v, f = row["values"][case], row["derating"]
                    unit = None if v is None or f is None else v * f
                    units.append(unit)
                    installed.append(None if unit is None else unit * row["quantity"])
                normal = _total(installed) if installed else None
                n1 = None if normal is None else normal - max(units)
                normal_headroom = None if design is None or normal is None else normal - design
                n1_headroom = None if design is None or n1 is None else n1 - design
                thermal = None
                if system in ("CHW", "PCW") and design is not None and all(c[k] is not None for k in ("rho_kg_m3", "cp_kj_kgk", "supply_c", "return_c")):
                    thermal = design / 60000 * c["rho_kg_m3"] * c["cp_kj_kgk"] * (c["return_c"] - c["supply_c"])
                cases.append(dict(case=case, current=current, expansion=expansion, combined=combined,
                                  design_demand=design, known_subtotal=sum(v for v in known_amounts if v is not None),
                                  normal_capacity=normal, n_minus_one_capacity=n1,
                                  normal_headroom=normal_headroom, n_minus_one_headroom=n1_headroom,
                                  normal_deficit=None if normal_headroom is None else max(0.0, -normal_headroom),
                                  n_minus_one_deficit=None if n1_headroom is None else max(0.0, -n1_headroom),
                                  equivalent_thermal_kw=thermal))
            if any(x["design_demand"] is None or x["normal_capacity"] is None for x in cases):
                pending.append("至少一個同時工況的需求／容量／係數未知；只顯示已知小計")
            def status(key):
                if pending:
                    return "待資料／待覆核"
                return "容量不足" if any(x[key] < -1e-9 for x in cases) else "初篩容量足夠"
            known_design = [x["design_demand"] for x in cases]
            peak = None if any(v is None for v in known_design) else max(known_design)
            group_results.append(dict(system=system, unit=UNITS[system], boundary=boundary, conditions=c,
                                      demands=copy.deepcopy(group["demands"]), capacities=copy.deepcopy(group["capacities"]),
                                      cases=cases, peak_design_demand=peak,
                                      normal_status=status("normal_headroom"), n_minus_one_status=status("n_minus_one_headroom"),
                                      issues=list(dict.fromkeys(pending))))
        results.append(dict(id=alt["id"], name=alt["name"], groups=group_results, issues=issues))
    return dict(plan_hash=project_hash(p), plan=p, checked_binding=copy.deepcopy(current_binding),
                stale=stale, alternatives=results, limitation=LIMITATION)


@localized_report
def capacity_report(result):
    """Recompute from inputs; never render a tampered or stale cached evaluation."""
    p = result["plan"]
    if result["plan_hash"] != project_hash(p):
        raise ValidationError("報告輸入已變更；請重新計算")
    result = evaluate_plan(p, current_binding=result.get("checked_binding"))
    lines = ["容量／擴建／替代方案初篩", verbatim(p["name"]),
             "合成驗證案例，非真實專案驗證" if p["synthetic"] else "使用者填報資料，尚非真實工程驗收",
             LIMITATION, "來源文件／版次由填報者提供；本報告不會重新讀取外部原廠或設備表檔案的後續變更。", "計畫 SHA256：" + result["plan_hash"],
             "服務範圍：" + (verbatim(p["scope"]) if p["scope"] else "未知"),
             f"額外裕度：{p['additional_margin_pct']:.6g}%（每一同時工況加總後僅套用一次）；依據：" + (verbatim(p["margin_reason"]) if p["margin_reason"] else "未填"),
             "需求取各同時工況總和的最大值，不把各設備不同時間的峰值相加。來源已含裕度保留，不自動扣除或重套。",
             "水量與等效熱量為同一需求的不同表達，不再相加；電力 kW 不由熱量換算。",
             "只有另行確認完整的需求值才參與完整需求、餘量及缺口；未確認值只保留為已知小計。"]
    if p["binding"]:
        lines.append("主案快照：" + verbatim(str(p["binding"])) + ("｜來源過期或未核對" if result["stale"] else "｜與本次提供主案一致"))
    def issue_text(issue, rows):
        # Pending records belong to the source/author. Preserve them literally.
        for row in rows:
            if issue in row["pending"]:
                return verbatim(issue)
            prefix = row["id"] + " "
            if issue.startswith(prefix):
                return verbatim(row["id"]) + issue[len(row["id"]):]
        return issue
    fmt = lambda value: "未知" if value is None else format(value, ".9g")
    for alt in result["alternatives"]:
        lines += ["", "方案：" + verbatim(alt["name"], default="目前全部列")] + ["待辦：" + v for v in alt["issues"]]
        for group in alt["groups"]:
            unit = group["unit"]
            lines += [f"{group['system']}｜{verbatim(group['boundary']) if group['boundary'] else '邊界未知'}｜{unit}", "工況：" + verbatim(str(group["conditions"])),
                      "正常：" + group["normal_status"] + "；N−1：" + group["n_minus_one_status"]]
            for row in group["cases"]:
                lines.append(f"  {verbatim(row['case'])}：現有 {fmt(row['current'])} + 擴建 {fmt(row['expansion'])} → 含額外裕度 {fmt(row['design_demand'])} {unit}；正常容量 {fmt(row['normal_capacity'])}／N−1 {fmt(row['n_minus_one_capacity'])}；餘量 {fmt(row['normal_headroom'])}／{fmt(row['n_minus_one_headroom'])}；缺口 {fmt(row['normal_deficit'])}／{fmt(row['n_minus_one_deficit'])}")
                if row["design_demand"] is None:
                    lines.append("  已知小計（非完整需求）：" + fmt(row["known_subtotal"]) + " " + unit)
                if row["equivalent_thermal_kw"] is not None:
                    lines.append("  同一設計水量的等效熱量：" + fmt(row["equivalent_thermal_kw"]) + " kW（不是額外負荷）")
            lines.append("同時工況設計峰值：" + fmt(group["peak_design_demand"]) + " " + unit)
            for kind, rows in (("需求", group["demands"]), ("供應", group["capacities"])):
                for row in rows:
                    factor = (f"同時率 {row['coincidence']}；來源已含裕度 {row['included_margin_pct']}%；需求完整性：" + ("已另行確認" if row["demand_complete"] else "尚未確認") if kind == "需求" else f"降額係數 {row['derating']}")
                    lines.append(f"{kind} {verbatim(row['id'])}／實體 {verbatim(row['asset_id'])}：{row['quantity']} 台 × 單台 {verbatim(str(row['values']))}；{factor}；來源 {verbatim(str(row['source']))}")
                    lines.extend("  註：" + verbatim(x) for x in row["notes"])
            lines.extend("待辦：" + issue_text(x, group["demands"] + group["capacities"]) for x in group["issues"])
    return "\n".join(lines) + "\n"


def read_plan(path):
    return validate_plan(read_json_file(path, max_bytes=4_000_000))
