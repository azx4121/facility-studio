"""Validated demand schedules; grouping never mixes incompatible supplies."""

from collections import defaultdict
import math
import re

from .data import PIPE_DB
from .equipment_io import Cell, EquipmentImportError
from .equipment_schema import SCHEMAS, SYSTEMS
from .errors import ValidationError
from .simple_engines import (
    electrical,
    GAS_FLOW_FACTORS,
    GAS_PRESSURE_FACTORS,
    FLOW_FACTORS,
)
from .simple_schema import defaults
from .utils import duct_selection, integer, number, water_selection
from .quick_tools import convert_all

REFERENCE_T = 25.0
REFERENCE_P = 101.325


def validate_rows(imported):
    active, skipped, errors = [], 0, []
    used = set()
    for entry in imported["records"]:
        system, row, cells = entry["system"], entry["row"], entry["cells"]
        current_column = "啟用(1/0)"
        try:
            enabled = cells.get("enabled", Cell())
            if (
                enabled.formula
                or enabled.excel_error
                or isinstance(enabled.value, bool)
            ):
                raise ValueError("請填數字1或0，不使用公式")
            switch = integer(
                1 if enabled.value in (None, "") else enabled.value, "enabled", 0, 1
            )
            if switch == 0:
                skipped += 1
                continue
            result = dict(system=system, row=row, adopted_defaults={})
            for spec in SCHEMAS[system]:
                key, current_column = spec["key"], spec["label"]
                cell = cells.get(key, Cell())
                if cell.excel_error:
                    raise ValueError("輸入儲存格含Excel錯誤值，請修正或貼上實際值")
                if cell.formula:
                    raise ValueError("輸入欄位請填實際數字／文字，不接受公式；請貼上值")
                value = cell.value
                if isinstance(value, bool):
                    raise ValueError("請填數字或選項，不使用TRUE／FALSE")
                if value is None or str(value).strip() == "":
                    if spec["required"]:
                        raise ValueError("必填；未知資料不能當成零")
                    value = spec["default"]
                    if value not in (None, ""):
                        result["adopted_defaults"][current_column] = value
                kind = spec["kind"]
                if value is None:
                    result[key] = None
                elif kind == "text":
                    text = str(value).strip()
                    if len(text) > 500 or any(ord(c) < 32 for c in text):
                        raise ValueError("文字過長或含換行／控制字元")
                    result[key] = text
                elif kind == "choice":
                    text = str(value).strip()
                    if key == "phases":
                        text = str(integer(value, key, 1, 3))
                    if text not in spec["options"]:
                        raise ValueError("可用選項：" + "、".join(spec["options"]))
                    result[key] = text
                else:
                    parse = integer if kind == "integer" else number
                    result[key] = parse(value, key, spec["low"], spec["high"])
            identity = system, result["id"]
            if identity in used:
                current_column = "設備編號"
                raise ValueError("同一系統的設備編號重複；多台相同設備請填設備台數")
            used.add(identity)
            active.append(result)
        except (ValueError, ValidationError) as error:
            errors.append(
                str(EquipmentImportError(str(error), system, row, current_column))
            )
    if errors:
        raise EquipmentImportError(
            "\n".join(errors[:30])
            + (f"\n其餘{len(errors)-30}項請修正後重試" if len(errors) > 30 else "")
        )
    if not active:
        raise EquipmentImportError(
            "沒有啟用的設備。請把實際設備的啟用欄設為1；範例預設0"
        )
    return active, skipped


def _candidate(power, pf, phases, voltage, kind, length, design=None):
    data = defaults("electrical")
    data.update(power=str(power), pf=str(pf), kind=kind, length=str(length))
    try:
        return (
            electrical(
                data,
                supply_override=(phases, voltage),
                design_current_a=design,
                conservative_drop=design is not None,
            ),
            None,
        )
    except ValidationError as error:
        return None, str(error)


