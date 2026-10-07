"""Explicit, persisted demand ledger. Updating an ID replaces only that source.

Summer and winter are coincident cases. Water circuits with different design
temperatures or fluids remain separate; a main-workbench row adopts one circuit.
"""

import copy
import math
from collections import defaultdict

from .errors import ValidationError
from .schema import FIELDS
from .utils import project_hash, VOLTAGE_MAP

LOOPS = {
    "MCHW": ("mchw_q", "u_mchw", "chw1_dt", "chw1_in"),
    "CHW": ("chw_q", "u_chw", "dt_chw", "chw2_in"),
    "HW": ("hw_q", "u_hw", "dt_hw", None),
    "PCW": ("pcw_tot", "u_pcw_tot", "dt_pcw_sys", None),
}
POWER_KEYS = {"e_up_eq", "e_up_oven", "e_np_fan", "e_np_heat", "e_np_humid", "e_np_exh", "e_np_pump"}
FLOW_KEYS = {"gas1_q", "gas2_q", "gas3_q", "pv_q", "gex_q", "sex_q", "aex_q", "vex_q", "hex_q", "upw_q"}
SUM_KEYS = POWER_KEYS | FLOW_KEYS


def empty_ledger():
    return dict(version=1, entries={}, original={}, baseline={}, last_updates={}, selections={})


def finite(value, minimum=0, maximum=1e9):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValidationError("需求彙整數值不合法")
    return value


def validate_ledger(value):
    if not isinstance(value, dict) or set(value) != set(empty_ledger()) or value["version"] != 1:
        raise ValidationError("需求彙整格式不符")
    d = copy.deepcopy(value)
    for name in ("original", "last_updates"):
        fields = d[name]
        if not isinstance(fields, dict) or set(fields) - set(FIELDS) or any(not isinstance(v, str) or len(v) > 1000 for v in fields.values()):
            raise ValidationError("需求彙整目標欄位不符")
    if not isinstance(d["baseline"], dict) or set(d["baseline"]) - SUM_KEYS:
        raise ValidationError("其他服務負荷欄位不符")
    for v in d["baseline"].values():
        finite(v)
    if not isinstance(d["selections"], dict) or set(d["selections"]) - set(LOOPS) or any(not isinstance(v, str) or len(v) > 100 for v in d["selections"].values()):
        raise ValidationError("採用迴路記錄不符")
    if not isinstance(d["entries"], dict) or len(d["entries"]) > 500:
        raise ValidationError("需求來源過多或格式不符")
    required = {"id", "name", "kind", "source_hash", "updates", "water", "power", "notes", "pending"}
    for ident, entry in d["entries"].items():
        if not isinstance(ident, str) or not ident or len(ident) > 100 or not isinstance(entry, dict) or set(entry) != required or entry["id"] != ident:
            raise ValidationError("需求來源識別不符")
        if entry["kind"] not in ("AHU", "設備表"):
            raise ValidationError("需求來源種類不符")
        for key in ("name", "source_hash"):
            if not isinstance(entry[key], str) or not entry[key] or len(entry[key]) > 1000:
                raise ValidationError("需求來源名稱或雜湊不符")
        if not isinstance(entry["updates"], dict) or set(entry["updates"]) - set(FIELDS) or any(not isinstance(v, str) or len(v) > 1000 for v in entry["updates"].values()):
            raise ValidationError("需求來源欄位不符")
        for key in ("notes", "pending"):
            if not isinstance(entry[key], list) or len(entry[key]) > 50 or any(not isinstance(v, str) or len(v) > 1000 for v in entry[key]):
                raise ValidationError("需求來源說明不符")
        if not isinstance(entry["water"], list) or len(entry["water"]) > 20:
            raise ValidationError("水迴路來源格式不符")
        for water in entry["water"]:
            if not isinstance(water, dict) or set(water) != {"loop", "circuit", "supply", "return", "rho", "cp", "mu", "summer_lpm", "winter_lpm"}:
                raise ValidationError("水迴路條件不完整")
            if water["loop"] not in LOOPS or not isinstance(water["circuit"], str) or not 1 <= len(water["circuit"]) <= 100:
                raise ValidationError("水迴路識別不符")
            finite(water["supply"], -40, 120)
            finite(water["return"], -40, 120)
            if abs(water["supply"] - water["return"]) < 0.01:
                raise ValidationError("水迴路供回水溫差必須大於零")
            finite(water["rho"], 900, 1300)
            finite(water["cp"], 2, 5)
            finite(water["mu"], .0001, .1)
            finite(water["summer_lpm"])
            finite(water["winter_lpm"])
        if not isinstance(entry["power"], dict) or set(entry["power"]) - {"UP", "NP"}:
            raise ValidationError("盤別來源格式不符")
        for power in entry["power"].values():
            if not isinstance(power, dict) or set(power) != {"kw", "kvar", "design_kw", "design_kvar", "branch_floor_a", "length_m", "voltage"}:
                raise ValidationError("盤別設計需求不完整")
            for v in power.values():
                finite(v)
    return d


