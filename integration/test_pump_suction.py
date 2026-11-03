import math
from pathlib import Path
import sys

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "macos"))
from facility_studio.simple_schema import defaults, active_field
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_reports import tool_report
from facility_studio.pump_suction import suction_check
from facility_studio.errors import ValidationError


def inputs(**kw):
    return dict(dict(defaults("liquid"), check_npsh="1", suction_surface_kpa="101.325",
                     suction_level_m="2", suction_loss_kpa="10", npshr_m="3",
                     pump_curve_reference="合成泵曲線 R1；100 LPM、1450 rpm",
                     npsh_margin_m="1", npsh_margin_reference="合成業主裕度要求 R1"), **kw)


def test_open_tank_matches_independent_hand_calculation_and_report():
    result = calculate_tool("liquid", inputs())
    check = result["suction"]
    # Standard tabulated water at 20 C: rho~998.2 kg/m3, Pv~2.339 kPa.
    independent = (101325 - 2339 - 10000) / (998.2 * 9.80665) + 2
    assert check["available_m"] == pytest.approx(independent, abs=.003)
    assert check["criterion_met"] and check["threshold_m"] == 4
    report = tool_report(result, inputs())
    assert "NPSHa" in report and "合成泵曲線 R1" in report and "液面" in report


def test_hot_water_has_lower_npsha_and_loss_is_not_discharge_route():
    cold = calculate_tool("liquid", inputs())["suction"]
    hot = calculate_tool("liquid", inputs(liquid_t="90"))["suction"]
    assert hot["available_m"] < cold["available_m"]
    short = calculate_tool("liquid", inputs(length="1"))["suction"]
    long = calculate_tool("liquid", inputs(length="1000"))["suction"]
    assert short["available_m"] == long["available_m"]


def test_unknown_curve_and_margin_never_pass():
    result = calculate_tool("liquid", inputs(npshr_m="", npsh_margin_m=""))["suction"]
    assert result["available_m"] > 0 and result["threshold_m"] is None
    assert not result["criterion_met"] and len(result["warnings"]) == 2


@pytest.mark.parametrize("key,value", [("suction_loss_kpa", ""), ("suction_loss_kpa", "-1"),
    ("check_npsh", "invalid"),
    ("pump_curve_reference", "invalid\x00reference"),
    ("npsh_margin_reference", "invalid\x00reference"),
    ("suction_surface_kpa", "0"), ("npshr_m", "nan"), ("npsh_margin_m", "inf"),
    ("pump_curve_reference", ""), ("npsh_margin_reference", "")])
def test_invalid_inputs_or_missing_sources_are_not_zero(key, value):
    with pytest.raises(ValidationError):
        calculate_tool("liquid", inputs(**{key: value}))


def test_low_pressure_and_large_suction_lift_are_not_accepted():
    for changes in [dict(suction_surface_kpa="1"), dict(suction_level_m="-20")]:
        result = calculate_tool("liquid", inputs(**changes))["suction"]
        assert not result["criterion_met"]
        assert any("單相" in w or "閃蒸" in w for w in result["warnings"])
        if "suction_level_m" in changes:
            assert result["available_m"] < 0


def test_positive_total_head_can_still_flash_at_high_velocity():
    result = suction_check(inputs(suction_level_m="0", suction_loss_kpa="0", npshr_m="0", npsh_margin_m="0"),
                           "清水", 20, 998.2, 20)
    assert result["available_m"] > 0 and result["suction_static_kpa"] < result["vapor_kpa"]
    assert not result["criterion_met"]


def test_mixture_requires_bubble_point_not_water_fallback():
    d = inputs(liquid="乙二醇水溶液")
    with pytest.raises(ValidationError):
        calculate_tool("liquid", d)
    d.update(vapor_pressure_kpa="1.7", vapor_reference="合成泡點資料 20°C、20wt%")
    result = calculate_tool("liquid", d)["suction"]
    assert result["vapor_kpa"] == 1.7


@given(st.floats(min_value=-5, max_value=10, allow_nan=False),
       st.floats(min_value=0, max_value=20, allow_nan=False))
@settings(max_examples=60, deadline=None)
def test_bernoulli_equivalence_with_suction_static_pressure(level, loss):
    check = suction_check(inputs(suction_level_m=str(level), suction_loss_kpa=str(loss)), "清水", 20, 998.2, 1.5)
    from_nozzle = ((check["suction_static_kpa"] - check["vapor_kpa"]) * 1000 / (998.2 * 9.80665)
                   + 1.5**2 / (2 * 9.80665))
    assert math.isclose(check["available_m"], from_nozzle, abs_tol=1e-10)


def test_disabled_optional_inputs_do_not_change_existing_result():
    d = dict(defaults("liquid"), suction_loss_kpa="invalid", npshr_m="invalid")
    assert calculate_tool("liquid", d)["suction"] is None
    assert not active_field("liquid", "suction_loss_kpa", d)
    d["check_npsh"] = "1"
    assert active_field("liquid", "suction_loss_kpa", d)
    assert not active_field("liquid", "vapor_pressure_kpa", d)


def test_nozzle_elevation_is_not_confused_with_npsh_datum():
    low = suction_check(inputs(suction_nozzle_offset_m="0"), "清水", 20, 998.2, 1.5)
    high = suction_check(inputs(suction_nozzle_offset_m="2"), "清水", 20, 998.2, 1.5)
    assert low["available_m"] == high["available_m"]
    assert low["suction_static_kpa"] - high["suction_static_kpa"] == pytest.approx(998.2 * 9.80665 * 2 / 1000)
    head_at_datum = ((high["suction_static_kpa"] - high["vapor_kpa"]) * 1000 / (998.2 * 9.80665)
                     + 1.5**2 / (2 * 9.80665) + 2)
    assert high["available_m"] == pytest.approx(head_at_datum)