def _gas_amount(row):
    if row["system"] == "PV":
        factors = {"Torr(abs)": 101.325 / 760, "kPa(abs)": 1.0, "mbar(abs)": 0.1}
        absolute = row["pressure"] * factors[row["pressure_unit"]]
        if not 101.325 / 760 - 1e-9 <= absolute <= 101.325 + 1e-9:
            raise EquipmentImportError(
                "PV模型限1~760Torr絕壓；更低壓力需真空導通模型",
                row["system"],
                row["row"],
                "管內絕對壓力",
            )
    else:
        gauge = row["pressure"] * GAS_PRESSURE_FACTORS[row["pressure_unit"]]
        if gauge > 30000:
            raise EquipmentImportError(
                "表壓超過300bar初估範圍", row["system"], row["row"], "管內表壓"
            )
        absolute = gauge + row["atmosphere"]
    temperature = row["temperature"]
    if row["unit"] == "ALPM":
        canonical = (
            row["flow"]
            * absolute
            / REFERENCE_P
            * (REFERENCE_T + 273.15)
            / (temperature + 273.15)
        )
    else:
        standard = row["flow"] * GAS_FLOW_FACTORS[row["unit"]]
        canonical = (
            standard
            * row["reference_p"]
            / REFERENCE_P
            * (REFERENCE_T + 273.15)
            / (row["reference_t"] + 273.15)
        )
    return canonical, absolute


def _gas_size(standard, absolute, temperature, velocity):
    actual = (
        standard
        * REFERENCE_P
        / absolute
        * (temperature + 273.15)
        / (REFERENCE_T + 273.15)
    )
    diameter = (
        math.sqrt(4 * actual / 60000 / math.pi / velocity) * 1000 if actual else 0.0
    )
    pipe = next((p for p in PIPE_DB if p["id"] >= diameter), None) if actual else None
    speed = actual / 60000 / (math.pi * (pipe["id"] / 1000) ** 2 / 4) if pipe else None
    return dict(
        actual_lpm=actual,
        minimum_id_mm=diameter,
        pipe=pipe,
        velocity_mps=speed,
        size=(
            pipe["name"] if pipe else "無需求" if not actual else "超出管徑表，需另選管"
        ),
        within_table=not actual or pipe is not None,
    )


