from .errors import InputError, ValidationError
import copy
import math
from collections.abc import Mapping
from .data import VOLTAGE_MAP
from .engine import calculate, electrical_from_inputs, gas_from_inputs, migrate_project
from .schema import FIELDS
from .utils import CFM_TO_CMH, GPM_TO_LPM, choice, number
from .field_state import effective_main, main_inactive

"""One explicit assessment shared by the desktop and exported reports."""


def validate_domain_inputs(i, keys):
    inactive = main_inactive(i)
    for k in keys:
        if k in inactive:
            continue
        f = FIELDS[k]
        v = i[k]
        if f["options"]:
            choice(v, f["options"], k)
        elif not f["text"]:
            number(v, k, f["low"], f["high"])


def independent_domains(p):
    p = migrate_project(copy.deepcopy(p))
    i = effective_main(p["inputs"])
    out = {}

    def attempt(name, fn):
        try:
            out[name] = {"result": fn(), "error": None}
        except (InputError, ValueError, KeyError, TypeError) as e:
            out[name] = {"result": None, "error": str(e)}

    def electric():
        validate_domain_inputs(i, [k for k, v in FIELDS.items() if v["page"] == 4])
        return electrical_from_inputs(i)

    def gas():
        validate_domain_inputs(
            i, [k for k, v in FIELDS.items() if v["page"] == 3] + ["atm_kpa"]
        )
        return gas_from_inputs(i)

    attempt("electric", electric)
    attempt("gas", gas)
    attempt("hvac", lambda: calculate(p, isolate_utilities=True))
    return out


UNIT_FACTORS = {
    **{
        "u_" + k: {"CMH": 1.0, "CFM": CFM_TO_CMH}
        for k in ["gex", "sex", "aex", "vex", "hex"]
    },
    **{
        k: {"LPM": 1.0, "GPM": GPM_TO_LPM}
        for k in ["u_mchw", "u_chw", "u_dccw", "u_pcw_tot", "u_hw"]
    },
    **{
        k: {"SLPM": 1.0, "SCFM": 28.316846592, "CMH": 1000 / 60}
        for k in ["u_gas1", "u_gas2", "u_gas3", "u_pv"]
    },
}
UNIT_VALUES = {
    "u_" + k: k + "_q"
    for k in ["gex", "sex", "aex", "vex", "hex", "gas1", "gas2", "gas3"]
}
UNIT_VALUES.update(
    u_mchw="mchw_q",
    u_chw="chw_q",
    u_dccw="dccw_q",
    u_pcw_tot="pcw_tot",
    u_hw="hw_q",
    u_pv="pv_q",
)
for pan, keys in [
    ("up", ["eq", "oven"]),
    ("np", ["fan", "heat", "humid", "exh", "pump"]),
]:
    for key in keys:
        UNIT_VALUES["u_e_" + pan + "_" + key] = "e_" + pan + "_" + key


def converted_units(i, key, old, new):
    if old == new:
        return {}
    if key == "u_unit":
        scale = {"W/(m²·K)": 1.0, "kcal/(h·m²·K)": 4.1868 / 3.6}
        return {
            k: number(i[k], k, 0) * scale[old] / scale[new]
            for k in ["wall_u", "floor_u"]
        }
    if key.startswith("u_e_"):
        pan = key.split("_")[2]
        pf_key = f"e_{pan}_pf"
        pf = (
            number(i[pf_key], pf_key, 0.1, 1)
            if i.get(f"e_{pan}_pf_mode") == "本盤獨立 PF"
            else number(i["e_pf"], "e_pf", 0.1, 1)
        )
        scale = {
            "kW": 1.0,
            "HP": 0.745699871582 / number(i["e_eff"], "e_eff", 0.1, 1),
            "A": math.sqrt(3) * VOLTAGE_MAP[i["e_volt"]] * pf / 1000,
            "kVA": pf,
            "W": 0.001,
        }
    else:
        scale = UNIT_FACTORS[key]
    value = UNIT_VALUES[key]
    return {value: number(i[value], value, 0) * scale[old] / scale[new]}


