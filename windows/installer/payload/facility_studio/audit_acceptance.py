"""Regression acceptance for the independently reproduced F01–F06 defects.

The original audit's physical references remain independent of the repaired
conversion helpers. These checks run in source CI and inside the delivered EXE.
"""
import copy
from decimal import Decimal
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch


class _Checks:
    def __init__(self, out):
        self.out = out
        self.checks = []

    def check(self, name, passed, actual=None, expected=None, issue=None):
        if not passed:
            raise AssertionError((name, actual, expected))
        self.checks.append(dict(name=name, passed=True, issue_id=issue))

    def near(self, name, actual, expected, issue=None, tolerance=1e-9):
        self.check(name, math.isfinite(actual) and abs(actual-expected) <= tolerance * max(1, abs(expected)), actual, expected, issue)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def electrical_schedule():
    from facility_studio.equipment_analysis import analyze_equipment
    from facility_studio.equipment_io import Cell
    from facility_studio.equipment_schema import SCHEMA_ID
    values = dict(enabled=1,id='AUDIT-001',name='Synthetic 10 kW load',group='AUDIT',
                  power=10,voltage=380,phases='3',pf=.85)
    return analyze_equipment(dict(schema_id=SCHEMA_ID,source_name='synthetic-audit.csv',
        records=[dict(system='電力',row=6,cells={k:Cell(v) for k,v in values.items()})]))


def empty_power_inputs():
    from facility_studio.schema import default_project
    from facility_studio.contributions import POWER_KEYS
    p = default_project()
    for key in POWER_KEYS:
        p['inputs'][key] = '0'
        p['inputs']['u_'+key] = 'kW'
    return p


def rcu_project(solar=100):
    from facility_studio.schema import default_project, FIELDS
    p=default_project()
    p['inputs'].update(sys_type=next(x for x in FIELDS['sys_type']['options'] if x.startswith('RCU')),
        ppl_A='0',ppl_B='0',en_ach_A='100',en_ach_B='100',winter_solar_kw=str(solar),pre_mode='停用／旁通')
    return p


