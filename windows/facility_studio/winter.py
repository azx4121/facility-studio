"""Steady winter room balance for the explicitly entered envelope and gains."""

from .errors import ValidationError
from .utils import state_tw


def room_targets(inputs, room, parts, mass_da, moisture_summer, ffu_kw=None):
    n = lambda key: float(inputs[key])
    factor = 4.1868 / 3600 if inputs["u_unit"] == "kcal/(h·m²·K)" else 0.001
    # FFU operating ratio in winter is independent of process winter_gain_ratio (default 100%).
    ffu_ratio = float(inputs.get("winter_ffu_ratio", "100"))
    max_mau_t = float(inputs.get("winter_mau_max_t", "40"))
    variable_internal = (
        sum(parts[k] for k in ["equipment_net", "people", "lighting", "oven"])
        * n("winter_gain_ratio")
        / 100
    )
    if inputs["sys_type"].startswith("MAU"):
        if ffu_kw is not None:
            other_fan_kw = max(0.0, parts["fan"] - ffu_kw)
            fan_internal = (
                ffu_kw * ffu_ratio / 100
                + other_fan_kw * n("winter_gain_ratio") / 100
            )
        else:
            fan_internal = parts["fan"] * ffu_ratio / 100
    else:
        fan_internal = parts["fan"] * n("winter_gain_ratio") / 100
    internal = variable_internal + fan_internal
    wall = n("en_wall") * n("wall_u") * (n("ow_t") - room["t"]) * factor
    floor = (
        n("en_floor") * n("floor_u") * (n("winter_floor_adj_t") - room["t"]) * factor
    )
    sensible = internal + wall + floor + n("winter_solar_kw")
    moisture = moisture_summer * n("winter_moisture_ratio") / 100
    if mass_da <= 1e-9:
        if abs(sensible) > 1e-6 or moisture > 1e-10:
            raise ValidationError("零送風無法完成冬季室內熱濕平衡", "winter_model")
        return dict(
            sensible_kw=0.0,
            moisture_kg_s=0.0,
            supply_t=room["t"],
            unconstrained_supply_t=room["t"],
            supply_w=room["w"],
            dcc_kw=0.0,
            terminal_heat_kw=0.0,
            internal_kw=internal,
            fan_retained_kw=fan_internal,
            winter_ffu_ratio=ffu_ratio,
            winter_mau_max_t=max_mau_t,
            max_mau_t=max_mau_t,
            wall_kw=wall,
            floor_kw=floor,
            mau_overtemp_warning=False,
            mau_temp_capped=False,
        )
    supply_w = room["w"] - moisture / mass_da
    if supply_w < 0:
        raise ValidationError(
            "冬季定風量不足，所需送風含濕比小於零", "winter_moisture_ratio"
        )
    cp = 1.006 + 1.86 * supply_w
    unconstrained_t = room["t"] - sensible / (mass_da * cp)
    supply_t = unconstrained_t
    dcc_kw = 0.0
    terminal_heat_kw = 0.0
    mau_overtemp = False
    if inputs["sys_type"].startswith("MAU"):
        if supply_t < n("mau_supply_t"):
            supply_t = n("mau_supply_t")
            dcc_kw = max(0.0, sensible - mass_da * cp * (room["t"] - supply_t))
        elif supply_t > max_mau_t:
            mau_overtemp = True
            supply_t = max_mau_t
            terminal_heat_kw = max(0.0, -sensible - mass_da * cp * (supply_t - room["t"]))
    try:
        state_tw(supply_t, supply_w, n("atm_kpa"))
    except ValidationError as e:
        raise ValidationError(
            "冬季送風需求超出物性範圍或超飽和；需調整風量或負荷：" + str(e),
            "winter_model",
        ) from e
    return dict(
        sensible_kw=sensible,
        moisture_kg_s=moisture,
        supply_t=supply_t,
        unconstrained_supply_t=unconstrained_t,
        supply_w=supply_w,
        dcc_kw=dcc_kw,
        terminal_heat_kw=terminal_heat_kw,
        internal_kw=internal,
        fan_retained_kw=fan_internal,
        winter_ffu_ratio=ffu_ratio,
        winter_mau_max_t=max_mau_t,
        max_mau_t=max_mau_t,
        wall_kw=wall,
        floor_kw=floor,
        mau_overtemp_warning=mau_overtemp,
        mau_temp_capped=mau_overtemp,
    )
