"""Fresh deterministic stress recipes usable inside the delivered application.

Every recipe changes physical room, utility and climate inputs. Native callers
must separately record their frozen executable and operating-system checks:
this module tests calculations and persistence, not GUI launch or rendering.
"""
import copy
import hashlib
import json
import math
import platform
import random
import sys
import tempfile
import time
import traceback
from collections import Counter
from pathlib import Path

from . import api, i18n
from .data import HVAC_PIPES
from .gas_catalog import GAS_OPTIONS, CUSTOM_GAS
from .project_store import save_project_file
from .simple_engines import compressed_air
from .simple_schema import defaults
from .utils import water_selection

SEED = 20261013
AREA_24 = math.pi * ((HVAC_PIPES[-1]["id_mm"] / 1000) ** 2) / 4


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def run_checks(scenarios=100, repeat=20):
    """Return case-level evidence, retaining every unexpected failure."""
    if scenarios < len(GAS_OPTIONS) or repeat < 1:
        raise ValueError('At least 51 scenarios and one calculation per recipe are required')
    started = time.perf_counter()
    rng = random.Random(SEED)
    checks = []
    cases = []
    physical_hashes = set()
    calculation_calls = 0
    simple_gas_calls = 0
    expected_rejections = 0
    old_language = i18n.language()

    def check(name, condition):
        checks.append(dict(name=name, passed=bool(condition)))
        if not condition:
            raise AssertionError(name)

    def close(name, actual, expected):
        check(name, math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-8))

    def calculate(project):
        nonlocal calculation_calls
        calculation_calls += 1
        return api.calculate(project)

    def gas_calculate(inputs):
        nonlocal simple_gas_calls
        simple_gas_calls += 1
        return compressed_air(inputs)

    def snapshot(result):
        return _digest(dict(result=result, report=str(api.report(result))))

    i18n.set_language('zh-Hant', persist=False)
    try:
        with tempfile.TemporaryDirectory(prefix='FacilityStudioStress-') as directory:
            for index in range(scenarios):
                case_started = time.perf_counter()
                offset = len(checks)
                case_id = 'ST%03d' % (index + 1)
                row = dict(id=case_id, software_pass=False)
                try:
                    p = api.default_project()
                    inp = p['inputs']
                    length = 12 + index * .21 + rng.uniform(.01, .1)
                    width = 8 + (index % 10) * .43 + rng.uniform(.01, .1)
                    height = 3 + (index % 4) * .25
                    ach = 12 + (index % 7) * 2
                    people = 4 + index % 8
                    velocity = .5 + (index % 10) * .25
                    capacity = AREA_24 * 60000 * velocity
                    water_flow = (capacity * (1 + (-1 if index % 2 else 1) * 1e-6)
                                  if index < 12 else rng.uniform(100, capacity * 3))
                    gas = GAS_OPTIONS[index % len(GAS_OPTIONS)]
                    gas_flow = rng.uniform(25, 500)
                    gas_pressure = (index % 11) * .9
                    gas_velocity = 2 + index % 19
                    gas_t = -10 + (index % 17) * 5
                    reference_t = (index % 6) * 10
                    reference_p = 90 + index % 21
                    z = .2 + (index % 14) * .2
                    changes = dict(project_name=case_id,
                        en_L_A=length, en_W_A=width, en_H_A=height, en_ach_A=ach,
                        ppl_A=people, oa_t=30+(index % 8)*.6,
                        oa_rh=45+(index % 6)*5, ow_t=(index % 7)*2,
                        ow_rh=50+(index % 5)*5, pre_mode='停用／旁通',
                        light_lux=300+(index % 7)*50, eq_kw=10+index*.75,
                        en_wall=2*(length+width)*height, en_floor=length*width,
                        e_up_eq=20+index, e_length_m=15+index*.6,
                        chw_link='獨立輸入', chw_q=water_flow,
                        water_velocity_max=velocity, gas1_type=gas,
                        gas1_name='5% H2 / 95% N2', gas1_q=gas_flow,
                        gas1_pressure_mode='本路管內壓力', gas1_barg=gas_pressure,
                        gas1_v_mode='自訂流速', gas1_velocity=gas_velocity,
                        gas_barg=gas_pressure+2, gas_temp=gas_t,
                        gas_std_t=reference_t, gas_std_kpa=reference_p, gas_z_ratio=z)
                    inp.update({k: format(v, '.15g') if isinstance(v, (int, float)) else v
                                for k, v in changes.items()})
                    physical_hash = _digest({k: v for k, v in inp.items() if k != 'project_name'})
                    row.update(physical_input_sha256=physical_hash, gas=gas,
                               water_lpm=float(inp['chw_q']))
                    check(case_id+'/physically distinct recipe', physical_hash not in physical_hashes)
                    physical_hashes.add(physical_hash)
                    original = _digest(p)
                    result = calculate(p)
                    baseline = snapshot(result)
                    close(case_id+'/room area', result['zones']['A']['area'], length*width)
                    close(case_id+'/room volume', result['zones']['A']['volume'], length*width*height)
                    close(case_id+'/ACH circulation', result['circulation_cmh'], length*width*height*ach)
                    water = result['water']['CHW']
                    required_runs = math.ceil(float(inp['chw_q']) / capacity - 1e-12)
                    check(case_id+'/single pipe before parallel runs', water['runs'] == required_runs)
                    close(case_id+'/water continuity', water['velocity_mps']*water['area_m2']*water['runs']*60000,
                          float(inp['chw_q']))
                    check(case_id+'/water velocity ceiling', water['velocity_mps'] <= velocity + 1e-8)
                    candidates = [x for x in HVAC_PIPES
                                  if float(inp['chw_q'])/water['runs']/60000 /
                                  (math.pi*(x['id_mm']/1000)**2/4) <= velocity+1e-12]
                    check(case_id+'/smallest suitable water pipe', water['id_mm'] == candidates[0]['id_mm'])
                    simple = defaults('gas')
                    simple.update(gas=gas, gas_name=inp['gas1_name'], flow=inp['gas1_q'],
                        velocity=inp['gas1_velocity'], pressure=inp['gas1_barg'],
                        temperature=inp['gas_temp'], reference_t=inp['gas_std_t'],
                        reference_p=inp['gas_std_kpa'], z_ratio=inp['gas_z_ratio'])
                    gas_result = gas_calculate(simple)
                    expected_flow = float(inp['gas1_q'])*reference_p/(101.325+gas_pressure*100) \
                        *(gas_t+273.15)/(reference_t+273.15)*z
                    close(case_id+'/independent gas T P Z', result['gas']['1']['actual_lpm'], expected_flow)
                    close(case_id+'/main and quick gas agreement', gas_result['actual_lpm'], expected_flow)
                    close(case_id+'/main and quick gas pipe agreement', result['gas']['1']['selected_id_mm'],
                          gas_result['pipe']['id'])
                    check(case_id+'/gas velocity ceiling', gas_result['velocity_mps'] <= gas_velocity+1e-8)
                    reverse = dict(simple, flow_basis='管內實際流量', flow_unit='ALPM', flow=str(expected_flow))
                    close(case_id+'/gas actual to standard inversion', gas_calculate(reverse)['standard_lpm'],
                          float(inp['gas1_q']))
                    for repetition in range(1, repeat):
                        check(case_id+'/repeat-%d' % (repetition+1), snapshot(calculate(p)) == baseline)
                    # Use an existing localized label while retaining a Unicode
                    # filename in the actual persistence exercise.
                    file_path = Path(directory) / ('設備'+' '+case_id+'.json')
                    save_project_file(file_path, p)
                    check(case_id+'/atomic save and reopen', snapshot(calculate(api.read_project(file_path))) == baseline)
                    changed = copy.deepcopy(p)
                    changed['inputs']['project_name'] += ' saved revision'
                    save_project_file(file_path, changed)
                    check(case_id+'/previous project backup', _digest(api.read_project(file_path.with_suffix('.json.bak'))) == original)
                    check(case_id+'/replacement save and reopen',
                          snapshot(calculate(api.read_project(file_path))) == snapshot(calculate(changed)))
                    # Zero-demand drafts exercise the public project validator,
                    # rather than bypassing it through gas_from_inputs.
                    draft = copy.deepcopy(p)
                    draft['inputs'].update(gas2_type='NF3' if index % 2 else CUSTOM_GAS,
                        gas2_q='0' if index % 2 else '0.00', gas2_v_mode='自訂流速',
                        gas2_velocity=('', 'bad', 'NaN', '1e309')[index % 4],
                        gas2_name='retained\ninvalid draft')
                    zero = calculate(draft)
                    check(case_id+'/zero-demand gas is neutral', zero['gas']['2']['actual_lpm'] == 0
                          and zero['gas']['2']['velocity_mps'] == 0
                          and 'custom_name' not in zero['gas']['2'])
                    check(case_id+'/zero-demand draft retained', zero['project']['inputs'] == draft['inputs'])
                    check(case_id+'/zero-demand drafts preserve HVAC',
                          _digest(zero['summer']) == _digest(result['summer'])
                          and _digest(zero['winter']) == _digest(result['winter']))
                    check(case_id+'/input immutability', _digest(p) == original)
                    row.update(software_pass=True, outcome_sha256=baseline,
                               engineering_output_sha256=_digest(dict(
                                   result={k: v for k, v in result.items()
                                           if k not in {'project', 'raw_inputs', 'inputs', 'effective_inputs', 'hash'}},
                                   report=str(api.report(result)))),
                               engineering_status=result['quality']['status'],
                               engineering_failed=result['quality']['failed'],
                               engineering_pending=result['quality']['pending'])
                except Exception as error:
                    row.update(error_type=type(error).__name__, error_message=str(error),
                               traceback=traceback.format_exc())
                row.update(check_count=len(checks)-offset, seconds=time.perf_counter()-case_started)
                cases.append(row)
            # Engineering bounds are explicit negative controls outside the 100
            # valid recipes, and are never counted as successful full designs.
            for name, flow, limit in (
                    ('above32parallel', AREA_24*60000*2*32*1.001, 2),
                    ('manualundersized', 30000, 1)):
                rejected = False
                try:
                    if name == 'manualundersized':
                        water_selection(flow, limit, manual_id=574.6)
                    else:
                        water_selection(flow, limit)
                except api.ValidationError:
                    rejected = True
                checks.append(dict(name='negative/'+name, passed=rejected))
                expected_rejections += int(rejected)
    finally:
        i18n.set_language(old_language, persist=False)
    failed = [x for x in cases if not x['software_pass']]
    failed_checks = [x for x in checks if not x['passed']]
    return dict(version=api.VERSION, passed=not failed and not failed_checks,
        seed=SEED, scenario_count=len(cases), distinct_physical_input_count=len(physical_hashes),
        repeat_per_scenario=repeat, calculation_calls=calculation_calls,
        simple_gas_calls=simple_gas_calls, expected_engineering_rejections=expected_rejections,
        software_passed=len(cases)-len(failed), software_failed=len(failed),
        engineering_status_counts=dict(Counter(x.get('engineering_status') for x in cases
                                              if x.get('engineering_status'))),
        engineering_failed_scenarios=sum(x.get('engineering_failed', 0) > 0 for x in cases),
        engineering_pending_scenarios=sum(x.get('engineering_pending', 0) > 0 for x in cases),
        check_count=len(checks), failed_checks=failed_checks, cases=cases,
        host=platform.platform(), frozen=bool(getattr(sys, 'frozen', False)),
        seconds=time.perf_counter()-started,
        scope=f'{scenarios} varied full-project calculation/report/persistence recipes; water and all factory gases; no GUI launch claim')