def circuit_id(water):
    return project_hash({k: water[k] for k in ("loop", "circuit", "supply", "return", "rho", "cp", "mu")})[:24]


def aggregate_ledger(ledger, inputs):
    d = validate_ledger(ledger)
    updates, notes, pending, groups = {}, [], [], {}
    summed, scalar_values = defaultdict(float), defaultdict(set)
    powers = defaultdict(list)
    for entry in d["entries"].values():
        notes.extend(entry["notes"])
        pending.extend(entry["pending"])
        for key, value in entry["updates"].items():
            if key in SUM_KEYS:
                summed[key] += finite(float(value))
            else:
                scalar_values[key].add(value)
        for pan, power in entry["power"].items():
            powers[pan].append(power)
        for water in entry["water"]:
            ident = circuit_id(water)
            if ident not in groups:
                groups[ident] = dict(water, id=ident, summer_lpm=0.0, winter_lpm=0.0, sources=[])
            group = groups[ident]
            group["summer_lpm"] += water["summer_lpm"]
            group["winter_lpm"] += water["winter_lpm"]
            group["sources"].append(entry["name"])
    for key, values in scalar_values.items():
        if len(values) != 1:
            raise ValidationError("來源條件不同，不能合併到同一主案欄位：" + FIELDS[key]["label"], key)
        updates[key] = next(iter(values))
    for key, value in summed.items():
        updates[key] = format(value + d["baseline"].get(key, 0), ".15g")
    for loop in LOOPS:
        candidates = [g for g in groups.values() if g["loop"] == loop]
        for g in candidates:
            g["design_lpm"] = max(g["summer_lpm"], g["winter_lpm"])
            g["adopted"] = False
        selected = d["selections"].get(loop)
        if len(candidates) == 1:
            selected = candidates[0]["id"]
        group = next((g for g in candidates if g["id"] == selected), None)
        if len(candidates) > 1:
            pending.append(loop + " 有不同供回水／介質／供應迴路，分開列示；主案水力列只能選其中一組，不能代表全廠總管。")
        if not group:
            continue
        group["adopted"] = True
        flow, unit, dt, tin = LOOPS[loop]
        updates.update({flow: format(group["design_lpm"], ".15g"), unit: "LPM", dt: format(abs(group["supply"] - group["return"]), ".15g"), loop.lower() + "_link": "獨立輸入"})
        if tin:
            updates[tin] = format(group["supply"], ".15g")
        prefix = loop.lower() + "_"
        updates.update({prefix + "fluid_mode": "本迴路獨立物性", prefix + "fluid_name": "來源迴路：" + group["circuit"], **{prefix + k: format(group[k], ".15g") for k in ("rho", "cp", "mu")}})
    voltage = VOLTAGE_MAP[inputs["e_volt"]]
    for pan, records in powers.items():
        if any(abs(p["voltage"] - voltage) > .01 for p in records):
            raise ValidationError("來源盤電壓與主案三相線電壓不同，請另案計算", "e_volt")
        prefix = "e_" + pan.lower()
        base_pf = float(d["original"].get(prefix + "_pf", inputs[prefix + "_pf"]) if d["original"].get(prefix + "_pf_mode", inputs.get(prefix + "_pf_mode")) == "本盤獨立 PF" else inputs["e_pf"])
        base = sum(d["baseline"].get(k, 0) for k in summed if k in POWER_KEYS and k.startswith(prefix + "_"))
        for key in POWER_KEYS:
            if not key.startswith(prefix + "_") or key in summed:
                continue
            unit_key = "u_" + key
            unchanged = inputs[key] == d["last_updates"].get(key) and inputs[unit_key] == d["last_updates"].get(unit_key)
            value = float(d["original"].get(key, inputs[key]) if unchanged else inputs[key])
            unit = d["original"].get(unit_key, inputs[unit_key]) if unchanged else inputs[unit_key]
            kw = value if unit == "kW" else value * .745699871582 / float(inputs["e_eff"]) if unit == "HP" else value * math.sqrt(3) * voltage * base_pf / 1000
            base += kw
            if unit != "kW":
                # A and shaft-HP drafts used the original panel PF/efficiency.
                # Normalize their unchanged physical input before setting a
                # new equivalent panel PF; otherwise their kW would drift.
                updates[key] = format(kw, ".15g")
                updates[unit_key] = "kW"
        base_q = base * math.tan(math.acos(base_pf))
        p = sum(x["kw"] for x in records) + base
        q = sum(x["kvar"] for x in records) + base_q
        dp = sum(x["design_kw"] for x in records) + base * 1.25
        dq = sum(x["design_kvar"] for x in records) + base_q * 1.25
        kva = math.hypot(p, q)
        updates[prefix + "_pf_mode"] = "本盤獨立 PF"
        updates[prefix + "_pf"] = format(p / kva if kva else 1, ".15g")
        updates[prefix + "_design_floor"] = format(max(math.hypot(dp, dq) * 1000 / (math.sqrt(3) * voltage), max(x["branch_floor_a"] for x in records)), ".15g")
        # The main row already receives the explicit design floor; do not apply
        # 125% twice. Each imported feeder retains its own independent report.
        updates[prefix + "_type"] = "一般負載"
        notes.append(pan + " 彙整運轉 P/Q 與來源設計電流；各來源設計餘裕相加，較只加全群最大馬達保守。支路候選仍保留在設備明細。")
        updates["e_length_m"] = format(max(float(d["original"].get("e_length_m", inputs["e_length_m"])), float(updates.get("e_length_m", "0")), *(x["length_m"] for x in records)), ".15g")
    return dict(updates=updates, water=list(groups.values()), sources=[dict(id=e["id"], name=e["name"], kind=e["kind"]) for e in d["entries"].values()], notes=list(dict.fromkeys(notes)), pending=list(dict.fromkeys(pending)))


