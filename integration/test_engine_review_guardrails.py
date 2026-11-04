"""Regression guardrails from the 2026-11-04 independent engineering review.

Run each source tree in a separate process with FACILITY_TEST_PLATFORM. No
mocked physics: humidity and pumping references below are independent equations.
"""
import math
import os
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / os.environ.get("FACILITY_TEST_PLATFORM", "macos")))
from facility_studio import i18n
from facility_studio.ahu_engine import nm_calculate, nm_validate
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.design_workflow import ahu_utility_preview
from facility_studio.errors import ValidationError
from facility_studio.field_state import ahu_inactive
from facility_studio.reports import nm_report
from facility_studio.schema import default_project
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_reports import tool_report
from facility_studio.simple_schema import defaults


def humidity(t, rh):
    k = t + 273.15
    ps = math.exp(-5800.2206 / k + 1.3914993 - .048640239 * k
                  + .000041764768 * k**2 - .000000014452093 * k**3
                  + 6.5459673 * math.log(k))
    pv = ps * rh / 100
    return .621945 * pv / (101325 - pv)


@pytest.mark.parametrize("isolated", [False, True])
def test_infeasible_bf_is_not_an_achievable_demand_point(isolated):
    d = dict(NM_DEFAULTS, c2_bf_min=".25")
    if isolated:
        d.update(c2_rt="40", winter_t="16", winter_rh="90")
    wi, wt, wa = humidity(35, 70), humidity(16, 90), humidity(8, 100)
    assert (wt - wa) / (wi - wa) == pytest.approx(.192118041, abs=1e-9)
    assert .25 * wi + .75 * wa > wt
    r = nm_calculate(d)
    c = r["summer"]["c2"]
    assert not c["feasible_adp"] and c["path"] == "infeasible"
    assert c["adp_req_c"] is None and c["bf_req"] is None
    assert not r["summer"]["checks"]["C2 可達 ADP"]
    assert r["quality"]["status"] == "未達條件"
    finding = next(q for q in r["quality"]["items"] if q["name"] == "夏季 C2 可達 ADP")
    assert finding["status"] == "未達" and c["reason"] in finding["detail"]
    assert finding["field"] == "c2_bf_min"
    assert any("不可達需求點" in label for label, _ in r["summer"]["nodes"])
    before = i18n.language()
    try:
        for lang in ("zh-Hant", "en"):
            i18n.set_language(lang, persist=False)
            text = str(nm_report(r))
            assert i18n.translate(c["reason"], lang) in text
            assert i18n.translate("C2 再冷（不可達需求點）", lang) in text
            if lang == "en":
                assert "not attainable outlet conditions" in text
                assert not re.search(r"[\u3400-\u9fff]", i18n.translate(finding["detail"], lang))
    finally:
        i18n.set_language(before, persist=False)


def test_legacy_automatic_path_keeps_same_solver_failure_and_reason():
    d = dict(NM_DEFAULTS, c2_bf_min=".25", c2_rt="40", winter_t="16", winter_rh="90",
             humidifier="循環水洗濕膜", h1_source="熱水＋電熱", h2_source="熱水＋電熱",
             wash_mode="旁通／停用", pump_air_fraction="0", c1_t="35")
    for season in ("summer", "winter"):
        for tag in ("h1", "c1", "c2", "h2"):
            d[f"{season}_{tag}_mode"] = "自動需求"
    r = nm_calculate(d)
    assert r["summer"]["control_basis"] == "自動目標需求"
    assert not r["summer"]["checks"]["C2 可達 ADP"]
    assert r["summer"]["c2"]["path"] == "infeasible"
    assert r["summer"]["c2"]["reason"]


@pytest.mark.parametrize("bf", [".05", ""])
def test_feasible_and_missing_bf_cases_remain_distinct(bf):
    r = nm_calculate(dict(NM_DEFAULTS, summer_rh="40", c2_bf_min=bf))
    assert r["summer"]["c2"]["feasible_adp"]
    assert r["summer"]["checks"]["C2 可達 ADP"]
    assert not any("不可達需求點" in label for label, _ in r["summer"]["nodes"])
    if not bf:
        assert any(q["status"] == "待資料" and "BF" in q["detail"] for q in r["quality"]["items"])


