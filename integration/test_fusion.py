"""Production-path assertions, physical balances and adversarial conditions."""
import copy
import json
from pathlib import Path
import sys
import warnings

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "macos"))
from facility_studio import engineering_backends as backend
from facility_studio.ahu_schema import NM_DEFAULTS, NM_V4_KEYS
from facility_studio.ahu_engine import nm_calculate, nm_read_project
from facility_studio.engine import calculate, coil_record
from facility_studio.schema import default_project
from facility_studio.utils import water_selection, state_trh, state_tw, darcy_factor
from facility_studio.quick_tools import convert_all, UNITS
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_schema import defaults
from facility_studio.reports import report, nm_report
from facility_studio.coil_rating import rate_coil


def test_actual_core_calls_all_five(monkeypatch):
    calls = {}
    for name in ("saturation_pressure", "moist_enthalpy", "moist_volume", "darcy_friction", "cooling_process", "liquid_water", "convert"):
        original = getattr(backend, name)
        def wrapper(*args, _name=name, _original=original, **kwargs):
            calls[_name] = calls.get(_name, 0) + 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(backend, name, wrapper)
    p = default_project()
    p["inputs"].update(chw_property_source="CoolProp 純水溫壓", chw_property_t="10", chw_property_p="300")
    result = calculate(p)
    assert set(calls) == {"saturation_pressure", "moist_enthalpy", "moist_volume", "darcy_friction", "cooling_process", "liquid_water", "convert"}
    assert set(result["engineering_backends"]) == {"PsychroLib", "python-hvac", "CoolProp", "fluids", "Pint"}
    assert all(name in report(result) for name in result["engineering_backends"])


@pytest.mark.parametrize("w", [0., 1e-12, 1e-8, .001, .01])
def test_exact_dry_limit_and_analytical_enthalpy(w):
    s = state_tw(30, w, 101.325)
    assert s["w"] == w
    assert s["h"] == pytest.approx(1.006 * 30 + w * (2501 + 1.86 * 30), abs=1e-12)
    assert s["v_da"] == pytest.approx(.287042 * 303.15 * (1 + w / .621945) / 101.325, rel=1e-12)


@settings(max_examples=100, derandomize=True, deadline=None, database=None)
@given(st.floats(4000, 1e8), st.floats(0, .02))
def test_colebrook_equation_independently(re, rough):
    import math
    f = darcy_factor(re, rough)
    residual = 1 / math.sqrt(f) + 2 * math.log10(rough / 3.7 + 2.51 / (re * math.sqrt(f)))
    assert abs(residual) < 1e-9


def test_process_condensate_control_volume():
    a, b = state_trh(30, 70, 101.325), state_trh(12, 95, 101.325)
    r = coil_record("合成盤管", a, b, 2., 1.)
    cond = 2 * (a["w"] - b["w"])
    assert r["condensate_kg_s"] == pytest.approx(cond)
    assert r["water_kw"] == pytest.approx(2 * (a["h"] - b["h"]) - cond * 4.1868 * 12)
    assert r["air_kw"] == pytest.approx(r["water_kw"] + r["liquid_kw"])


@pytest.mark.parametrize("group", list(UNITS))
def test_production_units_preserve_explicit_definitions(group):
    units = UNITS[group]
    if group == "溫度":
        assert convert_all(group, 0, "°C")["°F"] == pytest.approx(32)
    else:
        source = next(iter(units))
        result = convert_all(group, 1., source)
        for target, factor in units.items():
            assert result[target] == pytest.approx(units[source] / factor, rel=1e-10, abs=1e-10)
    assert convert_all("溫度差（升溫／降溫）", 5, "°C差")["°F差"] == pytest.approx(9)


