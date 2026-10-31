"""Supply airflow of mixed-air systems (AHU / FCU / RCU): existence, conditioning and practicality.

Background (defect F-1). engine.calculate searches the smallest airflow for which the coil can deliver the
supply state the room balance asks for. The old feasibility test compared the coil-entering and supply
humidity ratios with an ABSOLUTE tolerance of 1e-10 kg/kg. Their difference shrinks as 1/airflow, so for a
room the coil can never dry (room humidity below the saturation humidity at the coil ADP) the test turned
true at an enormous airflow and the search "found" a solution of billions of CMH with a 0.00 K supply
temperature difference. That solution is a limit point at infinity, not a design.

Three layers, each answering a different question:

NUMERICAL   Is the root a regular root? The humidity test is rewritten in a form that does not depend on the
            airflow (net moisture the coil must remove, kg/s), and the conditioning of a moisture-limited
            root is reported (condition number).
PHYSICAL    Does any finite airflow exist at all? Answered analytically before searching, with the cause and the
            remedy (the chilled-water supply temperature that would make the room reachable).
ENGINEERING A finite airflow exists but is it a design? Judged by how much the loads inflate the airflow over
            the baseline the room already moves (the larger of the circulation / fresh-air floor and the
            sensible design airflow), NOT by a fixed air-change rate. Cleanroom circulation therefore never
            trips it, because the circulation is part of the baseline.

MAU systems do not use this search: their outdoor-air mass flow comes from a closed-form moisture balance and
is bounded by the sensible balance; FFU circulation is a separate quantity.
"""
import math

from .errors import InputError
from .utils import dewpoint

# Moisture-balance resolution (kg/kg) at the design airflow. Same value the old test used, but anchored at the
# starting airflow so it no longer grows with the trial airflow. It only decides whether the coil has any
# net moisture to remove; it is NOT a slack on reachability (see supply_humidity_reachable).
HUMIDITY_RESOLUTION = 1e-10

# The geometric airflow search, unchanged: up to 160 steps of x1.08 from the starting airflow.
SEARCH_STEPS = 160
SEARCH_GROWTH = 1.08
SEARCH_RANGE = SEARCH_GROWTH ** SEARCH_STEPS

# solve_c2_bypass rejects a coil whose required outlet dew point is more than this below the ADP floor, and a
# coil whose bypass factor at the lowest ADP is negative. The airflow search used to stop 1e-10 kg/kg
# (about 2e-7 K of dew point near 8 degC) inside that boundary, so the coil solver refused every
# moisture-limited solution the search had just found. Reachability therefore uses the strict criterion.
COIL_DEWPOINT_TOLERANCE_K = 1e-7

# The search starts from |qs| / 10 kg/s, i.e. a supply-to-room temperature difference of about 10 K.
DESIGN_SUPPLY_DT_K = 10.0
# Below this supply-to-room difference a load-driven airflow is not a practical design: coil and control
# sensitivity, duct and fan size. Engineering judgement, adjustable here in one place.
MIN_PRACTICAL_SUPPLY_DT_K = 2.0
# Airflow inflation at which the supply difference falls from the design value to the practical minimum.
INFLATION_FAIL = DESIGN_SUPPLY_DT_K / MIN_PRACTICAL_SUPPLY_DT_K
INFLATION_WARN = 2.0
# A moisture-limited airflow is m = moisture / (w_room - w_saturation_at_ADP). Its relative sensitivity to a
# relative input error e is kappa * e with kappa = w_room / (w_room - w_ADP). Inputs are given to about
# 0.1 %, so kappa above 1000 means the answer is dominated by input resolution.
INPUT_RESOLUTION = 1e-3
CONDITION_FAIL = 1.0 / INPUT_RESOLUTION


def moisture_to_remove(room, oa, oa_mass, moisture):
    """Net moisture (kg/s) the cooling coil must take out: outdoor-air moisture above the room plus generation."""
    return oa_mass * (oa["w"] - room["w"]) + moisture


def supply_humidity_reachable(ws, min_w, min_adp, p_kpa):
    """Can the coil deliver supply humidity ws? True when bypass factor >= 0 at the lowest admissible ADP.

    No negative slack: the coil solver needs BF >= 0 (within 1e-12) and the airflow search must stop where
    the coil solver can follow it.
    """
    return ws >= min_w and dewpoint(ws, p_kpa) >= min_adp - COIL_DEWPOINT_TOLERANCE_K


def humidity_tolerance(m_start):
    """Resolution of the moisture balance in kg/s, fixed by the starting airflow (never by the trial airflow)."""
    return HUMIDITY_RESOLUTION * m_start


