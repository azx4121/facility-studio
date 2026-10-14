"""Room-basis airflow bookkeeping; capacities are not operating flows."""

import math
from .errors import InputError


def oa_requirements(inputs, leakage_cmh, exhaust_cmh, people):
    n = lambda key: float(inputs[key])
    target_outflow = leakage_cmh + n("prd_q")
    personnel = people * n("oa_per_person")
    base = max(exhaust_cmh + target_outflow, personnel)
    design = max(exhaust_cmh + target_outflow + n("oa_future_cmh"), personnel)
    design *= 1 + n("oa_reserve_pct") / 100
    return dict(
        exhaust_cmh=exhaust_cmh,
        target_leakage_cmh=leakage_cmh,
        target_relief_cmh=n("prd_q"),
        target_outflow_cmh=target_outflow,
        personnel_cmh=personnel,
        minimum_cmh=base,
        future_cmh=n("oa_future_cmh"),
        reserve_pct=n("oa_reserve_pct"),
        design_minimum_cmh=design,
        capacity_cmh=n("oa_capacity_cmh"),
    )


def ffu_requirements(inputs, zones, operating_oa_cmh, design_oa_cmh):
    requested = sum(zone["cmh"] for zone in zones.values())
    return_basis = inputs["ffu_flow_basis"] == "回風循環（外氣另加）"
    if return_basis and any(
        zone["area"] > 0 and inputs["mode_" + name] != "ACH"
        for name, zone in zones.items()
    ):
        raise InputError(
            "截面風速是 FFU 送風需求，請採總送風基準；回風循環基準只適用 ACH。",
            field_name="ffu_flow_basis",
        )
    through_ffu = inputs["ffu_oa_route"] == "外氣經 FFU"
    # An unknown capacity remains unknown. Future demand can still be sized,
    # but must not be represented as observed MAU capability.
    sizing_oa = max(operating_oa_cmh, design_oa_cmh, float(inputs["oa_capacity_cmh"]))
    oa_design = sizing_oa if through_ffu else 0.0
    oa_operating = operating_oa_cmh if through_ffu else 0.0
    supply = requested + oa_design if return_basis else max(requested, oa_design)
    return dict(
        basis=inputs["ffu_flow_basis"],
        route=inputs["ffu_oa_route"],
        requested_cmh=requested,
        sizing_oa_cmh=sizing_oa,
        oa_through_design_cmh=oa_design,
        oa_through_operating_cmh=oa_operating,
        supply_cmh=supply,
        return_cmh=max(0.0, supply - oa_design),
        operating_return_cmh=max(0.0, supply - oa_operating),
        room_supply_cmh=supply + (0.0 if through_ffu else operating_oa_cmh),
        count=math.ceil(supply / float(inputs["ffu_cmh"]) - 1e-12),
    )