@pytest.mark.parametrize("t", [5., 10., 40., 80.])
def test_water_properties_are_used_for_thermal_and_pressure(t):
    data = defaults("water")
    data.update(property_source="CoolProp 純水溫壓", water_t=str(t), water_p="300")
    r = calculate_tool("water", data)
    props = r["fluid_properties"]
    assert r["load_kw"] == pytest.approx(100 / 60000 * props["rho"] * props["cp"] * 5)
    assert r["pressure"]["head_m"] == pytest.approx(r["pressure"]["loss_pa"] / props["rho"] / 9.80665)
    assert "HEOS" in r["note"]


def test_vapor_water_rejected():
    data = defaults("water")
    data.update(property_source="CoolProp 純水溫壓", water_t="150", water_p="101.325")
    with pytest.raises(ValueError, match="單相液態"):
        calculate_tool("water", data)


@pytest.mark.parametrize("key", ["water_t", "water_p"])
def test_water_validation_identifies_the_actual_field(key):
    from facility_studio.errors import ValidationError
    data = defaults("water")
    data.update(property_source="CoolProp 純水溫壓", water_t="10", water_p="300")
    data[key] = "不是數字"
    with pytest.raises(ValidationError) as error:
        calculate_tool("water", data)
    assert error.value.field_name == key


def test_inactive_model_drafts_are_preserved_and_not_used():
    from facility_studio.errors import ValidationError
    p = default_project()
    p["inputs"].update(chw_property_source="沿用手動物性", chw_property_t="保留草稿", chw_property_p="另一草稿",
                       motor_input_efficiency="未用草稿", np_auto_mode="手動填列")
    before = copy.deepcopy(p)
    assert calculate(p)["water"]["CHW"]["fluid_properties"]["rho"] == 1000
    assert p == before
    p["inputs"]["chw_property_source"] = "CoolProp 純水溫壓"
    with pytest.raises(ValidationError) as error:
        calculate(p)
    assert error.value.field_name in ("chw_property_t", "chw_property_p")


def test_dual_sizing_corrects_audited_case_and_manual_warns():
    old = water_selection(221.75, 2.)
    new = water_selection(221.75, 2., max_friction_pa_m=350)
    assert old["id_mm"] == 52.5 and new["id_mm"] > old["id_mm"]
    assert not new["friction_limit_exceeded"]
    manual = water_selection(221.75, 2., manual_id=52.5, max_friction_pa_m=350)
    assert manual["friction_limit_exceeded"]
    p = default_project()
    p["inputs"].update(chw_link="獨立輸入", chw_q="221.75", water_friction_limit="350")
    r = calculate(p)
    assert r["pressure"]["CHW"]["high_friction_rate"]
    assert any(q["name"] == "CHW 摩擦壓損警戒" and q["status"] == "未達" for q in r["quality"]["items"])
    assert "摩擦壓損" in report(r)


def test_chiller_boundaries_and_safety_factor_not_repeated():
    p = default_project()
    p["inputs"].update(chw_link="獨立輸入", chw_q="2000")
    internal = calculate(p)
    assert internal["q_water_capacity_envelope_kw"] > internal["q_internal_peak_kw"]
    assert internal["q_total_kw"] == internal["q_internal_peak_kw"]
    p["inputs"]["chiller_capacity_basis"] = "獨立冷源水路包絡（確認無重複）"
    r = calculate(p)
    assert r["q_total_kw"] * r["sf"] == pytest.approx(r["q_water_capacity_envelope_kw"])
    assert "水路供冷容量包絡" in report(r)