def analyze_equipment(imported):
    rows, skipped = validate_rows(imported)
    grouped = defaultdict(list)
    for row in rows:
        if row["system"] == "電力":
            key = row["system"], row["group"], int(row["phases"]), row["voltage"]
        elif row["system"] == "EXHAUST":
            key = row["system"], row["group"], row["exhaust_type"]
        else:
            key = row["system"], row["group"]
        grouped[key].append(row)
    result_groups, row_results, warnings = [], [], []
    electrical_config = "銅XLPE、端子60°C、環溫35°C、同管3根、壓降≤3%；參考表初估。"

    def group_order(entry):
        key = entry[0]
        name = tuple(
            (1, int(part)) if part.isdigit() else (0, part.casefold())
            for part in re.split(r"([0-9]+)", key[1])
        )
        tail = key[2:]
        if key[0] == "EXHAUST":
            tail = (("GEX", "SEX", "AEX", "VEX", "HEX").index(key[2]),)
        return SYSTEMS.index(key[0]), name, tail

    for key, items in sorted(grouped.items(), key=group_order):
        system, name = key[:2]
        group = dict(
            system=system,
            group=name,
            equipment_rows=len(items),
            equipment_count=sum(r["quantity"] for r in items),
            warnings=[],
        )
        if system == "電力":
            phases, voltage = key[2:]
            p_full = q_full = p = q = pd = qd = 0.0
            motors, sockets = [], 0
            for row in items:
                raw = row["power"] * row["quantity"]
                ratio = math.tan(math.acos(row["pf"]))
                demand = raw * row["usage"] / 100
                p_full += raw
                q_full += raw * ratio
                p += demand
                q += demand * ratio
                multiplier = 1.25 if row["kind"] == "連續運轉" else 1.0
                pd += demand * multiplier
                qd += demand * ratio * multiplier
                if row["kind"] == "馬達" and demand > 0:
                    motors.append(
                        (row["power"] / row["pf"], row["power"], row["power"] * ratio)
                    )
                sockets += row["sockets"] * row["quantity"]
                branch, pending = _candidate(
                    row["power"], row["pf"], phases, voltage, row["kind"], row["length"]
                )
                row_results.append(
                    dict(
                        system=system,
                        id=row["id"],
                        name=row["name"],
                        group=name,
                        phases=phases,
                        voltage=voltage,
                        quantity=row["quantity"],
                        connected_kw=raw,
                        demand_kw=demand,
                        per_device_branch=branch,
                        pending=pending,
                        adopted_defaults=row["adopted_defaults"],
                    )
                )
            if motors:
                _, motor_p, motor_q = max(motors)
                pd += 0.25 * motor_p
                qd += 0.25 * motor_q
                group["warnings"].append(
                    "馬達群進線初估另加最大單台馬達25%；支路NFB仍需FLC、啟動與過載保護資料。"
                )
            kva, design_kva = math.hypot(p, q), math.hypot(pd, qd)
            pf = p / kva if kva else 1.0
            divisor = (math.sqrt(3) if phases == 3 else 1) * voltage
            current, design_current = kva * 1000 / divisor, design_kva * 1000 / divisor
            branch_floor = max(
                (
                    r["power"]
                    / r["pf"]
                    * 1000
                    / divisor
                    * (1.25 if r["kind"] != "一般設備" else 1)
                    for r in items
                    if r["usage"] > 0
                ),
                default=0,
            )
            if design_current < branch_floor - 1e-8:
                group["warnings"].append(
                    "同時需求低於最大單台負載；進線候選至少採該單台支路設計電流。同時率與實際最大需求仍須確認。"
                )
            design_current = max(design_current, branch_floor)
            length = max(r["length"] for r in items)
            candidate, pending = _candidate(
                p, pf, phases, voltage, "一般設備", length, design_current
            )
            group.update(
                phases=phases,
                voltage=voltage,
                connected_kw=p_full,
                connected_kva=math.hypot(p_full, q_full),
                demand_kw=p,
                demand_kvar=q,
                demand_kva=kva,
                equivalent_pf=pf,
                current_a=current,
                design_current_a=design_current,
                minimum_active_branch_design_a=branch_floor,
                candidate=candidate,
                pending=pending,
                sockets=sockets,
                feeder_length_m=length,
                formula="P=Σ台數×單台kW×同時率；Q=ΣP×tan(arccosPF)，S=√(P²+Q²)。連續負載125%，馬達群加最大單台25%。進線不低於同時率>0的最大單台支路設計電流。",
                basis=electrical_config
                + "PF採落後、正弦及平衡負載。進線壓降採設計電流與R/X上界；長度暫採群組已填最大配線距離，實際進線路徑另核。",
            )
            if phases == 1:
                group["warnings"].append(
                    "單相分組未指派A/B/C相；不可把這個電流當三相總盤電流。"
                )
        elif system in ("PCW", "DI"):
            full = demand = thermal_full = thermal = circulation = 0.0
            for row in items:
                flow = convert_all("水量", row["flow"], row["unit"])["LPM"]
                connected = flow * row["quantity"]
                used = connected * row["usage"] / 100
                extra = row.get("circulation", 0) * row["quantity"]
                full += connected
                demand += used
                circulation += extra
                kw = (
                    used * 1000 * 4.1868 / 60000 * row["delta"]
                    if system == "PCW"
                    else None
                )
                if kw is not None:
                    thermal += kw
                    thermal_full += connected * 1000 * 4.1868 / 60000 * row["delta"]
                row_results.append(
                    dict(
                        system=system,
                        id=row["id"],
                        name=row["name"],
                        group=name,
                        connected_lpm=connected,
                        demand_lpm=used,
                        circulation_lpm=extra,
                        thermal_kw=kw,
                        adopted_defaults=row["adopted_defaults"],
                    )
                )
            velocity = min(r["velocity"] for r in items)
            design_flow = demand + circulation
            minimum_id = (
                math.sqrt(4 * design_flow / 60000 / math.pi / velocity) * 1000
                if design_flow
                else 0.0
            )
            pipe = water_selection(design_flow, velocity) if system == "PCW" else None
            group.update(
                connected_lpm=full + circulation,
                process_demand_lpm=demand,
                demand_lpm=design_flow,
                circulation_lpm=circulation,
                velocity_limit=velocity,
                minimum_id_mm=minimum_id,
                pipe=pipe,
                thermal_kw=thermal if system == "PCW" else None,
                connected_thermal_kw=thermal_full if system == "PCW" else None,
                formula=(
                    "主管量=Σ台數×每台LPM×同時率＋持續循環量；Q熱=ΣLPM×ρcp×ΔT/60000。"
                    if system == "PCW"
                    else "主管量=Σ台數×每台LPM×同時率＋Σ台數×額外循環LPM；D內=√(4Q/πv)。"
                ),
                basis=(
                    "PCW採清水ρ=1000、cp=4.1868；未核泵揚程／換熱器。"
                    if system == "PCW"
                    else "DI按實際內徑定寸；未套用碳鋼名目管徑。循環量不乘同時率，水質與供回水路徑另核。"
                ),
            )
        elif system in ("CDA", "N2", "PV"):
            full = demand = 0.0
            absolutes, temperatures = [], []
            for row in items:
                flow, absolute = _gas_amount(row)
                connected = flow * row["quantity"]
                used = connected * row["usage"] / 100
                full += connected
                demand += used
                absolutes.append(absolute)
                temperatures.append(row["temperature"])
                branch = _gas_size(flow, absolute, row["temperature"], row["velocity"])
                row_results.append(
                    dict(
                        system=system,
                        id=row["id"],
                        name=row["name"],
                        group=name,
                        connected_standard_lpm=connected,
                        demand_standard_lpm=used,
                        absolute_kpa=absolute,
                        per_device_pipe=branch,
                        adopted_defaults=row["adopted_defaults"],
                    )
                )
            pressure, temperature = min(absolutes), max(temperatures)
            velocity = min(r["velocity"] for r in items)
            size = _gas_size(demand, pressure, temperature, velocity)
            group.update(
                connected_standard_lpm=full,
                demand_standard_lpm=demand,
                reference_t=REFERENCE_T,
                reference_p=REFERENCE_P,
                absolute_kpa=pressure,
                temperature_c=temperature,
                velocity_limit=velocity,
                **size,
                formula="標準量按參考溫壓統一後加總；實際量=SLPM×P標準/P絕對×T管內(K)/T標準(K)；D內=√(4Q實際/πv)。",
                basis="流量統一至25°C／101.325kPa(abs)。同一群組採最低已填絕壓、最高溫度、最低流速上限定寸；僅流速初估，Z=1。",
            )
            if max(absolutes) - min(absolutes) > 1e-7:
                group["warnings"].append(
                    "同群組設備的管內壓力不同；定寸採最低壓力，供應壓力級次及支路減壓器仍須確認。"
                )
            if system == "PV":
                group.update(
                    pressure_torr=pressure * 760 / 101.325,
                    effective_pumping_m3h=size["actual_lpm"] * 0.06,
                    throughput_pa_m3s=size["actual_lpm"] / 60000 * pressure * 1000,
                )
                group["warnings"].append(
                    "列出的抽速是製程端所需有效抽速；未核真空管導通、氣體種類、洩漏、放氣及泵曲線，不能當泵銘牌選型。"
                )
            if not size["within_table"]:
                group["warnings"].append("需求超出管徑表；不以最大表列管徑假裝符合。")
        else:
            subtype = key[2]
            full = demand = 0.0
            pressures = []
            for row in items:
                cmh = row["flow"] * FLOW_FACTORS[row["unit"]]
                connected = cmh * row["quantity"]
                used = connected * row["usage"] / 100
                full += connected
                demand += used
                if row["pressure"] is not None:
                    pressures.append(row["pressure"])
                row_results.append(
                    dict(
                        system=system,
                        id=row["id"],
                        name=row["name"],
                        group=name,
                        exhaust_type=subtype,
                        connected_cmh=connected,
                        demand_cmh=used,
                        adopted_defaults=row["adopted_defaults"],
                    )
                )
            velocity = min(r["velocity"] for r in items)
            group.update(
                exhaust_type=subtype,
                connected_cmh=full,
                demand_cmh=demand,
                velocity_limit=velocity,
                rectangle=duct_selection(demand, velocity, 2, "方管"),
                round=duct_selection(demand, velocity, 2, "圓管"),
                known_terminal_pressure_pa=max(pressures) if pressures else None,
                pressure_complete=len(pressures) == len(items),
                formula="風量=Σ台數×單台CMH×同時率；A=CMH/3600/v。不同排氣類型分開彙總。",
                basis="靜壓只列已知設備端最大要求，沒有相加為風機ESP；全路徑阻力、洗滌塔及末端另核。",
            )
            if not group["pressure_complete"]:
                group["warnings"].append("部分設備靜壓未填，保留待資料，不當成0Pa。")
        if any(r["usage"] < 100 for r in items):
            group["warnings"].append(
                "同時率為輸入的初估係數；全開需求另列。常時排氣、吹掃及安全需求不得只用平均運轉率折減。"
            )
        result_groups.append(group)
    original = {(r["system"], r["id"]): r for r in rows}
    for detail in row_results:
        row = original[detail["system"], detail["id"]]
        detail["inputs"] = {
            spec["label"]: row[spec["key"]]
            for spec in SCHEMAS[row["system"]]
            if spec["key"] not in ("enabled", "id", "name", "notes")
        }
        detail["notes"] = row["notes"]
    panel_supplies = defaultdict(set)
    for g in result_groups:
        if g["system"] == "電力":
            panel_supplies[g["group"]].add((g["phases"], g["voltage"]))
    for name, supplies in panel_supplies.items():
        if len(supplies) > 1:
            warnings.append(
                f"{name}含多種供電方式，已分開列候選；總盤進線需單線圖、變壓器及相別分配，未合併電流。"
            )
    power_groups = [g for g in result_groups if g["system"] == "電力"]
    totals = dict(
        connected_kw=sum(g["connected_kw"] for g in power_groups),
        demand_kw=sum(g["demand_kw"] for g in power_groups),
        demand_kva_sum=sum(g["demand_kva"] for g in power_groups),
        sockets=sum(g["sockets"] for g in power_groups),
    )
    return dict(
        version="5.5.4",
        schema_id=imported["schema_id"],
        source_name=imported["source_name"],
        active_records=len(rows),
        skipped_records=skipped,
        groups=result_groups,
        rows=row_results,
        totals=totals,
        warnings=warnings,
        electrical_basis=electrical_config,
        pending="未自動產出正式盤體尺寸、遮斷容量、相別平衡、接地或管路壓損結論；需補單線圖／短路資料／配線及管路路徑／原廠性能。",
    )


