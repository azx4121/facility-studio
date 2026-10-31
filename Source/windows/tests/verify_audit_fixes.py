"""Independent verification suite for all 6 cross-reviewed FEED fixes."""

import copy
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from facility_studio import api as a
from facility_studio.ahu_engine import nm_calculate
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.contributions import (
    aggregate_ledger,
    ahu_contribution,
    empty_ledger,
    removed_ledger,
    updated_ledger,
)
from facility_studio.engine import calculate, condition_air, solve_c2_bypass
from facility_studio.errors import InputError
from facility_studio.gas_catalog import evaluate_gas_phase
from facility_studio.quality import _coil_pinch_and_enthalpy_ok
from facility_studio.reports import executive_summary, nm_report, report
from facility_studio.schema import default_project
from facility_studio.services import upstream_values
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_schema import defaults
from facility_studio.utils import VOLTAGE_MAP, dewpoint, state_trh, state_tw
from facility_studio.workspace_store import new_workspace


def test_point1_coil_adp_and_reheat():
    # Gemini A-1 case: inlet 22.192°C / 50.86% RH, supply 12.208°C / 8.184 g/kg, a2 = 8°C
    p_kpa = 101.325
    enter = state_trh(22.192, 50.86, p_kpa)
    ts = 12.208
    ws = 0.008184

    base_inputs = default_project()["inputs"]
    base_inputs.update(
        pre_mode="單盤管（一般空調箱）",
        chw2_in="6",
        coil_approach="2",  # a2 = 8.0°C
        allow_humidify="1",
    )

    # Both allow_reheat="1" and allow_reheat="0" must take the direct path (reheat_kw == 0)
    for allow_rh in ("1", "0"):
        inp = dict(base_inputs, allow_reheat=allow_rh)
        res = condition_air(inp, enter, 6.0447673, ts, ws)
        assert abs(res["c2"]["outlet"]["t"] - ts) < 1e-6, res["c2"]["outlet"]
        assert abs(res["reheat_kw"]) < 1e-6, f"allow_reheat={allow_rh} produced reheat={res['reheat_kw']}"
        assert res["c2"]["achievable_without_reheat"] is True
        # Required ADP_req ~ 10.97°C and BF_req ~ 0.110 (not a2=8.0°C)
        assert abs(res["c2"]["adp_req_c"] - 10.9735) < 0.02, res["c2"]["adp_req_c"]
        assert abs(res["c2"]["bf_req"] - 0.1100) < 0.003, res["c2"]["bf_req"]

    # When a2 = 13.0°C (> required dewpoint 11.016°C), must reject with InputError
    infeasible_inp = dict(base_inputs, chw2_in="11", coil_approach="2", allow_reheat="0")
    try:
        condition_air(infeasible_inp, enter, 6.0447673, ts, ws)
    except InputError as exc:
        assert exc.field_name == "chw2_in"
    else:
        raise AssertionError("Expected InputError when a2=13°C exceeds dewpoint(ws)=11.02°C")

    # When target ts is practically on saturation curve (BF_req -> 0 < bf_min=0.02),
    # no outlet with BF >= 0.02 is that cold: reheat cannot help, and saturating the
    # coil (BF = 0) to bypass the stated floor is not an admissible answer.
    tdp = dewpoint(ws, p_kpa)
    try:
        solve_c2_bypass(enter, tdp + 0.001, ws, 8.0, p_kpa, allow_reheat="1", bf_min=0.02)
    except InputError as exc:
        assert "再熱無法解決" in str(exc), exc
    else:
        raise AssertionError("Expected no admissible coil path below the BF=0.02 outlet")
    near_sat_sol = solve_c2_bypass(enter, tdp + 0.001, ws, 8.0, p_kpa, allow_reheat="1", bf_min=0.02, raise_on_infeasible=False)
    assert near_sat_sol["achievable_without_reheat"] is False and near_sat_sol["path"] == "infeasible"

    # Verify ahu_engine.py (nm_calculate) also solves direct path without reheat when feasible
    nm_inp = dict(
        NM_DEFAULTS,
        summer_t="22.192",
        summer_rh="50.86",
        sa_t="12.208",
        sa_rh=str(state_tw(12.208, ws, p_kpa)["rh"]),
        fan_air_kw="0",
        summer_c1_mode="旁通",
        summer_h1_mode="旁通",
        summer_c2_mode="自動需求",
        summer_h2_mode="自動需求",
        wash_mode="停用",
        c2_in="6",
        c2_out="12",
        c2_adp="2",
    )
    nm_res = nm_calculate(nm_inp)
    assert abs(nm_res["summer"]["h2"]["air_kw"]) < 1e-5, nm_res["summer"]["h2"]
    assert abs(nm_res["summer"]["c2"]["adp_req_c"] - 10.9735) < 0.02
    assert abs(nm_res["summer"]["c2"]["bf_req"] - 0.1100) < 0.003
    assert "所需 ADP" in nm_report(nm_res)


