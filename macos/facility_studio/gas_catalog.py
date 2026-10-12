"""Shared factory gas choices; a name is not a piping safety approval.

Only the legacy gas choices carry the original preliminary velocity references.
New process gases and mixtures require an explicitly entered design velocity.
The sizing model uses volumetric T/P/Z conversion, not a density/EOS database.
"""
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