def group_metrics(group):
    system = group["system"]
    if system == "電力":
        selected = (group["candidate"] or {}).get("selected")
        size = (
            f"{selected['nfb_a']:g}AT；{selected['size_mm2']:g}mm²×{selected['runs']}組/相"
            if selected
            else group["pending"] or "無需求"
        )
        return (
            f"{group['demand_kw']:,.3f}kW / {group['demand_kva']:,.3f}kVA",
            f"{group['current_a']:,.2f}A；設計{group['design_current_a']:,.2f}A",
            size,
        )
    if system in ("CDA", "N2", "PV"):
        return (
            f"{group['demand_standard_lpm']:,.3f}SLPM",
            f"{group['actual_lpm']:,.3f}ALPM",
            group["size"],
        )
    if system in ("PCW", "DI"):
        pipe = group["pipe"]
        size = (
            f"{pipe['size']}×{pipe['runs']}路"
            if pipe
            else f"內徑≥{group['minimum_id_mm']:.2f}mm"
        )
        secondary = (
            f"{group['thermal_kw']:,.3f}kW"
            if system == "PCW"
            else f"含循環{group['circulation_lpm']:,.3f}LPM"
        )
        return f"{group['demand_lpm']:,.3f}LPM", secondary, size
    rect, round_duct = group["rectangle"], group["round"]
    if not group["demand_cmh"]:
        return "0.000CMH", f"{group['exhaust_type']}；未核總ESP", "無需求"
    return (
        f"{group['demand_cmh']:,.3f}CMH",
        f"{group['exhaust_type']}；未核總ESP",
        f"{rect['w_mm']:g}×{rect['h_mm']:g}mm；圓Ø{round_duct['diameter_m']*1000:.1f}mm",
    )