def updated_ledger(ledger, entry, inputs):
    d = copy.deepcopy(ledger)
    d["entries"][entry["id"]] = copy.deepcopy(entry)
    validate_ledger(d)
    summary = aggregate_ledger(d, inputs)
    for key in summary["updates"]:
        d["original"].setdefault(key, inputs[key])
    updates = dict(summary["updates"])
    for key, previous in d["last_updates"].items():
        if key not in updates and inputs[key] == previous:
            updates[key] = d["original"][key]
    d["last_updates"] = dict(summary["updates"])
    return d, updates, summary


def removed_ledger(ledger, ident, inputs):
    d = copy.deepcopy(ledger)
    d["entries"].pop(ident, None)
    summary = aggregate_ledger(d, inputs)
    updates = dict(summary["updates"])
    for key, previous in d["last_updates"].items():
        if key not in updates and inputs[key] == previous:
            updates[key] = d["original"][key]
    d["last_updates"] = dict(summary["updates"])
    return d, updates, summary


def ahu_contribution(result, ident, inputs):
    from .design_workflow import ahu_source_hash
    i = result["inputs"]
    entry = dict(id=ident, name=i["name"], kind="AHU", source_hash=ahu_source_hash(i), updates={}, water=[], power={}, notes=[], pending=[])
    factor = 1 + float(i["sf"]) / 100
    for tag, loop in (("c1", "MCHW"), ("c2", "CHW")):
        supply, ret = float(i[tag + "_in"]), float(i[tag + "_out"])
        entry["water"].append(dict(loop=loop, circuit=loop, supply=supply, **{"return": ret}, rho=1000.0, cp=4.1868, mu=.001, **{s + "_lpm": result[s][tag]["water_kw"] * factor * 60000 / (1000 * 4.1868 * (ret - supply)) for s in ("summer", "winter")}))
    hw = {}
    for season in ("summer", "winter"):
        for tag in ("h1", "h2"):
            h = result[season][tag]
            if h["hw_kw"] <= 1e-8:
                continue
            water = h["effective_water"]
            supply, ret = water["hw_in"], water["hw_out"]
            key = (supply, ret)
            if key not in hw:
                hw[key] = dict(loop="HW", circuit="HW", supply=supply, **{"return": ret}, rho=1000.0, cp=4.1868, mu=.001, summer_lpm=0.0, winter_lpm=0.0)
            hw[key][season + "_lpm"] += h["water_lpm"] * factor
    entry["water"].extend(hw.values())
    fan = float(i["fan_qty"]) * float(i["fan_unit_kw"])
    heat = sum(float(i[t + "_kw"]) for t in ("h1", "h2") if i[t + "_source"] in ("電熱", "熱水＋電熱"))
    steam = float(i["steam_kw"]) if "蒸汽" in i["humidifier"] else 0.0
    pump = float(i["pump_input_kw"]) if "水洗" in i["humidifier"] and i["pump_input_kw"].strip() else 0.0
    if "蒸汽" in i["humidifier"] and steam <= 0:
        entry["pending"].append(i["name"] + " 蒸汽設備額定耗電未知；彙整只列已知電力，不可作為完整 NP 需求。")
    if "水洗" in i["humidifier"] and not i["pump_input_kw"].strip():
        entry["pending"].append(i["name"] + " 水洗泵額定耗電未知；彙整只列已知電力，請補原廠資料。")
    for tag, value in (("fan", fan), ("heat", heat), ("humid", steam), ("pump", pump)):
        entry["updates"].update({"e_np_" + tag: format(value, ".15g"), "u_e_np_" + tag: "kW"})
    pf = float(inputs["e_pf"])
    kw = fan + heat + steam + pump
    kvar = kw * math.tan(math.acos(pf))
    entry["power"]["NP"] = dict(kw=kw, kvar=kvar, design_kw=kw * 1.25, design_kvar=kvar * 1.25, branch_floor_a=0.0, length_m=0.0, voltage=VOLTAGE_MAP[inputs["e_volt"]])
    entry["notes"].extend([i["name"] + " 額定電力採回傳時共用 PF=" + format(pf, ".4g") + "；風機／電熱／加濕／水洗泵為不同設備，不由冷量換算耗電。", "只納入明確回傳的單機；同 ID 再回傳會更新原台，不能把方案 A/B 當成同時運轉的兩台。"])
    if result["quality"]["status"] != "通過":
        entry["pending"].append(i["name"] + " 單機狀態：" + result["quality"]["status"] + "；容量為需求草稿。")
    return entry