def pure_checks(a):
    from facility_studio.simple_engines import calculate_tool, electrical
    from facility_studio.simple_schema import defaults, TOOLS, active_field
    from facility_studio.simple_reports import tool_report
    from facility_studio.reports import executive_summary
    from facility_studio.engine import calculate, electrical_from_inputs
    from facility_studio.errors import ValidationError
    from facility_studio.quick_tools import convert_all
    from facility_studio.contributions import empty_ledger, equipment_contribution, updated_ledger, removed_ledger

    # Independent fixed-unit electrical equivalence, rather than reusing conversion helpers.
    for supply, phases, voltage in [('三相 380V',3,380),('單相 220V',1,220)]:
        for pf in (.7,.85,1):
            factor=(math.sqrt(3) if phases==3 else 1)*voltage*pf/1000
            for unit,value in [('kW',10),('W',10000),('kVA',10/pf),('A',10/factor),
                               ('HP',10*.9/.745699871582),('PS',10*.9/.73549875)]:
                d=defaults('electrical');d.update(supply=supply,pf=str(pf),power_unit=unit,power=str(value))
                r=electrical(d)
                a.near(f'electrical-equivalent/{supply}/{pf}/{unit}',r['power_kw'],10)
                a.near(f'electrical-current/{supply}/{pf}/{unit}',r['current_a'],10/factor)

    # Every ordinary form must reject non-finite active numeric fields.
    for tool,spec in TOOLS.items():
        values=defaults(tool)
        for field in spec['fields']:
            key=field['key']
            if field['options'] or field['checkbox'] or not active_field(tool,key,values):
                continue
            try:float(values[key])
            except ValueError:continue
            for invalid in ('nan','inf','-inf','1e9999','','12.3x'):
                d=dict(values);d[key]=invalid
                try:
                    calculate_tool(tool,d)
                    rejected=False
                except ValidationError:
                    rejected=True
                a.check(f'reject-invalid/{tool}/{key}/{invalid}',rejected,expected='ValidationError')

    # F01: report and adopted engineering calculation disagree about local-loss K.
    for k in (0,4,20,100):
        d=defaults('water');d['k_sum']=str(k);r=calculate_tool('water',d)
        expected_local=k*1000*r['pipe']['velocity_mps']**2/2
        a.near(f'water-local-loss-physics/K={k}',r['pressure']['local_pa'],expected_local)
        text=str(tool_report(r,d,language='zh-Hant'))
        report_k=float(re.search(r'ΣK=([0-9.eE+\-]+)',text)[1])
        a.near(f'water-report-adopted-K/{k}',report_k,k,'F01')
        (a.out/f'water-K{k}.txt').write_text(text,encoding='utf-8')
        dump(a.out/f'water-K{k}.json',dict(inputs=d,result=r))

    # F02: executive summary breaker is independently reselected without wire coordination.
    for kind in ('一般設備','連續運轉','馬達'):
        for power in (10,11.2,13,15,20,30,40,50,80,100):
            d=defaults('electrical');d.update(power=str(power),kind=kind)
            r=electrical(d);c=r['selected'];row=executive_summary(r)[-1]
            summary_at=float(re.match(r'([0-9.]+)',row['selection'])[1])
            a.near(f'electrical-summary-selected-breaker/{kind}/{power}',summary_at,c['nfb_a'],'F02')
            a.check(f'electrical-summary-wire-protection/{kind}/{power}',summary_at<=c['ampacity_a']+1e-9,
                    dict(summary_at=summary_at,selected=c,summary=row),expected='summary AT <= selected effective ampacity',issue='F02')
            if kind=='一般設備' and power==10:
                from facility_studio.html_report import html_report
                dump(a.out/'electrical-default-contradiction.json',dict(inputs=d,result=r,summary=row))
                (a.out/'electrical-default.html').write_text(str(html_report(r,language='zh-Hant')),encoding='utf-8')

    # F03: retain physical base power when a schedule is added to the same panel.
    schedule=electrical_schedule()
    for target,key in [('UP','e_up_oven'),('NP','e_np_pump')]:
        factor=math.sqrt(3)*380*.85/1000
        for unit,value in [('kW',85),('kVA',100),('W',85000),('HP',85*.9/.745699871582),('A',85/factor)]:
            p=empty_power_inputs();i=p['inputs'];i[key]=str(value);i['u_'+key]=unit
            before=electrical_from_inputs(i)[target]['kw']
            entry=equipment_contribution(schedule,schedule['groups'][0],i,target)
            ledger,updates,summary=updated_ledger(empty_ledger(),entry,i)
            adopted=dict(i,**updates)
            total=sum(float(adopted[k]) for k in adopted if k.startswith('e_'+target.lower()+'_') and 'u_'+k in adopted)
            # All physical loads above have been normalized to kW by this API.
            a.near(f'ledger-preserve-physical-base/{target}/{unit}',total,before+10,'F03')
            restored,restore_updates,_=removed_ledger(ledger,entry['id'],adopted)
            removed=dict(adopted,**restore_updates)
            a.check(f'ledger-remove-restores-original/{target}/{unit}',all(removed[k]==i[k] for k in updates),
                    expected='all adopted keys restored')
            dump(a.out/f'ledger-{target}-{unit}.json',dict(original=i,expected_total_kw=before+10,actual_total_kw=total,
                  updates=updates,ledger=ledger,summary=summary))

    # F04: terminal RCU count must cover the design envelope of both seasons.
    for solar in (0,50,100):
        p=rcu_project(solar);r=calculate(p)
        summer=sum(r['summer'][t]['water_kw'] for t in ('c1','c2'))
        winter=sum(r['winter'][t]['water_kw'] for t in ('c1','c2'))
        needed=math.ceil(max(summer,winter)*r['sf']/(float(p['inputs']['en_rcu_rt'])*r['rt_kw'])-1e-12)
        actual=r['counts']['RCU']
        a.check(f'rcu-both-seasons/{solar}',actual>=needed,
             dict(count=actual,summer_kw=summer,winter_kw=winter,installed_kw=actual*float(p['inputs']['en_rcu_rt'])*r['rt_kw']),
             dict(minimum_count=needed,design_kw=max(summer,winter)*r['sf']),'F04')
        dump(a.out/f'rcu-winter-{solar}.json',r)

    # F06: bounded finite input must not produce a successful infinite result.
    for category,unit in [('壓力','bar'),('風量','m³/s'),('水量','L/s'),('冷熱功率','日本冷凍噸')]:
        try:
            values=convert_all(category,'1e308',unit)
            valid=all(math.isfinite(v) for v in values.values())
        except ValidationError:
            values='rejected';valid=True
        a.check(f'unit-overflow/{category}/{unit}',valid,values,'finite values or structured rejection','F06')

    # Air, water, pump and import controls complement defect reproductions.
    for lpm in (0,1,100,5000):
        d=defaults('pumps');d.update(flow=str(lpm),head_m='20',terminal_head_m='5',static_head_m='3',head_margin_pct='10')
        r=calculate_tool('pumps',d)
        a.near(f'pump-head-physics/{lpm}',r['head_m'],30.5)
        a.near(f'pump-power-physics/{lpm}',r['motor_input_kw'],lpm/60000*1000*9.81*30.5/1000/.7/.9)
    for t,rh in [(-10,10),(0,50),(22,50),(35,90),(50,5)]:
        d=defaults('air');d.update(temperature=str(t),rh=str(rh));r=calculate_tool('air',d)['state']
        a.check(f'air-bounded/{t}/{rh}',r['wetbulb_c']<=t+1e-7 and r['dewpoint_c']<=t+1e-7 and r['w']>=0,r)
    from facility_studio.json_io import read_json_file
    bad={'duplicate':'{"a":1,"a":2}','nan':'{"a":NaN}','overflow':'{"a":1e9999}','depth':'['*65+'0'+']'*65}
    for name,text in bad.items():
        path=a.out/f'bad-json-{name}.json';path.write_text(text,encoding='utf-8')
        try:read_json_file(path);rejected=False
        except ValidationError:rejected=True
        a.check('json-reject/'+name,rejected,expected='structured rejection')
    from facility_studio.equipment_io import Cell
    from facility_studio.equipment_analysis import analyze_equipment
    from facility_studio.equipment_schema import SCHEMA_ID
    for key,bad_cell in [('power',Cell('=1+1',formula=True)),('usage',Cell('nan')),('quantity',Cell(1.5))]:
        vals=dict(enabled=Cell(1),id=Cell('AUDIT'),name=Cell('Synthetic'),power=Cell(10),voltage=Cell(380),phases=Cell('3'))
        vals[key]=bad_cell
        try:analyze_equipment(dict(schema_id=SCHEMA_ID,source_name='bad.csv',records=[dict(system='電力',row=6,cells=vals)]));rejected=False
        except ValidationError:rejected=True
        a.check('equipment-reject/'+key,rejected,expected='row/column error')