def _result(results, tool):
    """Accept direct engine results or desktop {result, inputs} records."""
    value = results.get(tool)
    if isinstance(value, dict) and "result" in value:
        value = value["result"]
    return value if isinstance(value, dict) else None


def electrical_device_loads(results, inputs=None):
    """Explicit electrical inputs only; thermal kW never become feeder kW.

    The returned list has one row per distinct source. Repeated transfers replace
    source values; they do not add another copy of the previous feeder total.
    Chiller electrical input is included only with an explicit COP or input kW.
    """
    i = inputs or {}
    loads = []

    def add(name, value):
        kw = number(value, name, 0, 1e9)
        if kw:
            if any(row["name"] == name for row in loads):
                raise InputError("設備清單含重複來源，請勿再次加入FFU、照明或CHWP", "device_loads")
            loads.append(dict(name=name, power_kw=kw, basis="電氣輸入"))

    clean = _result(results, "cleanroom")
    heat = _result(results, "heat_loads")
    light = _result(results, "lighting")
    pump = _result(results, "pumps")
    if clean:
        add("FFU", clean.get("ffu_fan_kw", 0))
    elif heat:
        add("FFU", heat.get("q_ffu_kw", 0))
    if light:
        add("照明", light["total_kw"])
    elif heat:
        add("照明", heat["q_lighting_kw"])
    if pump:
        add("CHWP", pump["motor_input_kw"])
    add("MAU", i.get("mau_input_kw", 0))
    add("製程設備", i.get("process_input_kw", 0))
    # Room equipment sensible heat need not equal the equipment input power.
    # Use only an explicitly provided electrical equipment schedule.
    for index, load in enumerate(i.get("device_loads", [])):
        if not isinstance(load, dict) or "power_kw" not in load:
            raise InputError("設備用電清單需含name及power_kw", "device_loads")
        name = str(load.get("name", f"其他設備{index + 1}"))
        add(name, load["power_kw"])
    explicit_chiller = number(i.get("chiller_input_kw", 0), "chiller_input_kw", 0, 1e9)
    cop = (number(i.get("chiller_cop", 0), "chiller_cop", 0, 20)
           if not explicit_chiller else 0.0)
    if explicit_chiller:
        add("Chiller", explicit_chiller)
    elif cop and heat:
        add("Chiller", heat["q_total_kw"] / cop)
    return loads


def upstream_values(tool, results, inputs=None):
    """Build an inspectable, non-mutating patch for the user's transfer button.

    results must contain current successful calculations; the UI removes a
    source when its inputs change. No implicit saved-file writes occur here.
    """
    i = inputs or {}
    clean = _result(results, "cleanroom")
    heat = _result(results, "heat_loads")
    water = _result(results, "water") or _result(results, "pipes")
    light = _result(results, "lighting")
    if tool == "heat_loads":
        values = {}
        if clean:
            values.update(area=str(clean["area_m2"]), persons=str(clean["persons"]),
                          oa_cmh=str(clean["oa_cmh"]), ffu_count=str(clean["ffu_count"]),
                          ffu_unit_kw=str(clean["ffu_unit_kw"]))
        if light:
            area = clean["area_m2"] if clean else light["area_m2"]
            if abs(area - light["area_m2"]) > 1e-6 * max(1, area):
                raise ValidationError("照明與潔淨室面積不同，請先確認同一計算範圍，再帶入熱負荷。", "area")
            values["area"] = str(area)
            values["lighting_w_m2"] = str(light["total_kw"] * 1000 / area)
        air = _result(results, "air")
        if air and air.get("comparison_state"):
            if air["delta_h_kj_kg"] < 0:
                raise ValidationError("A−B為負焓差，屬加熱工況，不能帶入外氣冷卻焓差；請核對A/B方向。", "oa_delta_h")
            values.update(oa_delta_h=str(air["delta_h_kj_kg"]), air_v_da=str(air["state"]["v_da"]),
                          oa_load_basis="外氣至室內基準" if air["comparison_basis"] == "室內狀態" else "外氣至實際露點送風")
        return values
    if tool in ("water", "pipes") and heat:
        return dict(mode="已知熱量", power=str(heat["q_total_kw"]), power_unit="kW")
    if tool == "pumps" and water:
        return dict(flow=str(water["pipe"]["lpm"]), flow_unit="LPM",
                    head_m=str(water["pressure"]["head_m"]))
    if tool == "electrical":
        loads = electrical_device_loads(results, i)
        return (dict(power=str(sum(row["power_kw"] for row in loads)),
                     power_unit="kW", kind="連續運轉") if loads else {})
    return {}


