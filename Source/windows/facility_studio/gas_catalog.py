"""Shared factory gas choices; a name is not a piping safety approval.

Only the legacy gas choices carry the original preliminary velocity references.
New process gases and mixtures require an explicitly entered design velocity.
The sizing model uses volumetric T/P/Z conversion, not a density/EOS database.
"""
import math
from .data import GAS_DESIGN_VELOCITY_MPS
from .errors import ValidationError

CUSTOM_GAS = "自訂／混合氣"
GAS_NAMES = {
    "N2": ("氮氣", "Nitrogen"),
    "CDA": ("潔淨乾燥空氣", "Clean dry air"),
    "O2": ("氧氣", "Oxygen"),
    "Ar": ("氬氣", "Argon"),
    "He": ("氦氣", "Helium"),
    "H2": ("氫氣", "Hydrogen"),
    "CO2": ("二氧化碳", "Carbon dioxide"),
    "GN2": ("氣態氮氣", "Gaseous nitrogen"),
    "PN2": ("純氮氣", "Pure nitrogen"),
    "N2O": ("氧化亞氮", "Nitrous oxide"),
    "NH3": ("氨氣", "Ammonia"),
    "CH4": ("甲烷", "Methane"),
    "C2H2": ("乙炔", "Acetylene"),
    "CO": ("一氧化碳", "Carbon monoxide"),
    "NF3": ("三氟化氮", "Nitrogen trifluoride"),
    "CF4": ("四氟化碳", "Carbon tetrafluoride"),
    "C2F6": ("六氟乙烷", "Hexafluoroethane"),
    "C3F8": ("八氟丙烷", "Octafluoropropane"),
    "C4F8": ("八氟環丁烷", "Octafluorocyclobutane"),
    "C4F6": ("六氟丁二烯", "Hexafluorobutadiene"),
    "CH2F2": ("二氟甲烷", "Difluoromethane"),
    "SF6": ("六氟化硫", "Sulfur hexafluoride"),
    "SiH4": ("矽甲烷", "Silane"),
    "Si2H6": ("乙矽烷", "Disilane"),
    "PH3": ("磷化氫", "Phosphine"),
    "AsH3": ("砷化氫", "Arsine"),
    "B2H6": ("乙硼烷", "Diborane"),
    "BF3": ("三氟化硼", "Boron trifluoride"),
    "BCl3": ("三氯化硼", "Boron trichloride"),
    "SiF4": ("四氟化矽", "Silicon tetrafluoride"),
    "Cl2": ("氯氣", "Chlorine"),
    "HCl": ("氯化氫", "Hydrogen chloride"),
    "HBr": ("溴化氫", "Hydrogen bromide"),
    "HF": ("氟化氫", "Hydrogen fluoride"),
    "WF6": ("六氟化鎢", "Tungsten hexafluoride"),
    "GeH4": ("鍺甲烷", "Germane"),
    "Ne": ("氖氣", "Neon"),
    "Kr": ("氪氣", "Krypton"),
    "Xe": ("氙氣", "Xenon"),
    "CHF3": ("三氟甲烷", "Trifluoromethane"),
    "CH3F": ("氟甲烷", "Fluoromethane"),
    "F2": ("氟氣", "Fluorine"),
    "ClF3": ("三氟化氯", "Chlorine trifluoride"),
    "H2S": ("硫化氫", "Hydrogen sulfide"),
    "SiH2Cl2": ("二氯矽烷", "Dichlorosilane"),
    "SiHCl3": ("三氯矽烷", "Trichlorosilane"),
    "SiCl4": ("四氯化矽", "Silicon tetrachloride"),
    "SO2": ("二氧化硫", "Sulfur dioxide"),
    "NO": ("一氧化氮", "Nitric oxide"),
    "C3H6": ("丙烯", "Propylene"),
    CUSTOM_GAS: ("自訂／混合氣", "Custom / mixed gas"),
}
GAS_OPTIONS = tuple(GAS_NAMES)