def legacy_example(unit):
    """Reproduce the v1 ledger saved by the original native Windows audit.

    The 55.945 kW baseline is the historical error, not a current conversion.
    Retaining this literal catches accidental silent migration of saved values.
    """
    from .contributions import empty_ledger, equipment_contribution
    p = empty_power_inputs()
    schedule = electrical_schedule()
    entry = equipment_contribution(schedule, schedule['groups'][0], p['inputs'])
    original = dict(e_up_eq='100', u_e_up_eq=unit, e_up_pf_mode='沿用共用 PF',
                    e_up_pf='0.85', e_up_design_floor='0', e_up_type='一般負載', e_length_m='30')
    adopted = dict(e_up_eq='65.9452410844747', u_e_up_eq='kW', e_up_pf_mode='本盤獨立 PF',
                   e_up_pf='0.85', e_up_design_floor='142.87462133714', e_up_type='一般負載', e_length_m='30')
    ledger = empty_ledger()
    ledger.update(version=1, entries={entry['id']: entry}, original=original,
                  baseline={'e_up_eq': 55.94524108447474}, last_updates=adopted)
    del ledger['power_basis']  # The original native-audit files predate this snapshot.
    p['inputs'].update(adopted)
    return p, ledger, entry


def boundary_checks(a):
    from . import i18n
    from .contributions import (empty_ledger, equipment_contribution, updated_ledger,
                                removed_ledger, legacy_power_keys, aggregate_ledger, validate_ledger)
    from .engine import calculate, electrical_from_inputs
    from .errors import ValidationError
    from .html_report import html_report
    from .quick_tools import UNITS, convert_all
    from .reports import report, executive_summary
    from .simple_engines import calculate_tool
    from .simple_reports import tool_report
    from .simple_schema import defaults
    from .schema import FIELDS

    language = i18n.language()
    try:
        for lang in ('zh-Hant', 'en'):
            for k in (0, 4, 20, 100):
                inputs = dict(defaults('water'), k_sum=str(k))
                result = calculate_tool('water', inputs)
                for form, text in (('txt', tool_report(result, inputs, language=lang)),
                                   ('html', html_report(result, language=lang))):
                    a.check(f'F01 {lang}/{form}/K{k}', f'ΣK={k:g}' in str(text), text, k, 'F01')
            inputs = dict(defaults('electrical'), power='200', kind='一般設備')
            result = calculate_tool('electrical', inputs)
            row = executive_summary(result)[-1]
            a.check(f'F02 200kW {lang} same circuit', result['recommended_breaker_at'] == result['selected']['nfb_a'] == 400,
                    result['selected'], 400, 'F02')
            for power in ('0',):
                result = calculate_tool('electrical', dict(inputs, power=power))
                row = executive_summary(result)[-1]
                a.check(f'F02 no invented candidate {lang}/{power}', result['selected'] is None
                        and result['recommended_breaker_at'] is None and '400 AT' not in row['selection'], row, issue='F02')
            try:
                calculate_tool('electrical', dict(inputs, power='100000'))
                rejected = False
            except ValidationError:
                rejected = True
            a.check(f'F02 oversized circuit {lang} rejects without a candidate', rejected, issue='F02')

        # More than one seasonal/unit-size boundary, including FCU airflow control.
        for kind in ('RCU', 'FCU'):
            for solar in (0, 50, 100, 200):
                for capacity in (1, 5, 30):
                    for rt_unit in FIELDS['rt_type']['options']:
                        p = rcu_project(solar)
                        p['inputs'].update(sys_type=next(x for x in FIELDS['sys_type']['options'] if x.startswith(kind)),
                                           en_rcu_rt=str(capacity), fcu_rt=str(capacity), rt_type=rt_unit)
                        r = calculate(p)
                        summer = sum(r['summer'][t]['water_kw'] for t in ('c1', 'c2'))
                        winter = sum(r['winter'][t]['water_kw'] for t in ('c1', 'c2'))
                        cooling_count = max(summer, winter) * r['sf'] / (capacity * r['rt_kw'])
                        if kind == 'FCU':
                            airflow_count = r['supply_room_cmh'] / float(p['inputs']['en_fcu_cmh'])
                            cooling_count = max(cooling_count, airflow_count)
                        expected = math.ceil(cooling_count - 1e-12)
                        name = f'F04 peak season/{kind}/{solar}/{capacity}/{rt_unit}'
                        a.check(name, r['counts'][kind] == expected, r['counts'][kind], expected, 'F04')
                        a.near(name + '/basis', r['terminal_cooling_kw'], max(summer, winter), 'F04')
                        for lang in ('zh-Hant', 'en'):
                            text = str(report(r, language=lang))
                            marker = '末端冷卻選型基準' if lang == 'zh-Hant' else 'Terminal cooling selection basis'
                            a.check(name + '/report/' + lang, marker in text, text[-1200:], marker, 'F04')

        schedule = electrical_schedule()
        for pan, untouched, matched in (('UP', 'e_up_oven', 'e_up_eq'), ('NP', 'e_np_pump', 'e_np_exh')):
            for key in (untouched, matched):
                for unit, value, expected in (('W', 100, .1), ('kVA', 100, 85), ('kW', 85, 85),
                                               ('HP', 85 * .9 / .745699871582, 85),
                                               ('A', 85 * 1000 / (math.sqrt(3) * 380 * .85), 85)):
                    p = empty_power_inputs()
                    inputs = p['inputs']
                    inputs.update({key: str(value), 'u_' + key: unit})
                    entry = equipment_contribution(schedule, schedule['groups'][0], inputs, pan)
                    ledger = empty_ledger()
                    if key == matched:
                        ledger['baseline'][key] = expected
                    ledger, updates, summary = updated_ledger(ledger, entry, inputs)
                    current = dict(inputs, **updates)
                    prefix = f'F03 {pan}/{key}/{unit}'
                    a.near(prefix + '/adopt', electrical_from_inputs(current)[pan]['kw'], expected + 10, 'F03')
                    ledger, updates, _ = updated_ledger(ledger, entry, current)
                    current.update(updates)
                    a.near(prefix + '/same ID replaces', electrical_from_inputs(current)[pan]['kw'], expected + 10, 'F03')
                    current.update(e_pf='.95', e_eff='.7')
                    ledger, updates, _ = updated_ledger(ledger, entry, current)
                    current.update(updates)
                    a.near(prefix + '/changed shared PF and eta cannot reinterpret adopted base',
                           electrical_from_inputs(current)[pan]['kw'], expected + 10, 'F03')
                    a.near(prefix + '/changed shared PF retains reactive current basis',
                           electrical_from_inputs(current)[pan]['current_a'], (expected + 10) * 1000 / (math.sqrt(3) * 380 * .85), 'F03')
                    _, updates, _ = removed_ledger(ledger, entry['id'], current)
                    current.update(updates)
                    a.check(prefix + '/remove restores original units', all(current[k] == inputs[k] for k in updates), issue='F03')

        # A different source PF must preserve both real and reactive base power.
        for mode in ('沿用共用 PF', '本盤獨立 PF'):
            p = empty_power_inputs()
            inputs = p['inputs']
            inputs.update(e_up_oven='100', u_e_up_oven='kVA', e_pf='.7', e_up_pf='.95', e_up_pf_mode=mode)
            base_pf = .95 if mode == '本盤獨立 PF' else .7
            entry = equipment_contribution(schedule, schedule['groups'][0], inputs)
            ledger, updates, _ = updated_ledger(empty_ledger(), entry, inputs)
            result = electrical_from_inputs(dict(inputs, **updates))['UP']
            expected_p = 100 * base_pf + 10
            expected_q = 100 * math.sqrt(1 - base_pf ** 2) + 10 * math.tan(math.acos(.85))
            a.near('F03 PF real power/' + mode, result['kw'], expected_p, 'F03')
            a.near('F03 PF vector current/' + mode, result['current_a'], math.hypot(expected_p, expected_q) * 1000 / (math.sqrt(3) * 380), 'F03')
        # UP and NP may first adopt at different common PF/efficiency settings.
        p = empty_power_inputs()
        inputs = p['inputs']
        inputs.update(e_up_oven='100', u_e_up_oven='kVA', e_np_pump='100', u_e_np_pump='kVA')
        entry_up = equipment_contribution(schedule, schedule['groups'][0], inputs, 'UP')
        ledger, updates, _ = updated_ledger(empty_ledger(), entry_up, inputs)
        inputs.update(updates)
        inputs['e_pf'] = '.7'
        entry_np = equipment_contribution(schedule, schedule['groups'][0], inputs, 'NP')
        ledger, updates, _ = updated_ledger(ledger, entry_np, inputs)
        inputs.update(updates)
        for entry in (entry_up, entry_np):
            ledger, updates, _ = updated_ledger(ledger, entry, inputs)
            inputs.update(updates)
        a.near('F03 each panel retains its own adoption basis/UP', electrical_from_inputs(inputs)['UP']['kw'], 95, 'F03')
        a.near('F03 each panel retains its own adoption basis/NP', electrical_from_inputs(inputs)['NP']['kw'], 80, 'F03')

        for unit in ('W', 'kVA'):
            p, ledger, entry = legacy_example(unit)
            before = copy.deepcopy(ledger)
            a.check('F03 legacy identified/' + unit, legacy_power_keys(validate_ledger(ledger)) == ['e_up_eq'], issue='F03')
            a.check('F03 legacy pending/' + unit, bool(aggregate_ledger(ledger, p['inputs'])['pending']), issue='F03')
            try:
                updated_ledger(ledger, entry, p['inputs'])
                rejected = False
            except ValidationError as exc:
                rejected = exc.code == 'legacy_power_adoption'
            a.check('F03 legacy cannot silently re-adopt/' + unit, rejected and ledger == before, issue='F03')
            restored, updates, _ = removed_ledger(ledger, entry['id'], p['inputs'])
            current = dict(p['inputs'], **updates)
            a.check('F03 legacy remove restores raw original/' + unit, current['e_up_eq'] == '100'
                    and current['u_e_up_eq'] == unit and not legacy_power_keys(restored) and restored['version'] == 2, issue='F03')
            # A v1 non-kW value intentionally replaced (no retained baseline) was never affected.
            safe = copy.deepcopy(ledger)
            safe['baseline']['e_up_eq'] = 0
            a.check('F03 legacy replacement is safe/' + unit, not legacy_power_keys(safe), issue='F03')

        # Decimal reference avoids repeating floating-point intermediate overflow.
        limit = Decimal.from_float(sys.float_info.max)
        for category, units in UNITS.items():
            if category == '溫度':
                continue
            for unit, factor in units.items():
                for value in ('0', '1', '-1', '12345.6789', '1e308', '-1e308'):
                    expected = {u: Decimal(value) * Decimal(str(factor)) / Decimal(str(f)) for u, f in units.items()}
                    fits = all(abs(v) <= limit for v in expected.values())
                    name = f'F06 finite conversion/{category}/{unit}/{value}'
                    try:
                        result = convert_all(category, value, unit)
                    except ValidationError as exc:
                        a.check(name, not fits and exc.code == 'overflow' and exc.field_name == 'value', exc.code, fits, 'F06')
                    else:
                        a.check(name, fits and all(math.isfinite(x) for x in result.values()), result, fits, 'F06')
                        for target, reference in expected.items():
                            a.near(name + '/' + target, result[target], float(reference), 'F06', tolerance=1e-12)
        for unit, valid in (('°F', True), ('°C', False), ('K', False)):
            try:
                values = convert_all('溫度', '1e308', unit)
            except ValidationError as exc:
                a.check('F06 temperature overflow/' + unit, not valid and exc.code == 'overflow', issue='F06')
            else:
                a.check('F06 representable large Fahrenheit', valid and all(math.isfinite(x) for x in values.values()), issue='F06')
        a.near('F06 absolute zero', convert_all('溫度', '-459.67', '°F')['K'], 0, 'F06')
        a.near('F06 alias temperature difference', convert_all('溫差', 9, '°F差')['K'], 5, 'F06')
        a.near('F06 alias valve coefficient', convert_all('Kv/Cv', 1, 'Cv(US)')['Kv'], .865, 'F06')
    finally:
        i18n.set_language(language, persist=False)


