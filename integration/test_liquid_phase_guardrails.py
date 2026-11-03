"""Independent physical guardrail expectations; intentionally fail on 731e416."""
import os, sys
from pathlib import Path
import pytest
from CoolProp.CoolProp import PropsSI

SOURCE_PLATFORM = os.environ.get("SOURCE_PLATFORM", "windows" if sys.platform == "win32" else "macos")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / SOURCE_PLATFORM))
from facility_studio.simple_schema import defaults
from facility_studio.simple_engines import calculate_tool
from facility_studio.errors import ValidationError

def rejected_or_failed(data):
    try:
        r=calculate_tool('liquid',data)
    except ValidationError:
        return True
    return bool(r.get('failures'))

@pytest.mark.parametrize('name',['乙二醇水溶液','丙二醇水溶液'])
def test_zero_glycol_concentration_must_obey_water_phase(name):
    # At 0 wt% glycol the substance is water, not an unknown mixture.
    # Water at 80 C has Pv=47.414 kPa. 1 kPa cannot be stable single-phase liquid.
    d=dict(defaults('liquid'),liquid=name,concentration='0',liquid_t='80',liquid_p='1',material='SUS316L')
    assert rejected_or_failed(d), 'Known vapor-phase input returned liquid sizing without a structural phase failure'

@pytest.mark.parametrize('name',['乙二醇水溶液','丙二醇水溶液'])
def test_manual_transport_properties_must_not_bypass_known_freezing(name):
    # Model freezing points at 20 wt% are -7.949 C MEG / -7.173 C MPG.
    d=dict(defaults('liquid'),liquid=name,concentration='20',liquid_t='-20',material='SUS316L',
           properties='供應商物性',liquid_rho='1040',liquid_cp='3.8',liquid_mu='.006',
           property_reference='Synthetic positive transport values, 20 wt%, -20 C')
    assert rejected_or_failed(d), 'Known freeze boundary was bypassed by supplier transport-property selection'

def test_flooded_saturated_surface_is_not_proven_suction_phase_failure():
    pv=PropsSI('P','T',353.15,'Q',0,'Water')/1000
    d=dict(defaults('liquid'),material='SUS316L',liquid_t='80',check_npsh='1',
           suction_surface_kpa=repr(pv),suction_level_m='10',suction_loss_kpa='1',
           npshr_m='3',pump_curve_reference='Synthetic pump R1, 100 LPM, 1450 rpm',
           npsh_margin_m='1',npsh_margin_reference='Synthetic project R1')
    r=calculate_tool('liquid',d)
    assert r['suction']['available_m'] > r['suction']['threshold_m']
    assert r['suction']['suction_static_kpa'] > r['suction']['vapor_kpa']
    assert not r['failures'], 'Saturated vessel surface alone was incorrectly labeled proven suction phase failure'
    assert r['suction']['criterion_met']

@pytest.mark.parametrize('name',['乙二醇水溶液','丙二醇水溶液'])
def test_glycol_without_bubble_data_explicitly_remains_unverified(name):
    from facility_studio.simple_reports import tool_report
    d=dict(defaults('liquid'),liquid=name,liquid_t='80',liquid_p='1',material='SUS316L')
    r=calculate_tool('liquid',d)
    assert r['liquid_phase_verified'] is False
    assert any('液相尚未驗證' in x for x in r['warnings'])
    assert '液相尚未驗證' in tool_report(r,d)

def pump_inputs(**kw):
    return dict(dict(defaults('liquid'),liquid='乙二醇水溶液',check_npsh='1',
                suction_surface_kpa='101.325',suction_level_m='2',suction_loss_kpa='10',
                npshr_m='3',pump_curve_reference='Synthetic pump R1, 100 LPM, 1450 rpm',
                npsh_margin_m='1',npsh_margin_reference='Synthetic project R1',
                vapor_pressure_kpa='1.7',vapor_reference='Synthetic same-condition bubble point'),**kw)

def test_supplied_bubble_point_must_match_operating_pressure():
    d=pump_inputs(liquid_t='80',liquid_p='1',vapor_pressure_kpa='40')
    with pytest.raises(ValidationError) as e:
        calculate_tool('liquid',d)
    assert e.value.field_name == 'liquid_p'

def test_verified_glycol_input_can_still_satisfy_npsh():
    r=calculate_tool('liquid',pump_inputs())
    assert r['liquid_phase_verified'] is True
    assert r['suction']['criterion_met'] and not r['failures']

def test_out_of_model_manual_glycol_is_not_guessed_safe():
    d=pump_inputs(concentration='80',properties='供應商物性',liquid_rho='1080',liquid_cp='3',
                  liquid_mu='.01',property_reference='Synthetic supplier transport data')
    r=calculate_tool('liquid',d)
    assert r['liquid_phase_verified'] is False
    assert not r['suction']['criterion_met']
    assert not r['failures']  # Missing evidence is not proof of failure.

def test_zero_concentration_uses_water_vapor_pressure_and_inactive_drafts():
    from facility_studio.simple_schema import active_field
    d=pump_inputs(concentration='0',vapor_pressure_kpa='invalid',vapor_reference='')
    r=calculate_tool('liquid',d)
    assert not active_field('liquid','vapor_pressure_kpa',d)
    assert 'vapor_pressure_kpa' not in r['adopted_inputs']
    assert r['suction']['vapor_kpa'] == pytest.approx(PropsSI('P','T',293.15,'Q',0,'Water')/1000)

@pytest.mark.parametrize('name',['乙二醇水溶液','丙二醇水溶液'])
def test_valid_supplier_glycol_transport_values_are_preserved(name):
    d=dict(defaults('liquid'),liquid=name,properties='供應商物性',liquid_rho='1040',liquid_cp='3.8',
           liquid_mu='.006',property_reference='Synthetic supplier transport data, 20 C 20 wt%')
    r=calculate_tool('liquid',d)
    assert (r['rho'],r['cp'],r['mu']) == (1040,3.8,.006)
    assert r['liquid_phase_verified'] is False

@pytest.mark.parametrize('surface_delta,level', [(-1,'10'),(0,'-1')])
def test_saturated_boundary_fix_keeps_actual_flashing_failures(surface_delta,level):
    pv=PropsSI('P','T',353.15,'Q',0,'Water')/1000
    d=pump_inputs(liquid='清水',liquid_t='80',material='SUS316L',
                  suction_surface_kpa=str(pv+surface_delta),suction_level_m=level,suction_loss_kpa='1')
    r=calculate_tool('liquid',d)
    assert r['failures'] and not r['suction']['criterion_met']

def test_selected_platform_source_is_the_one_loaded():
    from facility_studio import facility_simple
    assert Path(facility_simple.__file__).resolve().parent.parent.name == SOURCE_PLATFORM