# Critical temperatures (°C) from NIST Chemistry WebBook / Air Liquide Gas Encyclopedia.
GAS_TRIPLE_T_C = {
    "SiCl4": -68.8, "SiHCl3": -126.5, "HF": -83.6, "WF6": 1.85,
    "BCl3": -107.3, "ClF3": -76.3, "SiH2Cl2": -122.0, "C4F6": -60.0,
    "C4F8": -41.4, "SO2": -75.5, "Si2H6": -132.5, "Cl2": -101.5,
    "C3F8": -147.7, "NH3": -77.7, "C3H6": -185.2, "CO2": -56.6,
}

GAS_CRITICAL_T_C = {
    "He": -267.95, "H2": -240.0, "Ne": -228.7, "N2": -146.9, "GN2": -146.9,
    "PN2": -146.9, "CDA": -140.6, "CO": -140.2, "F2": -128.8, "Ar": -122.3,
    "O2": -118.6, "NO": -93.0, "CH4": -82.6, "Kr": -63.8, "CF4": -45.6,
    "NF3": -39.2, "SiF4": -14.1, "BF3": -12.3, "SiH4": -3.5, "B2H6": 16.7,
    "Xe": 16.6, "C2F6": 19.9, "CHF3": 26.1, "CO2": 31.0, "C2H2": 35.2,
    "GeH4": 34.8, "N2O": 36.4, "CH3F": 44.6, "SF6": 45.5, "PH3": 51.6,
    "HCl": 51.5, "CH2F2": 78.1, "HBr": 89.8, "C3H6": 91.9, "AsH3": 99.9,
    "H2S": 100.0, "C3F8": 71.9, "C4F8": 115.2, "NH3": 132.4, "Cl2": 144.0,
    "C4F6": 150.0, "SO2": 157.5, "Si2H6": 158.9, "ClF3": 174.0,
    "SiH2Cl2": 176.0, "BCl3": 178.8, "WF6": 179.6, "HF": 188.0,
    "SiHCl3": 206.0, "SiCl4": 234.0,
}

# Verified normal boiling point (°C at 101.325 kPa), 25°C saturation vapor pressure (kPa abs),
# critical temperature (°C), and valid Clausius-Clapeyron screening range (°C).
# Source: NIST Chemistry WebBook / SEMI F1 / Matheson Gas Data Book.
GAS_PHASE_DATA = {
    "SiCl4":   (57.6,   31.0, 234.0, -10.0, 60.0),
    "SiHCl3":  (31.8,   77.0, 206.0, -10.0, 60.0),
    "HF":      (19.5,  122.0, 188.0, -10.0, 60.0),
    "WF6":     (17.1,  133.0, 179.6,   5.0, 40.0),
    "BCl3":    (12.6,  168.0, 178.8, -10.0, 60.0),
    "ClF3":    (11.75, 171.0, 174.0, -10.0, 60.0),
    "SiH2Cl2":  (8.3,  168.0, 176.0, -10.0, 60.0),
    "C4F6":     (6.0,  215.0, 150.0, -10.0, 60.0),
    "C4F8":    (-6.0,  310.0, 115.2, -20.0, 60.0),
    "SO2":    (-10.0,  390.0, 157.5, -20.0, 60.0),
    "Si2H6":  (-14.3,  390.0, 158.9, -20.0, 60.0),
    "Cl2":    (-34.0,  770.0, 144.0, -25.0, 60.0),
    "C3F8":   (-36.7,  860.0,  71.9, -25.0, 50.0),
    "NH3":    (-33.3, 1003.0, 132.4, -25.0, 60.0),
    "C3H6":   (-47.6, 1158.0,  91.9, -25.0, 55.0),
}

GAS_BOILING_POINT_C = {k: v[0] for k, v in GAS_PHASE_DATA.items()}
GAS_VAPOR_PRESSURE_KPA_25C = {k: v[1] for k, v in GAS_PHASE_DATA.items()}