def test_point2_pinch_and_wet_enthalpy():
    p_kpa = 101.325
    # 1. GPT counterexample: equal heat capacity counterflow dry/sensible coil
    # Air: 35°C -> 15°C (w = 6 g/kg, Tdp = 6.5°C so dry or sensible cooling)
    # Water: 2°C -> 22°C (dt = 20 K > 15 K), cold pinch = 15 - 2 = 13 K, hot pinch = 35 - 22 = 13 K
    s_in = state_tw(35.0, 0.006, p_kpa)
    s_out = state_tw(15.0, 0.006, p_kpa)
    coil_gpt = {
        "inlet": s_in,
        "outlet": s_out,
        "air_kw": 20.0,
        "water_kw": 20.0,
        "condensate_kg_s": 0.0,
    }
    ok_gpt = _coil_pinch_and_enthalpy_ok(coil_gpt, tin_w=2.0, tout_w=22.0, p_kpa=p_kpa)
    assert ok_gpt is True, "GPT 20 K counterexample should pass"

    # 2. Gemini A-2 counterexample: MAU Summer C1 air 35°C/70%RH (h=99.66 kJ/kg) -> 19°C/100%RH,
    # Water: 7°C -> 34.5°C (dt = 27.5 K). At hot end, h_sat(34.5°C) = 126.1 kJ/kg > h_a,in = 99.66 kJ/kg
    proj = default_project()
    proj["inputs"].update(pre_mode="自動旁通因子估算", pre_t="19", chw1_in="7", chw1_dt="27.5")
    res_a2 = calculate(proj)
    q_items = {item["name"]: item for item in res_a2["quality"]["items"]}
    assert q_items["夏季一段盤管 回水必要條件"]["status"] == "未達", q_items["夏季一段盤管 回水必要條件"]
    assert res_a2["quality"]["status"] == "未達條件"


def test_point3_winter_ffu_and_terminal_heating():
    proj = default_project()
    proj["inputs"].update(
        sys_type="MAU+FFU+DCC (全外氣/無塵室)",
        winter_model="室內熱濕平衡（定風量）",
        winter_gain_ratio="0",
        winter_ffu_ratio="100",
        winter_mau_max_t="40",
        ffu_w="150",
        ow_t="-15",
        en_wall="2500",
        wall_u="1.8",
        allow_reheat="1",
        allow_humidify="1",
    )
    res = calculate(proj)
    wr = res["winter_room"]
    # 1. FFU heat is 100% retained in winter even when winter_gain_ratio == 0%
    assert wr["fan_retained_kw"] > 0.0
    # 2. Heavy envelope loss caps MAU supply_t at 40°C and routes remaining loss to terminal_heat_kw
    assert wr["mau_temp_capped"] is True
    assert abs(wr["supply_t"] - 40.0) < 1e-6
    assert wr["terminal_heat_kw"] > 0.0
    # 3. Sensible energy balance closes with zero residual
    assert abs(wr["sensible_residual_kw"]) < 1e-6
    # 4. No heat source is assigned, so the remaining loss is an unassigned demand:
    #    it stays out of the HW design load and is not claimed for HW or NP.
    assert wr["terminal_heat_source"] is None
    expected_hw = max(res["summer"]["reheat_kw"], res["winter"]["reheat_kw"]) * res["sf"]
    assert abs(res["water"]["HW"]["load_kw"] - expected_hw) < 1e-4
    assert any("未配置室內加熱需求" in w for w in res["warnings"])
    assert not any("已轉列室內加熱需求並計入 HW" in w for w in res["warnings"])
    assert "室內加熱需求" in report(res)


