#!/usr/bin/env python3
"""Independent engineering boundaries for either source tree; no GUI is opened.

Run once per process for each --platform. These checks validate source behavior;
they do not certify a Windows EXE, a macOS App, or a selected physical device.
"""

import argparse
import copy
import json
import math
from pathlib import Path
import platform as host_platform
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]


def run_checks(source_platform):
    source_root = ROOT / source_platform
    package_root = source_root / "facility_studio"
    if not package_root.is_dir():
        raise ValueError("Selected source tree is missing: " + str(source_root))
    loaded = sys.modules.get("facility_studio")
    if loaded and Path(loaded.__file__).resolve().parent != package_root.resolve():
        raise RuntimeError("Run each source platform in a fresh Python process")
    sys.path.insert(0, str(source_root))
    from facility_studio.simple_engines import calculate_tool
    from facility_studio.simple_schema import defaults
    from facility_studio.data import STANDARD_BREAKER_AT
    from facility_studio.schema import default_project, V560_INPUT_KEYS, SCHEMA_VERSION
    from facility_studio.engine import calculate, migrate_project
    from facility_studio.services import upstream_values, calculate_pipeline, electrical_device_loads
    from facility_studio.utils import load_current, next_standard
    from facility_studio.errors import ValidationError

    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    def near(name, value, expected, tol=1e-9):
        check(name, math.isclose(value, expected, rel_tol=tol, abs_tol=tol))
    def run(tool, **changes):
        data = defaults(tool)
        data.update({key: str(value) for key, value in changes.items()})
        return calculate_tool(tool, data)

    # Zero pressure must mean zero PRESSURE-DRIVEN outward flow, not a base ACH.
    zero = run('cleanroom', delta_p=0, persons=0)
    negative = run('cleanroom', delta_p=-15, persons=0)
    near('zero dp no leakage', zero['leakage_cmh'], 0)
    near('negative dp no outward leakage', negative['leakage_cmh'], 0)
    ref = run('cleanroom', delta_p=15, persons=0)
    quad = run('cleanroom', delta_p=60, persons=0)
    near('reference one ACH is explicit 300m3 per hour', ref['leakage_cmh'], 300)
    near('fourfold dp gives double leakage', quad['leakage_cmh'], 600)
    people = run('cleanroom', delta_p=0, persons=20, exhaust_cmh=100)
    near('occupancy is alternative minimum not added twice', people['oa_cmh'], 600)
    near('DCC handles pure room recirculation', people['dcc_cmh'], 18000)
    near('all OA crosses plenum FFUs', people['ffu_total_cmh'], 18600)
    check('FFU count rounding includes OA', people['ffu_count'] == 19)
    large = run('cleanroom', delta_p=0, persons=20, ffu_size='1200x1200 (1.44m²)')
    near('4x4 nominal module area', large['coverage_ratio'], 27.36)
    check('coverage beyond 100 is preserved as failure', run('cleanroom', area=10, height=3, ach=1000, ffu_size='1200x1200 (1.44m²)')['coverage_exceeded'])

    heat = run('heat_loads', area=100, persons=10, equipment_kw=20, ffu_count=19, oa_cmh=600)
    near('room load independent sum', heat['q_room_sensible_kw'], 1.2 + 2 + .75 + 20 + 3.42)
    near('OA mass flow enthalpy load', heat['q_mau_kw'], 10)
    near('neutral reference latent counted once', heat['q_total_kw'], 37.92)
    actual = run('heat_loads', area=100, persons=10, equipment_kw=20, ffu_count=19, oa_cmh=600,
                 oa_load_basis='外氣至實際露點送風', mau_room_sensible_kw=2, mau_supply_delta_t=10)
    near('actual leaving MAU latent not added twice', actual['q_total_kw'], 35.37)
    near('MAU room sensible credit reduces DCC', actual['q_dcc_kw'], 25.37)

    pump = run('pumps', flow=60, flow_unit='m³/h', head_m=36.7, eta_pump=.75, eta_motor=.9)
    near('pump water power', pump['hydraulic_power_kw'], 6.00045)
    near('shaft excludes motor losses', pump['shaft_power_kw'], 8.0006)
    near('electrical includes motor losses', pump['motor_input_kw'], 8.889555555555556)
    check('motor catalogue rates output and rounds up after 15pct', pump['recommended_motor_kw'] == 11)
    check('motor over catalogue does not clamp', run('pumps', flow=100000, head_m=200)['recommended_motor_kw'] is None)
    check('AT over catalogue does not clamp', next_standard(401, STANDARD_BREAKER_AT) is None)

    load = run('electrical', power=10/.745699871582, power_unit='HP', motor_efficiency=.9, kind='連續運轉')
    expected_current = 10000 / (math.sqrt(3) * 380 * .85 * .9)
    near('shaft kW current uses efficiency once', load['current_a'], expected_current)
    near('continuous design current is 125pct', load['design_breaker_a'], 1.25 * expected_current)
    if source_platform in ('windows', 'macos'):
        check('125pct breaker and conductor use the same circuit selection',
              load['recommended_breaker_at'] == load['selected']['nfb_a'] == 25
              and load['design_a'] <= load['selected']['nfb_a'] <= load['selected']['ampacity_a'])
    else:
        check('legacy Mac continuous breaker reference', load['recommended_breaker_at'] == 30)
    near('single phase current', load_current(4.4, 220, 1, 1, 1), 20)

    # Use a fixed duct calculation then independently reconstruct its equal-circle
    # friction; fittings retain actual duct velocity pressure.
    duct = run('duct', flow=3600, check_path=1, pressure=1000, length=25,
               k_sum=0, equipment=0, friction_method='Huebscher 等摩擦圓管')
    r = duct['rectangle']
    a, b = r['w_mm']/1000, r['h_mm']/1000
    de = 1.30*(a*b)**.625/(a+b)**.25
    ve = 4/(math.pi*de**2)
    near('Huebscher diameter', r['equivalent_diameter_m'], de)
    near('equal-circle velocity basis', r['friction_velocity_mps'], ve)
    f = .02
    re = 1.2*ve*de/.0000181
    for _ in range(100):
        f = (-2*math.log10((.09/1000)/de/3.7+2.51/(re*math.sqrt(f))))**-2
    near('equal-circle friction without rectangular velocity mixing', r['friction_pa'], f*25/de*1.2*ve*ve/2, 1e-7)
    near('roughness epsilon and D both metres', r['relative_roughness'], .00009/de)

    p = default_project()
    p['inputs'].update(sys_type='MAU+FFU+DCC (全外氣/無塵室)', ffu_w='180', ffu_topology='獨立FFU循環（MAU直接入室）', ffu_airflow_basis='FFU總送風（已含OA）')
    legacy = calculate(p)
    near('legacy independent DCC retains entire recirculation', legacy['dcc_cmh'], legacy['circulation_cmh'])
    p['inputs']['ffu_topology'] = 'MAU入靜壓箱經FFU送風'
    p['inputs']['ffu_airflow_basis'] = '室內基本循環（另加OA）'
    recirc = calculate(p)
    near('new main flow explicitly adds final OA', recirc['ffu_total_cmh'], recirc['circulation_cmh'] + recirc['oa_room_cmh'])
    near('main separates DCC return', recirc['dcc_cmh'], recirc['circulation_cmh'])
    near('extra FFU fan power enters sensible balance', recirc['qs']-legacy['qs'], (recirc['ffu_count']-legacy['ffu_count'])*.18)
    near('main summer sensible conservation', recirc['sensible_residual'], 0, 1e-6)
    p['inputs']['ffu_airflow_basis'] = 'FFU總送風（已含OA）'
    plenum_total = calculate(p)
    near('plenum total-flow basis separates OA from return', plenum_total['dcc_cmh'], plenum_total['ffu_total_cmh']-plenum_total['oa_room_cmh'])
    near('quality consumes same DCC flow as reported', plenum_total['dcc_airside']['flow_cmh'], plenum_total['dcc_cmh'])
    p['inputs']['en_ach_A'] = '0'
    zero_plenum = calculate(p)
    check('negative plenum return is preserved, not clamped', zero_plenum['dcc_cmh'] < 0 and zero_plenum['dcc_airside']['flow_cmh'] < 0)
    check('nonpositive DCC cannot pass capacity check', zero_plenum['dcc_airside']['required_outlet_c'] is None and any(x['name']=='DCC 循環風量與能力' and x['status']=='未達' for x in zero_plenum['quality']['items']))
    p['inputs']['ffu_topology'] = '獨立FFU循環（MAU直接入室）'
    zero_independent = calculate(p)
    near('independent zero FFU need does not gain OA count', zero_independent['ffu_count'], 0)
    near('independent zero FFU keeps actual zero return', zero_independent['dcc_cmh'], 0)
    old = default_project()
    old['schema_version'] = 11
    for section in ['inputs','provenance']:
        old[section] = {key:value for key,value in old[section].items() if key in V560_INPUT_KEYS}
    snapshot = copy.deepcopy(old)
    migrated = migrate_project(old)
    check('v11 migration does not mutate original', old == snapshot)
    check('v11 migration preserves physical assumptions', migrated['schema_version'] == SCHEMA_VERSION and migrated['inputs']['ffu_airflow_basis'] == 'FFU總送風（已含OA）' and migrated['inputs']['leak_method'] == '門縫孔口法' and migrated['inputs']['ffu_topology'] == '獨立FFU循環（MAU直接入室）')

    pipeline = calculate_pipeline({'pumps': {'terminal_head_m':'10', 'static_head_m':'0'},
                                   'electrical': {'chiller_cop':'5', 'mau_input_kw':'2', 'process_input_kw':'25'}})
    near('water capacity matches transferred heat load', pipeline['water']['thermal']['kw'], pipeline['heat_loads']['q_total_kw'])
    near('head transfer adds only explicit terminal allowance', pipeline['pumps']['head_m'], pipeline['water']['pressure']['head_m']+10)
    loads = {row['name']:row['power_kw'] for row in pipeline['electrical_loads']}
    near('chiller thermal to electrical through COP only', loads['Chiller'], pipeline['heat_loads']['q_total_kw']/5)
    near('pump actual electrical input enters feeder', loads['CHWP'], pipeline['pumps']['motor_input_kw'])
    near('feeder uses distinct explicit electrical sources', pipeline['electrical']['power_kw'], sum(loads.values()))
    patch = upstream_values('electrical', pipeline, pipeline['adopted_inputs']['electrical'])
    near('repeat upstream transfer idempotent', float(patch['power']), pipeline['electrical']['power_kw'])
    check('all structured results finite', bool(json.dumps(pipeline, allow_nan=False)))

    # Repeated equipment identity must fail even when the later source is the
    # dedicated chiller/COP adapter rather than a user schedule row.
    for extra in ({'chiller_cop':'5'}, {'chiller_input_kw':'8'}):
        try:
            calculate_pipeline({'electrical': dict(extra, device_loads=[{'name':'Chiller','power_kw':10}])})
        except ValidationError as error:
            check('duplicate scheduled and calculated Chiller rejected '+str(extra), error.field_name == 'device_loads')
        else:
            check('duplicate Chiller must not be counted twice', False)

    scheduled = calculate_pipeline({'electrical': {'device_loads': [
        {'name':'Chiller','power_kw':8}, {'name':'MAU','power_kw':2}, {'name':'製程設備','power_kw':25}]}})
    check('scheduled Chiller satisfies missing-input warning', not any('冰機未提供' in x for x in scheduled['warnings']))
    check('scheduled MAU satisfies its warning independently', not any('MAU輸入電功率尚未提供' in x for x in scheduled['warnings']))
    check('scheduled process load satisfies its warning independently', not any('製程設備輸入電功率尚未提供' in x for x in scheduled['warnings']))
    partial = calculate_pipeline({'electrical': {'process_input_kw':'25', 'chiller_cop':'5'}})
    check('process entry does not hide missing MAU', any('MAU輸入電功率尚未提供' in x for x in partial['warnings']))
    check('provided process does not get a false missing warning', not any('製程設備輸入電功率尚未提供' in x for x in partial['warnings']))
    priority = calculate_pipeline({'electrical': {'chiller_cop':'5', 'chiller_input_kw':'12'}})
    near('explicit Chiller input wins over COP without duplication', sum(x['power_kw'] for x in priority['electrical_loads'] if x['name']=='Chiller'), 12)

    for changes, field in [
        ({'oa_cmh':0, 'persons':10}, 'oa_cmh'),
        ({'oa_cmh':0, 'persons':0, 'mau_room_sensible_kw':1, 'mau_supply_delta_t':10}, 'mau_room_sensible_kw'),
        ({'oa_cmh':100, 'persons':0, 'mau_room_sensible_kw':1, 'mau_supply_delta_t':2}, 'mau_room_sensible_kw'),
        ({'oa_cmh':600, 'persons':0, 'mau_room_sensible_kw':1, 'mau_supply_delta_t':0}, 'mau_room_sensible_kw'),
    ]:
        try:
            run('heat_loads', oa_load_basis='外氣至實際露點送風', **changes)
        except ValidationError as error:
            check('actual MAU physical boundary '+str(changes), error.field_name == field)
        else:
            check('impossible actual MAU boundary must fail', False)
    empty = run('heat_loads', oa_load_basis='外氣至實際露點送風', persons=0, oa_cmh=0)
    near('zero OA with no latent or MAU credit remains valid DCC-only load', empty['q_total_kw'], empty['q_room_sensible_kw'])
    near('sensible credit bound is explicit airflow and temperature difference', actual['mau_sensible_limit_kw'], 1.2*600/3600*1.006*10)

    # The lumen method requires manufacturer photometry; room geometry alone cannot determine U.
    lights = run('lighting', mode='反算燈數', area_mode='長×寬', length='10', width='6',
                 target='500', watts='40', lumen_mode='燈具型錄流明', lumens='4000',
                 u_mode='型錄 U＋室指數 K 檢核', mount_h='3.5', work_h='1',
                 utilization='.6', maintenance='.8')
    near('room index uses actual length and width', lights['room_index_k'], 60/(2.5*16))
    near('catalogue U is independent of geometry', lights['utilization'], .6)
    check('lumen method rounds up independently specified load', lights['quantity'] == 16)
    second = run('lighting', mode='反算燈數', area_mode='長×寬', length='20', width='3',
                 target='500', watts='40', lumen_mode='燈具型錄流明', lumens='4000',
                 u_mode='型錄 U＋室指數 K 檢核', mount_h='3.5', work_h='1',
                 utilization='.6', maintenance='.8')
    check('different shape changes K without inventing new photometric U',
          second['room_index_k'] != lights['room_index_k'] and second['utilization'] == .6)
    wb = default_project()
    wb['inputs'].update(en_L_A='10', en_W_A='6', en_H_A='3.5', en_L_B='0', en_W_B='0',
                        light_lux='500', light_lm='4000', light_w='40', light_m='.8', light_u='.6',
                        light_u_mode='型錄 U＋室指數 K 檢核', light_work_h='1')
    wb_light = calculate(wb)['light']
    check('workbench uses entered U and the same room geometry',
          wb_light['qty'] == 16 and math.isclose(wb_light['room_index_k'], 60/(2.5*16)))


    return {
        "kind": "source-engineering-boundaries",
        "source_platform": source_platform,
        "host_os": host_platform.system(),
        "python": host_platform.python_version(),
        "schema_version": SCHEMA_VERSION,
        "passed": True,
        "check_count": len(checks),
        "checks": [{"name": name, "passed": True} for name in checks],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("windows", "macos"), required=True,
                        help="Source tree to import; this does not change the host OS")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence path")
    args = parser.parse_args(argv)
    try:
        result = run_checks(args.platform)
    except Exception as error:
        result = {"kind": "source-engineering-boundaries", "source_platform": args.platform,
                  "host_os": host_platform.system(), "python": host_platform.python_version(),
                  "passed": False, "error": type(error).__name__ + ": " + str(error)}
        traceback.print_exc()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