def saturation_pressure_kpa(gas, temperature_c=25.0):
    """Estimate saturation vapor pressure (kPa abs) within validated subcritical temperature bounds."""
    if gas not in GAS_PHASE_DATA:
        return None
    tb_c, p25, tc_c, tmin_c, tmax_c = GAS_PHASE_DATA[gas]
    t = float(temperature_c)
    if t >= tc_c or t < tmin_c or t > tmax_c:
        return None
    tb_k = tb_c + 273.15
    t25_k = 298.15
    t_k = t + 273.15
    if abs(t_k - t25_k) < 1e-6:
        return p25
    denom = (1.0 / tb_k) - (1.0 / t25_k)
    if abs(denom) < 1e-9:
        return p25
    b_slope = math.log(p25 / 101.325) / denom
    return 101.325 * math.exp(b_slope * ((1.0 / tb_k) - (1.0 / t_k)))


def evaluate_gas_phase(gas, temperature_c, absolute_kpa, mole_fraction=1.0):
    """Evaluate phase state: returns phase_status, liquefaction_risk (True/False/None), vapor_pressure_kpa."""
    t = float(temperature_c)
    p_partial = float(absolute_kpa) * float(mole_fraction)
    if gas == CUSTOM_GAS:
        return dict(
            phase_status="未知／混合氣須按組分分壓對照原廠相圖", status="未知／混合氣須按組分分壓對照原廠相圖",
            liquefaction_risk=None,
            vapor_pressure_kpa=None,
        )
    t_tp = GAS_TRIPLE_T_C.get(gas)
    if t_tp is not None and t <= t_tp:
        return dict(phase_status="未知／低於三相點", status="未知／低於三相點", liquefaction_risk=None, vapor_pressure_kpa=None, triple_t_c=t_tp)
    tc_c = GAS_CRITICAL_T_C.get(gas)
    if tc_c is not None and t >= tc_c:
        return dict(
            phase_status="超臨界／高於臨界溫度", status="超臨界／高於臨界溫度",
            liquefaction_risk=False,
            vapor_pressure_kpa=None,
            critical_t_c=tc_c,
        )
    psat = saturation_pressure_kpa(gas, t)
    if psat is None:
        return dict(
            phase_status="未知／超出內建溫域或待原廠蒸氣壓資料", status="未知／超出內建溫域或待原廠蒸氣壓資料",
            liquefaction_risk=None,
            vapor_pressure_kpa=None,
        )
    # Use 90% of saturation vapor pressure as the engineering safety margin
    risk = bool(p_partial >= 0.90 * psat)
    return dict(
        phase_status="液化或逼近飽和風險" if risk else "氣相安全區間", status="液化或逼近飽和風險" if risk else "氣相安全區間",
        liquefaction_risk=risk,
        vapor_pressure_kpa=psat,
        critical_t_c=tc_c,
    )


def reference_velocity(gas):
    return GAS_DESIGN_VELOCITY_MPS.get(gas) if gas in GAS_NAMES else None


def custom_name(value, field_name):
    if not isinstance(value, str) or not value.strip() or len(value) > 120 or any(ord(c) < 32 for c in value):
        raise ValidationError("請填氣體名稱與混合比例，限120字且不可含換行。", field_name)
    return value.strip()


def gas_label(gas, name=None):
    if gas == CUSTOM_GAS:
        return name or CUSTOM_GAS
    return gas + "（" + GAS_NAMES[gas][0] + "）"


def has_demand(value):
    try:
        return float(value) != 0
    except (TypeError, ValueError):
        return True  # Keep incomplete drafts active so validation can locate them.


def switched_velocity(old_gas, new_gas, raw):
    if old_gas == new_gas:
        return raw
    new_reference = reference_velocity(new_gas)
    if new_reference is None:
        return ""
    if not raw.strip():
        return format(new_reference, "g")
    try:
        if float(raw) == reference_velocity(old_gas):
            return format(new_reference, "g")
    except ValueError:
        pass
    return raw
