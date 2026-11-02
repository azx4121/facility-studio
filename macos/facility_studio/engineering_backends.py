"""Shared, explicit numerical backends for the production calculation paths.

All public results are plain SI floats; Quantity objects never enter projects.
No optional silent fallback is allowed when a required backend is missing.
"""
from functools import lru_cache
from importlib.metadata import version
import math


@lru_cache(maxsize=1)
def registry():
    # The coil/process library and the application must share one registry.
    from hvac import UNITS
    UNITS.define("fs_mmAq = 9.80665 * pascal")
    UNITS.define("fs_mH2O = 9806.65 * pascal")
    UNITS.define("fs_USRT = 3.5168528420667 * kilowatt")
    UNITS.define("fs_Btu = 1055.05585262 * joule")
    UNITS.define("fs_JRT = 3.86116 * kilowatt")
    UNITS.define("fs_kcal = 4186.8 * joule")
    return UNITS


def convert(value, source, target):
    result = registry().Quantity(float(value), source).to(target).magnitude
    if not math.isfinite(result):
        from .errors import ValidationError
        raise ValidationError("單位換算結果超出有限數值範圍。", "value", code="overflow")
    return float(result)


@lru_cache(maxsize=1)
def psychrometrics():
    import psychrolib
    psychrolib.SetUnitSystem(psychrolib.SI)
    return psychrolib


def saturation_pressure(t_c):
    return float(psychrometrics().GetSatVapPres(t_c))


def moist_enthalpy(t_c, w):
    lib = psychrometrics()
    # PsychroLib floors W to 1e-7. Preserve the physical W=0 limit and the
    # existing ultra-dry range using the same ASHRAE equation's linear term.
    bounded = max(w, lib.MIN_HUM_RATIO)
    return float(lib.GetMoistAirEnthalpy(t_c, bounded) / 1000
                 + (w - bounded) * (2501 + 1.86 * t_c))


def moist_volume(t_c, w, p_kpa):
    lib = psychrometrics()
    bounded = max(w, lib.MIN_HUM_RATIO)
    v = lib.GetMoistAirVolume(t_c, bounded, p_kpa * 1000)
    # Keep the project's explicit molecular mass ratio 0.621945. PsychroLib
    # rounds its reciprocal to 1.607858; normalize that rounded coefficient
    # and its dry-air humidity floor rather than perturb legacy airflow.
    return float(v * (1 + w / .621945) / (1 + 1.607858 * bounded))


def darcy_friction(re, relative_roughness):
    from fluids.friction import Colebrook, friction_laminar
    if re <= 0:
        return 0.0
    if re < 2300:
        return float(friction_laminar(re))
    if re >= 4000:
        return float(Colebrook(re, relative_roughness))
    # A declared project convention; the transitional regime is uncertain.
    low = friction_laminar(2300)
    high = Colebrook(4000, relative_roughness)
    return float(low + (high - low) * (re - 2300) / 1700)


@lru_cache(maxsize=512)
def liquid_water(t_c, p_kpa):
    from CoolProp.CoolProp import PhaseSI, PropsSI
    t, p = float(t_c) + 273.15, float(p_kpa) * 1000
    if PhaseSI("T", t, "P", p, "HEOS::Water") != "liquid":
        raise ValueError("所填溫壓不是單相液態純水，不能套用水管模型。")
    return dict(
        rho=float(PropsSI("D", "T", t, "P", p, "HEOS::Water")),
        cp=float(PropsSI("C", "T", t, "P", p, "HEOS::Water") / 1000),
        mu=float(PropsSI("V", "T", t, "P", p, "HEOS::Water")),
        fluid="純水", source="CoolProp HEOS／IAPWS-95",
        temperature_c=float(t_c), pressure_abs_kpa=float(p_kpa),
    )


@lru_cache(maxsize=4096)
def cooling_process(h_in, h_out, w_in, w_out, m_da, condensate_h):
    """Use python-hvac's coupled heat/mass process with explicit condensate.

    Its negative Q is heat removed from the air control volume; condensed
    liquid leaves with positive enthalpy and is not counted as coil water load.
    """
    from hvac.air_conditioning import AirConditioningProcess
    q = registry().Quantity
    # Construct an incomplete process first, then solve the balances. This
    # avoids its constructor's unrelated automatic ADP extrapolation: a
    # general cooling process need not have a physical saturated ADP.
    process = AirConditioningProcess(m_da=q(m_da, "kg/s"), h_w=q(condensate_h, "kJ/kg"))
    for key, value, unit in (("h_ai", h_in, "kJ/kg"), ("h_ao", h_out, "kJ/kg"),
                             ("W_ai", w_in, "kg/kg"), ("W_ao", w_out, "kg/kg")):
        process[key] = q(value, unit)
    return float(-process.Q.to("kW").magnitude), float(-process.m_w.to("kg/s").magnitude)


def methods():
    return {
        "PsychroLib": "濕空氣飽和壓、焓與比容（SI／ASHRAE）",
        "python-hvac": "盤管熱質平衡（明列凝結水焓）與翅片管 ε-NTU",
        "fluids": "Colebrook Darcy 摩擦因子；過渡區保留明列插值",
        "CoolProp": "指定溫壓的 HEOS／IAPWS-95 單相純水物性",
        "Pint": "共同單位登錄庫；絕對溫度與溫差分開",
    }


def manifest():
    return {name: {"version": version(name), "method": method}
            for name, method in methods().items()}