def transfer_upstream(tool, results, inputs=None):
    """Return a new input mapping with upstream values adopted once."""
    out = dict(inputs or {})
    out.update(upstream_values(tool, results, out))
    return out


def calculate_pipeline(inputs):
    """Run the short-form design chain with each adopted input preserved.

    inputs maps tool names to input dictionaries, plus optional 'electrical'
    fields chiller_cop/chiller_input_kw/device_loads. Each output remains a
    normal calculate_tool result. Only the explicit terminal/static allowances
    in pumps contribute additional head.
    """
    from .simple_engines import calculate_tool
    from .simple_schema import defaults

    tools = ("cleanroom", "lighting", "heat_loads", "water", "pumps", "electrical")
    if not isinstance(inputs, Mapping):
        raise InputError("串接輸入需為工具與欄位的對照表。", code="invalid_input")
    unknown = set(inputs) - set(tools) - {"pipes"}
    if unknown:
        raise InputError("未知的串接工具：" + ", ".join(sorted(map(str, unknown))), code="unknown_field")
    if "water" in inputs and "pipes" in inputs:
        raise InputError("water 與 pipes 代表同一工具，請只提供一份水管輸入。", "water", code="conflicting_input")
    for name, values in inputs.items():
        tool = "water" if name == "pipes" else name
        if not isinstance(values, Mapping):
            raise InputError("工具輸入需為欄位對照表：" + name, name)
        allowed = set(defaults(tool)) | ({"device_loads"} if tool == "electrical" else {"air_v_da"} if tool == "heat_loads" else set())
        unknown = set(values) - allowed
        if unknown:
            field = name + "." + str(sorted(unknown, key=str)[0])
            raise InputError("未知的串接輸入欄位：" + field, field, code="unknown_field")

    results, adopted = {}, {}
    for tool in tools:
        if tool == "lighting" and tool not in inputs:
            continue
        values = defaults(tool)
        values.update(inputs.get(tool, inputs.get("pipes", {}) if tool == "water" else {}))
        values.update(upstream_values(tool, results, values))
        adopted[tool] = values
        results[tool] = calculate_tool(tool, values)
    results["electrical_loads"] = electrical_device_loads(results, adopted["electrical"])
    results["adopted_inputs"] = adopted
    warnings = [message for value in results.values() if isinstance(value, dict)
                for message in value.get("warnings", [])]
    electrical_i = adopted["electrical"]
    supplied = {row["name"] for row in results["electrical_loads"]}
    if "Chiller" not in supplied:
        warnings.append("冰機未提供COP或輸入電功率，配電合計尚未含冰機；熱負荷kW未當成電氣kW。")
    if "MAU" not in supplied:
        warnings.append("MAU輸入電功率尚未提供，配電合計未含MAU風機及其他箱內用電設備。")
    if "製程設備" not in supplied:
        warnings.append("製程設備輸入電功率尚未提供，配電合計未含製程設備；室內顯熱不直接當成設備用電。")
    if not results["water"]["pressure"]["equipment_included"] and float(adopted["pumps"].get("terminal_head_m", 0)) == 0:
        warnings.append("管路及泵浦尚未納入盤管與末端設備壓降，泵浦選型為管路小計。")
    results["warnings"] = warnings
    return results