def existence(room, oa, oa_mass, qs, moisture, min_adp, min_w, p_kpa, m_start, approach):
    """PHYSICAL layer. Raise InputError when no airflow the search can reach satisfies the room and the coil.

    Returns the analytic minimum airflows (kg/s) for the sensible and the moisture limits.
    """
    if qs > 1e-9 and min_adp >= room["t"] - 1e-9:
        raise InputError(
            f"未達條件：冰水供水＋ADP 裕度 {min_adp:.2f}°C 不低於室內乾球 {room['t']:.2f}°C，"
            f"盤管無法移除室內顯熱 {qs:.2f} kW；請降低冰水供水溫度或提高室內溫度",
            field_name="chw2_in",
        )
    lam = moisture_to_remove(room, oa, oa_mass, moisture)
    m_sens = qs / (1.006 * (room["t"] - min_adp)) if qs > 1e-9 else 0.0
    m_lat = 0.0
    if lam > humidity_tolerance(m_start):
        margin = room["w"] - min_w
        if margin <= 0:
            dp = dewpoint(room["w"], p_kpa)
            raise InputError(
                f"未達條件：盤管最低可達含濕量 {min_w * 1000:.3f} g/kg（冰水供水＋ADP 裕度 {min_adp:.2f}°C）"
                f"不低於室內含濕量 {room['w'] * 1000:.3f} g/kg（露點 {dp:.2f}°C），"
                f"任何風量都無法除濕；冰水供水溫度須低於 {dp - approach:.2f}°C，或提高室內相對濕度目標",
                field_name="chw2_in",
            )
        m_lat = moisture / margin if moisture > 0 else 0.0
    for flow, head in ((m_lat, "未達條件：除濕所需風量 "), (m_sens, "未達條件：顯熱所需風量 ")):
        if flow > m_start * SEARCH_RANGE:
            raise InputError(
                f"{head}{flow:.3g} kg/s 為基準風量 {m_start:.3g} kg/s 的 {flow / m_start:.3g} 倍，"
                f"超出可求解範圍（{SEARCH_RANGE:.3g} 倍）；冰水供水溫度與室內條件的裕度過小",
                field_name="chw2_in",
            )
    return dict(m_sens=m_sens, m_lat=m_lat, lam=lam)


def describe(m, m_start, m_floor, room, qs, moisture, min_w, min_adp, p_kpa, approach, chw_in, mode, exist):
    """Record how the airflow was determined, for the quality gate and the report."""
    cp = 1.006 + 1.86 * max(0.0, room["w"] - moisture / m) if m > 0 else 1.006
    supply_dt = qs / (m * cp) if m > 0 else 0.0
    inflation = m / m_start if m_start > 0 else 1.0
    searched = m > m_start * (1 + 1e-9)
    margin_w = room["w"] - min_w
    dp = dewpoint(room["w"], p_kpa)
    if searched:
        latent_bound = exist["m_lat"] > 0 and m >= exist["m_lat"] * (1 - 1e-6)
        governing = "除濕條件（冰水 ADP 過高）" if latent_bound else "盤管供水 ADP 條件（顯熱）"
    elif mode == "circulation":
        governing = "循環風量／外氣下限"
    else:
        parts = {"循環風量／外氣下限": m_floor, "顯熱設計風量": abs(qs) / DESIGN_SUPPLY_DT_K, "產濕設計風量": moisture / 0.002}
        governing = max(parts, key=parts.get)
    kappa = room["w"] / margin_w if searched and exist["m_lat"] > 0 and margin_w > 0 else None
    # Chilled-water supply at which BOTH engineering criteria hold, so the advice cannot land on the failing side of
    # either: inflation <= INFLATION_FAIL, and condition number <= CONDITION_FAIL.
    candidates = [dewpoint(room["w"] * (1.0 - 1.0 / CONDITION_FAIL), p_kpa) - approach]
    if moisture > 0 and m_start > 0:
        w_need = room["w"] - moisture / (m_start * INFLATION_FAIL)
        if w_need > 0:
            candidates.append(dewpoint(w_need, p_kpa) - approach)
    needed_chw = min(candidates)
    return dict(
        applicable=True, governing=governing, load_driven=searched,
        m_kg_s=m, m_start_kg_s=m_start, m_floor_kg_s=m_floor, m_sensible_min_kg_s=exist["m_sens"], m_moisture_min_kg_s=exist["m_lat"],
        inflation=inflation, supply_dt_k=supply_dt, dehumid_margin_w=margin_w, dehumid_margin_k=dp - min_adp,
        room_dewpoint_c=dp, adp_floor_c=min_adp, chw_supply_c=chw_in, approach_k=approach,
        condition_number=kappa, chw_needed_c=needed_chw,
        limits=dict(inflation_fail=INFLATION_FAIL, inflation_warn=INFLATION_WARN, min_supply_dt_k=MIN_PRACTICAL_SUPPLY_DT_K, condition_fail=CONDITION_FAIL),
    )


def not_applicable(reason):
    return dict(applicable=False, governing=reason, load_driven=False)