def group_conditions(group):
    system = group["system"]
    if system == "電力":
        return f"{group['phases']}相{group['voltage']:g}V；等效PF={group['equivalent_pf']:.4f}；進線暫採單程{group['feeder_length_m']:g}m。"
    if system in ("CDA", "N2", "PV"):
        return f"定寸絕壓{group['absolute_kpa']:.3f}kPa；管內{group['temperature_c']:g}°C；流速上限{group['velocity_limit']:g}m/s。"
    if system in ("PCW", "DI"):
        return f"流速上限{group['velocity_limit']:g}m/s；最小實際內徑{group['minimum_id_mm']:.2f}mm；各設備溫差／循環量見明細。"
    pressure = group["known_terminal_pressure_pa"]
    pressure_text = (
        "尚無設備端靜壓資料"
        if pressure is None
        else f"已知設備端最高要求{pressure:g}Pa"
    )
    return f"流速上限{group['velocity_limit']:g}m/s；{pressure_text}；{'設備資料完整' if group['pressure_complete'] else '部分資料待補'}，未核風機總ESP。"


def equipment_report(result):
    lines = [
        "設備需求分析 V5.5.4",
        f"來源：{result['source_name']}",
        f"全檔啟用{result['active_records']}筆；略過{result['skipped_records']}筆",
        "",
    ]
    totals = result["totals"]
    lines += [
        f"全檔連接電力 {totals['connected_kw']:,.3f}kW；同時需求 {totals['demand_kw']:,.3f}kW",
        f"全檔供電分組kVA合計 {totals['demand_kva_sum']:,.3f}kVA；插座點位 {totals['sockets']}個",
        "",
    ]
    for group in result["groups"]:
        name = group["system"] + "／" + group["group"]
        if group["system"] == "電力":
            name += f"／{group['phases']}相{group['voltage']:g}V"
        if group["system"] == "EXHAUST":
            name += "／" + group["exhaust_type"]
        lines.append(name)
        lines.extend("  " + text for text in group_metrics(group))
        lines.append("  條件：" + group_conditions(group))
        if group["system"] == "電力":
            lines.append(
                f"  全開：{group['connected_kw']:,.3f}kW；插座{group['sockets']}個"
            )
        elif "connected_standard_lpm" in group:
            lines.append(f"  全開：{group['connected_standard_lpm']:,.3f}SLPM")
        elif "connected_lpm" in group:
            lines.append(f"  全開含循環：{group['connected_lpm']:,.3f}LPM")
        else:
            lines.append(f"  全開：{group['connected_cmh']:,.3f}CMH")
        if group["system"] == "PV":
            lines.append(
                f"  管內{group['pressure_torr']:.3f}Torr(abs)，製程端有效抽速≥{group['effective_pumping_m3h']:,.3f}m³/h（未核泵曲線）"
            )
        lines += ["  公式：" + group["formula"], "  採用：" + group["basis"]]
        lines.extend("  待確認：" + warning for warning in group["warnings"])
        lines.append("")
    lines += ["設備列別明細"]
    for row in result["rows"]:
        line = f"  {row['system']}／{row['id']} {row['name']} → {row['group']}"
        if row["system"] == "電力":
            candidate = (row["per_device_branch"] or {}).get("selected")
            line += f"，連接{row['connected_kw']:.3f}kW／同時{row['demand_kw']:.3f}kW"
            if candidate:
                line += f"；每台支路{candidate['nfb_a']:g}AT、{candidate['size_mm2']:g}mm²×{candidate['runs']}組"
            elif row["pending"]:
                line += "；待資料：" + row["pending"]
        elif "demand_standard_lpm" in row:
            line += f"，連接{row['connected_standard_lpm']:.3f}／同時{row['demand_standard_lpm']:.3f}SLPM"
        elif "demand_lpm" in row:
            line += f"，連接{row['connected_lpm']:.3f}／同時{row['demand_lpm']:.3f}LPM"
        else:
            line += f"，連接{row['connected_cmh']:.3f}／同時{row['demand_cmh']:.3f}CMH"
        lines.append(line)
        inputs = row["inputs"]
        keys = (
            ("設備台數", "同時使用率(%)", "功率因數(PF)", "負載類型")
            if row["system"] == "電力"
            else (
                "設備台數",
                "同時使用率(%)",
                "每台需求流量",
                "流量單位",
                "供回水溫差(K)",
                "每台額外循環量(LPM)",
                "管內表壓",
                "管內絕對壓力",
                "壓力單位",
            )
        )
        lines.append(
            "    輸入："
            + "；".join(f"{key}={inputs[key]}" for key in keys if key in inputs)
        )
        if row["adopted_defaults"]:
            lines.append(
                "    空白欄採預設："
                + "、".join(
                    f"{key}={value}" for key, value in row["adopted_defaults"].items()
                )
            )
        if row["notes"]:
            lines.append("    備註：" + row["notes"])
    lines += ["", *result["warnings"], result["pending"]]
    return "\n".join(lines) + "\n"