def test_reheat_required_is_a_heater_failure_not_a_coil_failure():
    r = nm_calculate(dict(NM_DEFAULTS, summer_rh="40", sa_t="24", sa_rh="50", c2_bf_min=".05", summer_h2_mode="自動需求"))
    c = r["summer"]["c2"]
    assert c["path"] == "reheat_required" and c["feasible_adp"]
    assert not c["achievable_without_reheat"]
    assert r["summer"]["checks"]["C2 可達 ADP"]
    assert not r["summer"]["checks"]["H2 當前熱源情境"]


@pytest.mark.parametrize("flow,p,unit,bore", [
    ("60000", "150", "Torr(abs)", "200"),
    ("60000", "150", "Torr(abs)", "500"),
    (".3", "2", "Pa(abs)", "200"),
    (".001", ".01", "Pa(abs)", "200"),
])
def test_pump_speed_upper_bound_is_checked_in_every_regime(flow, p, unit, bore):
    d = dict(defaults("vacuum"), flow=flow, vacuum_p=p, vacuum_unit=unit,
             diameter_mode="指定內徑", inner_mm=bore, velocity="30")
    r = calculate_tool("vacuum", d)
    expected = float(flow) / 60 * 101325 / r["pressure_pa"] * 293.15 / 273.15
    assert r["required_speed_l_s"] == pytest.approx(expected, rel=1e-12)
    assert expected > r["pump_speed_l_s"]
    messages = [w for w in r["failures"] if "無法維持" in w]
    assert len(messages) == 1 and "泵入口" in messages[0]
    assert sum("無法維持" in w for w in r["warnings"]) == 1
    assert messages[0] in tool_report(r, d)
    assert not re.search(r"[\u3400-\u9fff]", i18n.translate(messages[0], "en"))
    if bore == "500" or p == "2":
        assert r["velocity_mps"] < 30
        assert r["effective_speed_l_s"] is None


def test_molecular_pipe_limit_and_pump_limit_are_separate():
    d = dict(defaults("vacuum"), flow=".0001", vacuum_p=".01", vacuum_unit="Pa(abs)",
             diameter_mode="指定內徑", inner_mm="50", velocity="30", pump_l_s="100")
    r = calculate_tool("vacuum", d)
    assert r["effective_speed_l_s"] < r["required_speed_l_s"] < r["pump_speed_l_s"]
    assert any("管路有效抽速" in w for w in r["failures"])
    assert not any("泵入口抽速" in w for w in r["failures"])


@pytest.mark.parametrize("flow", ["0", "1"])
def test_low_demand_does_not_claim_a_pump_failure_or_system_approval(flow):
    d = dict(defaults("vacuum"), flow=flow, diameter_mode="指定內徑", inner_mm="500")
    r = calculate_tool("vacuum", d)
    assert not r["failures"]
    assert r["effective_speed_l_s"] is None
    assert "需適用模型" in tool_report(r, d)


@pytest.mark.parametrize("flow_unit,factor", [("SLPM", 1), ("SCFM", 28.316846592), ("Sm³/h", 1000/60)])
@pytest.mark.parametrize("p_unit,factor_p", [("Pa(abs)", 1), ("Torr(abs)", 101325/760), ("kPa(abs)", 1000), ("mbar(abs)", 100)])
def test_vacuum_units_preserve_gas_load_and_failure(flow_unit, factor, p_unit, factor_p):
    d = dict(defaults("vacuum"), flow=str(60000/factor), flow_unit=flow_unit,
             vacuum_p=str((150*101325/760)/factor_p), vacuum_unit=p_unit,
             diameter_mode="指定內徑", inner_mm="500", velocity="30")
    r = calculate_tool("vacuum", d)
    assert r["required_speed_l_s"] == pytest.approx(5437.647202391849, rel=1e-12)
    assert any("泵入口抽速" in w for w in r["failures"])


@pytest.mark.parametrize("mode", ["不加濕", "電極式蒸汽", "電熱式蒸汽"])
@pytest.mark.parametrize("draft", ["draft", "-1", "2", "NaN"])
def test_inactive_washer_fraction_retains_draft_and_revalidates_when_enabled(mode, draft):
    d = dict(NM_DEFAULTS, humidifier=mode, pump_air_fraction=draft, winter_t="16", winter_rh="90")
    assert "pump_air_fraction" in ahu_inactive(d)
    r = nm_calculate(d)
    assert r["raw_inputs"]["pump_air_fraction"] == draft
    assert r["inputs"]["pump_air_fraction"] == NM_DEFAULTS["pump_air_fraction"]
    assert all(r[s]["washer_pump_heat_kw"] == 0 for s in ("summer", "winter"))
    with pytest.raises(ValidationError) as error:
        nm_validate(dict(d, humidifier="循環水洗濕膜"))
    assert error.value.field_name == "pump_air_fraction"