def equipment_contribution(result, group, inputs, target="UP"):
    system = group["system"]
    ident = "schedule-" + project_hash([system, group["group"], target, group.get("phases"), group.get("voltage"), group.get("exhaust_type")])[:32]
    entry = dict(id=ident, name=system + " / " + group["group"], kind="設備表", source_hash=project_hash(group), updates={}, water=[], power={}, notes=[], pending=[])
    u = entry["updates"]
    if system == "電力":
        voltage = VOLTAGE_MAP[inputs["e_volt"]]
        if group["phases"] != 3 or abs(group["voltage"] - voltage) > .01:
            raise ValidationError("只可帶入與主案相同線電壓的三相群組；單相與不同電壓請保留獨立分析。", "e_volt")
        prefix = "e_" + target.lower()
        key = prefix + ("_eq" if target == "UP" else "_exh")
        u.update({key: format(group["demand_kw"], ".15g"), "u_" + key: "kW"})
        entry["power"][target] = dict(kw=group["demand_kw"], kvar=group["demand_kvar"], design_kw=group["design_kw"], design_kvar=group["design_kvar"], branch_floor_a=group["minimum_active_branch_design_a"], length_m=group["feeder_length_m"], voltage=group["voltage"])
        entry["pending"].append("設備表進線候選需另核短路、啟動、相別與支路保護；用電不等於室內發熱。")
    elif system == "PCW":
        q = group["demand_lpm"]
        dt = group["thermal_kw"] * 60000 / (1000 * 4.1868 * q) if q > 0 else float(inputs["dt_pcw_sys"])
        if dt <= 0:
            raise ValidationError("PCW 需有效設備溫差才能帶入；請補設備水溫差。", "dt_pcw_sys")
        entry["water"].append(dict(loop="PCW", circuit=group["group"], supply=25.0, **{"return": 25.0 + dt}, rho=1000.0, cp=4.1868, mu=.001, summer_lpm=q, winter_lpm=q))
        entry["notes"].append("PCW 25°C 僅作供水條件占位，水溫差為流量加權等效值；原表未提供供回水工況，不代表原廠供水設計。")
        entry["pending"].append("PCW 實際供回水、季節同時率與最不利路徑待補；未改寫室內機台散熱。")
    elif system in ("CDA", "N2"):
        route = int(target)
        if route not in (1, 2, 3):
            raise ValidationError("請選特氣目的路別")
        # Imported schedules normalize at 25°C / 101.325 kPa(abs).
        q = group["demand_standard_lpm"] * 101.325 / float(inputs["gas_std_kpa"]) * (float(inputs["gas_std_t"]) + 273.15) / 298.15
        prefix = "gas" + str(route)
        u.update({prefix + "_type": "CDA" if system == "CDA" else "N2", prefix + "_q": format(q, ".15g"), "u_" + prefix: "SLPM"})
        entry["notes"].append("特氣需求已換到主案標準狀態；管內溫度、壓力與流速採主案該路條件，請核對後定寸。")
        entry["pending"].append("特氣來源最低絕壓 " + format(group["absolute_kpa"], ".6g") + " kPa、最高溫度 " + format(group["temperature_c"], ".6g") + "°C、流速上限 " + format(group["velocity_limit"], ".6g") + " m/s，尚需對照主案路別設定。")
    elif system == "EXHAUST":
        prefix = group["exhaust_type"].lower()
        u.update({prefix + "_q": format(group["demand_cmh"], ".15g"), "u_" + prefix: "CMH"})
        entry["pending"].append("排氣設備端最低靜壓不等於風機總 ESP；主案另計路徑壓損及一次風量餘裕。")
    elif system == "DI":
        u.update(upw_q=format(group["demand_lpm"], ".15g"), upw_type="DI (去離子水)", upw_quality_mode="自動參考值")
        entry["pending"].append("DI 帶入總流量含維持循環；水質參考值不是實測或原廠保證。")
    elif system == "PV":
        q = group["demand_standard_lpm"] * 101.325 / float(inputs["gas_std_kpa"]) * (float(inputs["gas_std_t"]) + 273.15) / 298.15
        u.update(pv_q=format(q, ".15g"), u_pv="SLPM", pv_torr=format(group["pressure_torr"], ".15g"), pv_pressure_unit="Torr(abs)")
        entry["pending"].append("PV 只作連續介質流速初估；幫浦／管路导通率待確認，來源流量是否從室內抽取仍依主案設定。")
    else:
        raise ValidationError("此群組尚無主案目的欄位")
    entry["notes"].append("同系統／供應群組／目的欄位再帶入會更新原來源；一個群組的所有設備請集中在同一份表。")
    return entry