def test_np_auto_is_deterministic_nonmutating_and_not_shaft_kw():
    p = default_project()
    base = calculate(p)["electric"]["NP"]["kw"]
    p["inputs"].update(np_auto_mode="自動加總本案（手填為額外負荷）", main_fan_input_kw="3",
                       ffu_input_w="80", main_reheat_source="電熱", main_humidifier_input_kw="10",
                       motor_input_efficiency="0.8")
    before = copy.deepcopy(p)
    r, again = calculate(p), calculate(p)
    assert p == before and r["electric"] == again["electric"]
    assert r["electric"]["NP"]["kw"] == pytest.approx(base + r["np_auto"]["total_kw"])
    shaft = sum(d["shaft_kw"] for k, d in r["pressure"].items() if k in r["water"])
    assert r["np_auto"]["parts"]["pump"] == pytest.approx(shaft / .8)
    assert r["electric"]["NP"]["design_current_a"] >= 1.25 * r["electric"]["NP"]["current_a"] - 1e-7
    assert r["water"]["HW"]["load_kw"] == 0
    assert not any("尚未自動併入 NP" in warning for warning in r["warnings"])


@pytest.mark.parametrize("fraction", ["0", "0.25", "1"])
def test_washer_pump_electric_and_heat_balance(fraction):
    i = dict(NM_DEFAULTS, humidifier="循環水洗濕膜", wash_mode="只在需要加濕時",
             pump_input_kw="1.2", pump_air_fraction=fraction,
             h1_source="電熱", h2_source="電熱", summer_h1_mode="自動需求",
             winter_h1_mode="自動需求", summer_h2_mode="自動需求", winter_h2_mode="自動需求")
    r = nm_calculate(i)
    without = nm_calculate(dict(i, pump_input_kw="0"))
    assert r["active_installed_electric_kw"] == pytest.approx(without["active_installed_electric_kw"] + 1.2)
    for season in ("summer", "winter"):
        s = r[season]
        assert abs(s["energy_residual_kw"]) < 1e-5
        if s["wash_on"]:
            assert s["washer_pump_heat_kw"] == pytest.approx(1.2 * float(fraction))


def test_legacy_ahu_preserves_values_and_gets_new_editable_fields(tmp_path):
    legacy = {k: NM_DEFAULTS[k] for k in NM_V4_KEYS}
    file = tmp_path / "legacy.json"
    file.write_text(json.dumps(dict(kind="ahu_stage", schema_version=4, inputs=legacy)))
    migrated = nm_read_project(file)["inputs"]
    assert all(migrated[k] == v for k, v in legacy.items())
    assert migrated["c2_bf_min"] == "" and migrated["coil_rating_mode"] == "需求 ADP／BF"


def test_inactive_c1_cannot_block_a_complete_pressure_record():
    i = dict(NM_DEFAULTS, dp_status="已填完整同風量資料")
    for key in i:
        if key.startswith("dp_") and key != "dp_status":
            i[key] = "20"
    i["dp_c1"] = "保留未用草稿"
    r = nm_calculate(i)
    assert "dp_c1" in r["inactive_fields"]
    assert r["pressure_complete"]
    assert not any(q["name"] == "風機壓差完整度" for q in r["quality"]["items"])


def test_actual_geometric_coil_and_invalid_geometry():
    i = dict(NM_DEFAULTS)
    inlet = state_trh(26, 50, 101.325)
    with warnings.catch_warnings():
        original = list(warnings.filters)
        r = rate_coil(i, inlet, 850 / 3600 / inlet["v_da"])
        assert warnings.filters == original
    assert 4.5 < r["capacity_kw"] < 5.0
    assert 7 < r["outlet_t"] < 26 and 7 < r["water_outlet_t"] < 26
    assert r["air_dp_pa"] > 0 and r["water_dp_pa"] > 0
    assert abs(r["air_balance_residual_kw"]) < .001
    assert not r["warnings"]
    with pytest.raises(ValueError, match="內徑"):
        rate_coil(dict(i, coil_di="20"), inlet, .28)
    live = nm_calculate(dict(i, flow="850", summer_t="26", summer_rh="50",
                             sa_t="15", sa_rh="85", coil_rating_mode="幾何 ε-NTU（python-hvac）"))
    assert live["summer"]["coil_rating"]["capacity_pass"]
    assert "C2 ε-NTU" in nm_report(live)
