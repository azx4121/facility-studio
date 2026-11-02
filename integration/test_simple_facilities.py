import math
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "macos"))
from facility_studio.simple_schema import defaults
from facility_studio.simple_engines import calculate_tool
from facility_studio.facility_simple import MATERIALS, duct_sheet, insulation
from facility_studio.errors import ValidationError
from facility_studio.simple_reports import tool_report


def test_gemini_cleanroom_case_and_legacy_explicit_basis():
    d = dict(defaults('cleanroom'), oa_cmh='3000')
    r = calculate_tool('cleanroom', d)
    assert (r['ffu_total_cmh'], r['dcc_cmh'], r['ffu_count']) == (18000, 15000, 18)
    assert r['relief_required_cmh'] == 2700
    assert r['total_supply_ach'] == 60
    assert abs(r['airflow_balance_residual_cmh']) < 1e-10
    old = calculate_tool('cleanroom', dict(d, ffu_airflow_basis='室內基本循環（另加OA）'))
    assert old['ffu_total_cmh'] == 21000 and old['dcc_cmh'] == 18000
    assert old['total_supply_ach'] == 70
    assert '2,700' in tool_report(r, d)


@given(st.floats(min_value=300, max_value=17000, allow_nan=False))
@settings(max_examples=100, deadline=None)
def test_total_supply_is_not_double_counted(oa):
    r = calculate_tool('cleanroom', dict(defaults('cleanroom'), oa_cmh=str(oa)))
    assert r['ffu_total_cmh'] == 18000
    assert math.isclose(r['dcc_cmh'] + r['oa_cmh'], 18000, abs_tol=1e-8)
    assert abs(r['airflow_balance_residual_cmh']) < 1e-9


@pytest.mark.parametrize('material', MATERIALS)
def test_materials_are_explicit_and_never_approve_chemical_compatibility(material):
    r = calculate_tool('liquid', dict(defaults('liquid'), material=material))
    assert r['material'] == material and not r['material_approved']
    assert r['inner_mm'] == pytest.approx(r['outer_mm'] - 2*r['wall_mm'])
    assert r['rho'] > 990 and r['material_source'].startswith('https://')


@pytest.mark.parametrize('name', ['乙二醇水溶液', '丙二醇水溶液', '乙醇', '甲醇'])
def test_fluid_change_drives_actual_properties(name):
    r = calculate_tool('liquid', dict(defaults('liquid'), liquid=name))
    water = calculate_tool('liquid', defaults('liquid'))
    assert r['rho'] != water['rho'] and r['mu'] != water['mu']
    assert r['friction_pa_m'] != water['friction_pa_m']


@pytest.mark.parametrize('name', ['丙酮','IPA 異丙醇','污水／混合廢液','鹽酸','硫酸','氫氟酸','氫氧化鈉','過氧化氫','自訂液體'])
def test_unknown_chemical_properties_cannot_fall_back_to_water(name):
    d = dict(defaults('liquid'), liquid=name)
    with pytest.raises(ValidationError):
        calculate_tool('liquid', d)
    d.update(liquid_rho='1100', liquid_cp='3.7', liquid_mu='.003', property_reference='合成供應商數據；20°C、20wt%')
    r = calculate_tool('liquid', d)
    assert r['rho'] == 1100 and r['mu'] == .003
    assert not r['material_approved']


def test_small_pipe_and_high_pressure_loss_warn_in_same_form():
    d = dict(defaults('liquid'), geometry='指定外徑及管壁', outer_mm='16', wall_mm='2', flow='100')
    r = calculate_tool('liquid', d)
    assert r['velocity_mps'] > 10
    assert any('流速' in w for w in r['warnings'])
    assert any('壓損' in w for w in r['warnings'])
    with pytest.raises(ValidationError):
        calculate_tool('liquid', dict(d, wall_mm='8'))


def test_inactive_drafts_do_not_poison_liquid_calculation():
    d = dict(defaults('liquid'), liquid_rho='bad', concentration='bad', outer_mm='bad', wall_mm='bad')
    assert calculate_tool('liquid', d)['rho'] > 0
    d.update(geometry='指定外徑及管壁', outer_mm='25', wall_mm='2', sdr='bad')
    assert calculate_tool('liquid', d)['inner_mm'] == 21


@pytest.mark.parametrize('edge,mm,gauge', [(460,.6,'#24'),(461,.8,'#22'),(1220,.8,'#22'),(1221,1,'#20'),(1831,1.2,'#18')])
def test_duct_thickness_boundary_and_source(edge, mm, gauge):
    row = duct_sheet(edge)
    assert row['thickness_mm'] == mm and row['gauge'] == gauge
    assert row['status'] == '參考選用，非施工核准'


def test_insulation_changes_with_humidity_and_has_energy_balance():
    d = dict(insulate='1', heat_limit='100')
    low = insulation(dict(d, ambient_rh='50'), 50, 7)
    high = insulation(dict(d, ambient_rh='90'), 50, 7)
    assert high['thickness_mm'] >= low['thickness_mm']
    assert high['surface_t_c'] >= high['dewpoint_c'] + 1
    r2 = .025 + high['thickness_mm']/1000
    assert abs(high['heat_w_m'] - 2*math.pi*r2*8*(high['surface_t_c']-30)) < 1e-9
    impossible = insulation(dict(d, ambient_rh='100'), 50, 7)
    assert not impossible['feasible'] and 'thickness_mm' not in impossible


def test_vacuum_absolute_unit_equivalence_and_pump_limits():
    d = defaults('vacuum')
    a = calculate_tool('vacuum', d)
    b = calculate_tool('vacuum', dict(d, vacuum_p=str(150*101325/760), vacuum_unit='Pa(abs)'))
    assert a['actual_lpm'] == pytest.approx(b['actual_lpm'])
    with pytest.raises(ValidationError):
        calculate_tool('vacuum', dict(d, vacuum_p='101.325', vacuum_unit='kPa(abs)'))
    molecular = calculate_tool('vacuum', dict(d, vacuum_p='.00001', flow='.0000001', diameter_mode='指定內徑', inner_mm='50'))
    assert 0 < molecular['effective_speed_l_s'] < molecular['pump_speed_l_s']
    viscous = calculate_tool('vacuum', d)
    assert viscous['conductance_l_s'] is None


@pytest.mark.parametrize('tool,key', [('liquid','flow'),('liquid','liquid_t'),('liquid','velocity'),('vacuum','vacuum_p'),('vacuum','pump_l_s')])
@pytest.mark.parametrize('bad', ['NaN','inf','-inf'])
def test_nonfinite_never_becomes_a_valid_result(tool,key,bad):
    with pytest.raises(ValidationError):
        calculate_tool(tool, dict(defaults(tool), **{key:bad}))


def test_small_engineering_values_are_not_displayed_as_zero():
    from facility_studio.display_helpers import engineering_result_rows
    r = calculate_tool('liquid', defaults('liquid'))
    row = next(x for x in engineering_result_rows(r) if x[0] == '動力黏度')
    assert isinstance(row[1], str) and float(row[1]) > 0
    assert float(row[1]) == pytest.approx(r['mu'], rel=1e-5)


def test_insulation_cannot_use_bore_or_stale_smaller_outside_diameter():
    d = dict(defaults('water'), insulate='1', insulation_outer_mm='20')
    with pytest.raises(ValidationError) as caught:
        calculate_tool('water', d)
    assert caught.value.field_name == 'insulation_outer_mm'