def test_bypassed_selected_washer_keeps_rated_capacity():
    r = nm_calculate(dict(NM_DEFAULTS, humidifier="循環水洗濕膜", wash_mode="旁通／停用",
                          pump_input_kw="5", pump_air_fraction="0"))
    assert all(r[s]["washer_pump_input_kw"] == 0 for s in ("summer", "winter"))
    assert r["active_installed_electric_kw"] == r["fan_installed_kw"] + 5
    assert float(ahu_utility_preview(r, default_project()["inputs"])["updates"]["e_np_pump"]) == 5


@pytest.mark.parametrize("kind,fan,fan_unit,pump,pump_unit,largest", [
    ("一般負載", "10", "HP", "0", "kW", "10"),
    ("一般負載", "5", "HP", "10", "HP", "10"),
    ("一般負載", "10", "HP", "2", "kW", "0"),
    ("連續負載", "10", "HP", "2", "kW", "draft"),
    ("馬達負載", "10", "kW", "2", "kW", "10"),
    ("一般負載", "10", "kW", "2", "kW", "draft"),
])
@pytest.mark.parametrize("floor", ["0", "100"])
def test_np_auto_preserves_motor_composition_and_design_floor(kind, fan, fan_unit, pump, pump_unit, largest, floor):
    import copy
    from facility_studio.engine import calculate, electrical_from_inputs
    from facility_studio.reports import report
    p = default_project()
    p["inputs"].update(np_auto_mode="自動加總本案（手填為額外負荷）", e_np_fan=fan,
                       u_e_np_fan=fan_unit, e_np_pump=pump, u_e_np_pump=pump_unit,
                       e_np_heat="3", u_e_np_heat="kW", e_np_type=kind,
                       e_np_largest_hp=largest, e_np_design_floor=floor)
    original = copy.deepcopy(p)
    manual = electrical_from_inputs(p["inputs"])["NP"]
    r = calculate(p)
    combined, auto = r["electric"]["NP"], r["np_auto"]
    extra_a = auto["total_kw"] * 1000 / (math.sqrt(3) * manual["voltage"] * manual["pf"])
    expected = manual["design_current_a"] + 1.25 * extra_a
    assert combined["kw"] == pytest.approx(manual["kw"] + auto["total_kw"], rel=1e-12)
    assert combined["current_a"] == pytest.approx(manual["current_a"] + extra_a, rel=1e-12)
    assert combined["design_current_a"] == pytest.approx(expected, rel=1e-12)
    assert combined["has_motor"] is manual["has_motor"]
    assert combined["hp"] == manual["hp"] and combined["largest_hp"] == manual["largest_hp"]
    assert auto["manual_motor_basis"]["hp"] == manual["hp"]
    assert auto["manual_motor_basis"]["largest_hp"] == manual["largest_hp"]
    assert auto["design_current_floor_a"] == pytest.approx(expected, rel=1e-12)
    assert p == original
    # Compare selection at the same independently reconstructed required current.
    old_style = dict(p["inputs"])
    for part in ("fan", "heat", "humid", "exh", "pump"):
        old_style[f"e_np_{part}"], old_style[f"u_e_np_{part}"] = "0", "kW"
    old_style.update(e_np_fan=str(combined["kw"]), e_np_largest_hp="0",
                     e_np_type="一般負載", e_np_design_floor=str(expected))
    at_floor = electrical_from_inputs(old_style)["NP"]
    assert combined["selected"] == at_floor["selected"]
    assert combined["candidate_count"] == at_floor["candidate_count"]
    before = i18n.language()
    try:
        for language in ("zh-Hant", "en"):
            i18n.set_language(language, persist=False)
            text = str(report(r))
            assert i18n.translate("NP 自動加總保留手動馬達 ", language) in text
            assert f"{expected:.3f}" in text
    finally:
        i18n.set_language(before, persist=False)


def test_np_auto_does_not_expand_the_manual_largest_motor_limit():
    from facility_studio.engine import calculate
    p = default_project()
    p["inputs"].update(np_auto_mode="自動加總本案（手填為額外負荷）", e_np_fan="10",
                       u_e_np_fan="HP", e_np_type="一般負載", e_np_largest_hp="11")
    with pytest.raises(ValidationError) as error:
        calculate(p)
    assert error.value.field_name == "e_np_largest_hp"
