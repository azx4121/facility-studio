"""Steady incompressible suction from a large vessel, referenced to pump datum."""
from .utils import number
from .errors import ValidationError

REFERENCE = "https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/npsh-1116954"
PURE = {"清水": "Water", "UPW／DI／RO": "Water", "乙醇": "Ethanol", "甲醇": "Methanol", "丙酮": "Acetone"}


def suction_check(data, name, temperature_c, density, velocity):
    if data.get("check_npsh", "0") != "1":
        return None
    def n(key, low, high):
        return number(data.get(key, ""), key, low, high)
    surface = n("suction_surface_kpa", .001, 10000)
    elevation = n("suction_level_m", -100, 1000)
    nozzle_offset = number(data.get("suction_nozzle_offset_m", "0"), "suction_nozzle_offset_m", -100, 100)
    losses = n("suction_loss_kpa", 0, 10000)
    if name in PURE:
        from CoolProp.CoolProp import PropsSI
        try:
            vapor = PropsSI("P", "T", temperature_c + 273.15, "Q", 0, PURE[name]) / 1000
        except ValueError:
            raise ValidationError("無法求得此溫度的飽和蒸氣壓", "liquid_t") from None
        vapor_source = "純液體操作溫度的飽和蒸氣壓"
    else:
        vapor = n("vapor_pressure_kpa", .000001, 10000)
        vapor_source = str(data.get("vapor_reference", "")).strip()
        if not vapor_source:
            raise ValidationError("混合液／化學液須填同溫度、濃度的泡點壓力來源", "vapor_reference")
    gravity = 9.80665
    rho_g = density * gravity
    available = (surface - vapor - losses) * 1000 / rho_g + elevation
    # Bernoulli from the vessel surface (velocity ~0) to suction nozzle.
    # NPSHa includes velocity head; do not add it again to the vessel equation.
    static_kpa = surface + rho_g * (elevation - nozzle_offset) / 1000 - losses - density * velocity**2 / 2000
    issues = []
    if surface <= vapor:
        issues.append("液槽表面壓力不高於泡點／飽和蒸氣壓，單相液體假設不成立。")
    if static_kpa <= vapor:
        issues.append("估算吸入口靜壓不高於蒸氣壓，吸入管可能閃蒸；不可採用單相結果選泵。")
    required = margin = None
    reference = str(data.get("pump_curve_reference", "")).strip()
    margin_source = str(data.get("npsh_margin_reference", "")).strip()
    if str(data.get("npshr_m", "")).strip():
        required = n("npshr_m", 0, 1000)
        if not reference:
            raise ValidationError("須填原廠曲線、泵型、流量與轉速的對應依據", "pump_curve_reference")
    else:
        issues.append("待提供工況原廠 NPSHr，不判定選泵條件。")
    if str(data.get("npsh_margin_m", "")).strip():
        margin = n("npsh_margin_m", 0, 1000)
        if not margin_source:
            raise ValidationError("須填原廠／業主採用的 NPSH 裕度依據", "npsh_margin_reference")
    else:
        issues.append("待提供本案 NPSH 裕度；不套用通用固定值。")
    threshold = required + margin if required is not None and margin is not None else None
    passed = threshold is not None and not issues and available >= threshold
    if threshold is not None and available < threshold:
        issues.append("可用 NPSHa 小於原廠 NPSHr 加本案裕度。")
    return dict(available_m=available, required_m=required, margin_m=margin,
                threshold_m=threshold, criterion_met=passed, vapor_kpa=vapor,
                vapor_source=vapor_source, surface_kpa=surface, level_m=elevation,
                nozzle_offset_m=nozzle_offset,
                losses_kpa=losses, suction_static_kpa=static_kpa,
                pump_reference=reference, margin_reference=margin_source,
                status="符合本案輸入的 NPSH 條件" if passed else "待資料或未達 NPSH 條件",
                warnings=issues, source=REFERENCE,
                formula="NPSHa=(液槽表面絕壓−蒸氣壓−吸入總壓損)/(ρg)+液面相對泵基準高度",
                scope="限大型液槽表面速度可忽略、等溫穩態滿管均質液體；吸入管採本頁內徑及流量。液位與吸入口高度均相對原廠 NPSH 基準面。吸入總壓損須另填，包含入口、管件、濾器及設備，不能直接套用排出路徑。全線局部高點、夾氣、瞬變、最小淹沒深度與泵全曲線須另核對。")