def test_point4_gas_liquefaction_and_critical_t():
    # 1. CO2 at 35°C (> Tc = 31.0°C) is supercritical, not extrapolated liquid
    co2_35 = evaluate_gas_phase("CO2", 35.0, 6000.0)
    assert co2_35["status"] == "超臨界／高於臨界溫度", co2_35
    assert co2_35["liquefaction_risk"] is False

    # 2. WF6 at 20°C and 500 kPa abs (~5 bar > P_sat ~ 1.09 bar) flags liquefaction risk
    wf6 = evaluate_gas_phase("WF6", 20.0, 500.0)
    assert wf6["liquefaction_risk"] is True
    assert wf6["status"] == "液化或逼近飽和風險"

    # 3. Gas mixture / custom gas returns unknown and prompts partial-pressure check
    mix = evaluate_gas_phase("自訂／混合氣", 20.0, 500.0)
    assert mix["liquefaction_risk"] is None
    assert "分壓" in mix["status"]

    # 4. Out-of-range temperature returns unknown
    out_of_range = evaluate_gas_phase("NH3", 95.0, 500.0)
    assert out_of_range["liquefaction_risk"] is None
    assert "未知" in out_of_range["status"]

    # 5. Full project with WF6 at 400 kPaG triggers 待資料 warning in quality.py
    proj = default_project()
    proj["inputs"].update(gas1_type="WF6", gas1_q="50", gas_barg="5", gas_temp="20", gas1_v_mode="自訂流速", gas1_velocity="8")
    res = calculate(proj)
    q_names = {item["name"]: item["status"] for item in res["quality"]["items"]}
    assert q_names.get("特氣相態與液化檢核") == "待資料", q_names


def test_point5_ledger_motor_dedup_and_idempotence():
    p = default_project()
    # Base UP panel: 80 kW heater/general load + 20 kW motor (entered as HP with eff=1.0, pf=1.0) = 100 kW total base
    hp_for_20kw = 20.0 / 0.745699871582
    p["inputs"].update(
        e_eff="1.0",
        e_pf="1.0",
        e_up_oven="80",
        u_e_up_oven="kW",
        e_up_eq=str(hp_for_20kw),
        u_e_up_eq="HP",
        e_up_type="馬達負載",
    )
    # Imported source on UP: 0 kW (or 10 kW general load on e_up_oven? No, imported source on e_up_eq is summed with baseline!)
    # Let's test base 80 kW on e_up_oven + base 20 kW motor in d["baseline"]["e_up_eq"] or on NP panel:
    # Even simpler: on NP panel, base has e_np_exh = 20 kW motor (in HP), e_np_pump = 80 kW (in kW), total untouched base = 100 kW!
    p["inputs"].update(
        e_np_fan="0",
        u_e_np_fan="kW",
        e_np_heat="0",
        u_e_np_heat="kW",
        e_np_humid="0",
        u_e_np_humid="kW",
        e_np_pump="80",
        u_e_np_pump="kW",
        e_np_exh=str(hp_for_20kw),
        u_e_np_exh="HP",
        e_np_type="馬達負載",
    )
    # The 80 kW kW-entered row is also a motor on a motor panel; without a stated
    # largest motor the ledger may only assume the largest row (80 kW, pending).
    unknown = dict(p["inputs"])
    # Import an AHU source that only touches e_np_fan/heat/humid (with 0 kW so untouched base on NP is 80 + 20 = 100 kW!)
    zero_np_entry = {
        "id": "ahu-test",
        "name": "AHU-Test",
        "kind": "AHU",
        "source_hash": "hash1",
        "updates": {"e_np_fan": "0", "u_e_np_fan": "kW"},
        "water": [],
        "power": {
            "NP": {
                "kw": 0.0,
                "kvar": 0.0,
                "design_kw": 0.0,
                "design_kvar": 0.0,
                "branch_floor_a": 0.0,
                "length_m": 0.0,
                "voltage": VOLTAGE_MAP[p["inputs"]["e_volt"]],
            }
        },
        "notes": [],
        "pending": [],
    }
    _, unknown_updates, unknown_summary = updated_ledger(empty_ledger(), zero_np_entry, unknown)
    v = VOLTAGE_MAP[p["inputs"]["e_volt"]]
    assert abs(float(unknown_updates["e_np_design_floor"]) - 120.0 * 1000.0 / (math.sqrt(3) * v)) < 1e-4
    assert any("最大單台馬達未填" in x for x in unknown_summary["pending"])
    p["inputs"]["e_np_largest_hp"] = str(hp_for_20kw)
    d1, updates1, _ = updated_ledger(empty_ledger(), zero_np_entry, p["inputs"])
    p["inputs"].update(updates1)
    assert d1["original"]["e_np_type"] == "馬達負載"
    # Verify design_floor corresponds to 100 kW + 0.25 * 20 kW = 105 kW (NOT 125 kW!)
    v = VOLTAGE_MAP[p["inputs"]["e_volt"]]
    expected_105_a = 105.0 * 1000.0 / (math.sqrt(3) * v)
    actual_floor_a = float(p["inputs"]["e_np_design_floor"])
    assert abs(actual_floor_a - expected_105_a) < 1e-4, (actual_floor_a, expected_105_a)

    # Repeat import of the exact same source must produce zero drift
    r1 = calculate(p)
    design_a_1 = r1["electric"]["NP"]["design_current_a"]
    d2, updates2, _ = updated_ledger(d1, zero_np_entry, p["inputs"])
    p["inputs"].update(updates2)
    r2 = calculate(p)
    assert abs(r2["electric"]["NP"]["design_current_a"] - design_a_1) < 1e-9

    # Removing the source restores the original panel type and HP unit
    _, restored, _ = removed_ledger(d2, "ahu-test", p["inputs"])
    p["inputs"].update(restored)
    assert p["inputs"]["e_np_type"] == "馬達負載"
    assert p["inputs"]["u_e_np_exh"] == "HP"