def run_checks():
    with tempfile.TemporaryDirectory(prefix='facility-audit-') as directory:
        a = _Checks(Path(directory))
        pure_checks(a)
        boundary_checks(a)
        return a.checks


def run_ui(root, app, main, check, pump, output=None):
    """Run real trace, confirmation, source removal and workspace round trips."""
    from . import i18n
    from .contributions import empty_ledger, equipment_contribution, legacy_power_keys
    from .engine import electrical_from_inputs
    from .utils import project_hash
    from .workspace_store import new_workspace, read_workspace

    original = copy.deepcopy(main.session_snapshot())
    original_path, original_saved, original_hash = main.path, main.saved_workspace_hash, main.saved_hash
    language, current, scope = i18n.language(), app.current, main.task_scope.get()
    dialogs = []

    def near(a, b):
        return math.isfinite(a) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    def remove_source(ident):
        existing = set(main.root.winfo_children())
        main.open_demand_ledger()
        win = next(w for w in main.root.winfo_children() if w not in existing and w.winfo_class() == 'Toplevel')
        try:
            tree = next(w for w in descendants(win) if w.winfo_class() == 'Treeview')
            tree.selection_set(ident)
            button = next(w for w in descendants(win) if w.winfo_class() == 'TButton'
                          and str(w.cget('text')) in ('移除選取來源的需求', 'Remove selected demand source'))
            button.invoke()
            pump()
            return ident not in main.demand_ledger['entries']
        finally:
            win.destroy()

    try:
        with tempfile.TemporaryDirectory(prefix='facility-audit-ui-') as directory, \
             patch('facility_studio.workspace_view.messagebox.askokcancel', return_value=True), \
             patch('facility_studio.workspace_view.messagebox.showerror', side_effect=lambda *x, **k: dialogs.append(str(x))):
            for lang in ('zh-Hant', 'en'):
                i18n.set_language(lang, persist=False)
                app.show_tool('pumps')
                page = app.active_page()
                for flow in (0, 100, 1234.5):
                    page.reset()
                    page.variables['flow'].set(str(flow))
                    page.calculate()
                    power = page.result['motor_input_kw']
                    for unit in ('m³/h', 'US GPM', 'LPM', 'US GPM', 'LPM'):
                        page.variables['flow_unit'].set(unit)
                        page.calculate()
                        pump()
                        check(f'F05 {lang}/{flow}/{unit} preserves physical flow and motor input',
                              lambda: page.result is not None and near(page.result['flow_lpm'], flow)
                              and near(page.result['motor_input_kw'], power))
                page.variables['flow'].set('invalid draft')
                page.variables['flow_unit'].set('m³/h')
                page.calculate()
                check(f'F05 {lang} invalid draft clears prior results', lambda: page.result is None)

                app.show_tool('units')
                page = app.active_page()
                page.reset()
                page.variables['category'].set('壓力')
                page.variables['unit'].set('bar')
                page.variables['value'].set('1e308')
                page.calculate()
                pump()
                check(f'F06 {lang} overflow clears output', lambda: page.result is None)
                page.variables['value'].set('1')
                page.calculate()
                check(f'F06 {lang} correction restores finite output', lambda: page.result is not None
                      and all(math.isfinite(v) for v in page.result['values'].values()))

                schedule = electrical_schedule()
                for pan, key in (('UP', 'e_up_eq'), ('NP', 'e_np_exh')):
                    for unit, expected in (('kVA', 95), ('W', 10.1)):
                        p = empty_power_inputs()
                        p['inputs'].update({key: '100', 'u_' + key: unit})
                        main.apply_workspace(new_workspace(p))
                        main.recalculate()
                        entry = equipment_contribution(schedule, schedule['groups'][0], main.snapshot()['inputs'], pan)
                        prefix = f'F03 {lang}/{pan}/{unit}'
                        with patch('facility_studio.session_controller.messagebox.askyesnocancel', return_value=True):
                            check(prefix + ' adopt retains baseline', lambda: main.apply_contribution(entry))
                            pump()
                            check(prefix + ' physical panel demand', lambda: near(electrical_from_inputs(main.snapshot()['inputs'])[pan]['kw'], expected))
                            check(prefix + ' update same ID', lambda: main.apply_contribution(entry))
                        path = Path(directory) / f'工作空間 {lang} {pan} {unit}.json'
                        check(prefix + ' save workspace', lambda: main.save_workspace(path))
                        main.apply_workspace(read_workspace(path), path)
                        main.recalculate()
                        check(prefix + ' reload retains exact physical demand', lambda: near(electrical_from_inputs(main.snapshot()['inputs'])[pan]['kw'], expected)
                              and main.demand_ledger['version'] == 2 and len(main.demand_ledger['entries']) == 1)
                        main.variables['e_pf'].set('.95')
                        main.variables['e_eff'].set('.7')
                        main.recalculate()
                        check(prefix + ' reload snapshot resists changed common PF and efficiency', lambda: main.apply_contribution(entry)
                              and near(electrical_from_inputs(main.snapshot()['inputs'])[pan]['kw'], expected))
                        check(prefix + ' remove using actual ledger button', lambda: remove_source(entry['id']))
                        check(prefix + ' removal restores original raw units', lambda: main.snapshot()['inputs'][key] == '100'
                              and main.snapshot()['inputs']['u_' + key] == unit)

                p = empty_power_inputs()
                p['inputs'].update(e_up_eq='100', u_e_up_eq='kVA')
                main.apply_workspace(new_workspace(p))
                entry = equipment_contribution(schedule, schedule['groups'][0], main.snapshot()['inputs'])
                before = project_hash(main.session_snapshot())
                with patch('facility_studio.session_controller.messagebox.askyesnocancel', return_value=None):
                    check(f'F03 {lang} cancelled adoption changes nothing', lambda: not main.apply_contribution(entry)
                          and before == project_hash(main.session_snapshot()))

                for unit, expected in (('W', 10.1), ('kVA', 95)):
                    p, ledger, entry = legacy_example(unit)
                    document = new_workspace(p)
                    document['demand_ledger'] = ledger
                    main.apply_workspace(document)
                    main.recalculate()
                    check(f'F03 {lang}/{unit} legacy error visibly fails quality', lambda: main.result['quality']['status'] == '未達條件'
                          and any(item['name'] == '舊版電力帶入需重建' and item['status'] == '未達' for item in main.result['quality']['items'])
                          and bool(legacy_power_keys(main.demand_ledger)))
                    before = project_hash(main.session_snapshot())
                    count = len(dialogs)
                    check(f'F03 {lang}/{unit} legacy cannot silently re-adopt', lambda: not main.apply_contribution(entry)
                          and before == project_hash(main.session_snapshot()) and len(dialogs) == count + 1)
                    dialogs.pop()
                    check(f'F03 {lang}/{unit} legacy original restored by removal', lambda: remove_source(entry['id'])
                          and main.snapshot()['inputs']['u_e_up_eq'] == unit and main.snapshot()['inputs']['e_up_eq'] == '100')
                    with patch('facility_studio.session_controller.messagebox.askyesnocancel', return_value=True):
                        check(f'F03 {lang}/{unit} legacy reimport adopts correct power', lambda: main.apply_contribution(entry)
                              and near(electrical_from_inputs(main.snapshot()['inputs'])['UP']['kw'], expected))
            check('F01–F06 no unexpected validation dialogs', lambda: not dialogs)
    finally:
        main.apply_workspace(original, original_path)
        main.saved_workspace_hash, main.saved_hash = original_saved, original_hash
        main.task_scope.set(scope)
        i18n.set_language(language, persist=False)
        for tool in ('pumps', 'units'):
            app.show_tool(tool)
            app.active_page().reset()
        app.show_tool(current)
        pump()
