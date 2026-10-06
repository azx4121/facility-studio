from .errors import InputError
import copy
import math
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
        scale = {
            "kW": 1.0,
            "HP": 0.745699871582 / number(i["e_eff"], "e_eff", 0.1, 1),
            "A": math.sqrt(3)
            * VOLTAGE_MAP[i["e_volt"]]
            * number(i["e_pf"], "e_pf", 0.1, 1)
            / 1000,
        }
    else:
        scale = UNIT_FACTORS[key]
    value = UNIT_VALUES[key]
    return {value: number(i[value], value, 0) * scale[old] / scale[new]}