def test_point6_coincident_chiller_and_consistency():
    proj = default_project()
    res = calculate(proj)
    expected_coincident = max(
        res["summer"]["coincident_cooling_kw"],
        res["winter"]["coincident_cooling_kw"],
    )
    assert abs(res["q_total_kw"] - expected_coincident) < 1e-6
    rows = {row["equipment"]: row for row in executive_summary(res)}
    chiller_row = rows["中央冰水主機 Chiller"]
    assert "夏冬同時峰值冷量" in chiller_row["demand"]
    assert "同時峰值容量目標" in chiller_row["selection"]

    # Check AHU return preserves source water properties when main project uses glycol
    ws = new_workspace(default_project())
    ws["main"]["inputs"].update(
        chw_fluid_mode="本迴路獨立物性",
        chw_rho="1050",
        chw_cp="3.60",
        chw_mu="0.0025",
    )
    ahu_res = nm_calculate(NM_DEFAULTS)
    entry = ahu_contribution(ahu_res, "ahu-1", ws["main"]["inputs"])
    _, _, summary = updated_ledger(empty_ledger(), entry, ws["main"]["inputs"])
    assert any("保留單機來源物性" in msg for msg in summary["pending"]), summary["pending"]

    # Check upstream_values("heat_loads") uses air_v_da when present
    air_res = calculate_tool("air", defaults("air"))
    air_res["air_v_da"] = 0.90
    up = upstream_values("heat_loads", {"air": air_res}, defaults("heat_loads"))
    hl_in = dict(defaults("heat_loads"), **up, air_v_da="0.90")
    hl_res = calculate_tool("heat_loads", hl_in)
    assert abs(hl_res["adopted_v_da"] - 0.90) < 1e-9


if __name__ == "__main__":
    test_point1_coil_adp_and_reheat()
    test_point2_pinch_and_wet_enthalpy()
    test_point3_winter_ffu_and_terminal_heating()
    test_point4_gas_liquefaction_and_critical_t()
    test_point5_ledger_motor_dedup_and_idempotence()
    test_point6_coincident_chiller_and_consistency()
    print("ALL 6 CROSS-REVIEWED FEED FIXES VERIFIED: PASS")
