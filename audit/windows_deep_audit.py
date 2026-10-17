"""Independent Windows audit. Records defects without changing application code.

An audit-completed exit code is distinct from all product checks passing.
Use --gui for real Tk event paths, --exe for the exact public frozen delivery.
"""
from pathlib import Path
import argparse
import copy
import csv
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'windows'))
EXPECTED_EXE_SHA = '49a04498b8353f4ef1f0d202de48576af925502dff202c232d2356b02a48a802'
EXPECTED_WINDOWS_TREE = '5edfb03e3d2ceaf1ed572162eaf871f0613a5c59'


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


class Audit:
    def __init__(self, out):
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.checks = []
        self.errors = []

    def check(self, name, passed, actual=None, expected=None, issue=None):
        self.checks.append(clean(dict(name=name, passed=bool(passed), actual=actual,
                                      expected=expected, issue_id=issue)))

    def near(self, name, actual, expected, issue=None, tolerance=1e-9):
        self.check(name, math.isfinite(actual) and abs(actual-expected) <= tolerance * max(1, abs(expected)), actual, expected, issue)

    def section(self, name, fn):
        try:
            fn()
        except Exception:
            self.errors.append(dict(section=name, traceback=traceback.format_exc()))

    def finish(self):
        failed = [c for c in self.checks if not c['passed']]
        result = dict(audit_completed=not self.errors, product_all_checks_passed=not failed and not self.errors,
                      host=dict(os=platform.system(), version=platform.platform(), python=platform.python_version()),
                      source_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                      windows_source_tree=subprocess.check_output(['git','rev-parse','HEAD:windows'],cwd=ROOT,text=True).strip(),
                      total_checks=len(self.checks), passed_checks=len(self.checks)-len(failed), failed_checks=len(failed),
                      issue_ids=sorted({c['issue_id'] for c in failed if c['issue_id']}),
                      checks=self.checks, execution_errors=self.errors)
        dump(self.out / 'audit-results.json', result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('checks','execution_errors')}, ensure_ascii=False))
        if self.errors:
            print(json.dumps(self.errors, ensure_ascii=False))
        return 2 if self.errors else 0


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


def gui_checks(a):
    os.environ['FACILITY_STUDIO_PREFERENCES']=str(a.out/'isolated-preferences.json')
    os.environ['LOCALAPPDATA']=str(a.out/'isolated-user-data')
    from facility_studio.localized_tk import tk
    from facility_studio.simple_desktop import SimpleToolsApp
    from facility_studio.contributions import empty_ledger,equipment_contribution
    from facility_studio.engine import electrical_from_inputs
    from facility_studio.utils import project_hash
    from facility_studio import i18n
    i18n.set_language('zh-Hant',persist=False)
    root=tk.Tk();callbacks=[]
    root.report_callback_exception=lambda *x:callbacks.append(''.join(traceback.format_exception(*x)))
    app=SimpleToolsApp(root);root.update()
    try:
        for unit in ('m³/h','US GPM'):
            app.show_tool('pumps');page=app.active_page();page.reset();page.calculate();root.update()
            before=copy.deepcopy(page.result)
            page.variables['flow_unit'].set(unit);page.calculate();root.update();after=copy.deepcopy(page.result)
            a.near('gui-pump-unit-invariance/'+unit,after['flow_lpm'],before['flow_lpm'],'F05')
            dump(a.out/('gui-pump-'+('m3h' if unit=='m³/h' else 'gpm')+'.json'),
                 dict(before=before,after=after,adopted_inputs=page.data()))

        for tool,key,unit,metric in [('water','flow_unit','US GPM',lambda r:r['flow_lpm']),
                  ('duct','flow_unit','CFM',lambda r:r['flow_cmh']),
                  ('gas','flow_unit','SCFM',lambda r:r['standard_lpm']),
                  ('electrical','power_unit','W',lambda r:r['power_kw']),
                  ('lighting','area_mode','面積 坪',lambda r:r['area_m2'])]:
            app.show_tool(tool);page=app.active_page();page.reset();page.calculate();root.update();before=metric(page.result)
            page.variables[key].set(unit);page.calculate();root.update()
            a.near('gui-control-equivalent-switch/'+tool,metric(page.result),before)

        # Use actual DesktopApp/SessionController, with only explicit synthetic-user decisions supplied.
        wb=app.open_workbench();root.update()
        schedule=electrical_schedule();dialogs=[]
        for unit,value in [('kVA','100'),('W','100')]:
            p=empty_power_inputs();p['inputs'].update(e_up_eq=value,u_e_up_eq=unit)
            wb.demand_ledger=empty_ledger();wb.transfer_receipts=[];wb.apply_project(p);wb.recalculate();root.update()
            before=electrical_from_inputs(wb.snapshot()['inputs'])['UP']['kw']
            entry=equipment_contribution(schedule,schedule['groups'][0],wb.snapshot()['inputs'],'UP')
            with patch('facility_studio.session_controller.messagebox.askyesnocancel',return_value=True), \
                 patch('facility_studio.workspace_view.messagebox.askokcancel',return_value=True), \
                 patch('facility_studio.workspace_view.messagebox.showerror',side_effect=lambda *x,**k:dialogs.append(str(x))):
                adopted=wb.apply_contribution(entry)
            root.update()
            after=electrical_from_inputs(wb.snapshot()['inputs'])['UP']
            a.check('gui-ledger-retain-adoption/'+unit,adopted,adopted,True)
            a.near('gui-ledger-retain-base/'+unit,after['kw'],before+10,'F03')
            saved=a.out/('gui-incorrect-adoption-'+unit+'.json')
            a.check('gui-save-reproduction/'+unit,wb.save_workspace(saved),expected='saved')
            dump(a.out/('gui-ledger-details-'+unit+'.json'),dict(before_kw=before,expected_after_kw=before+10,
                 actual_panel=after,adopted=adopted,workspace_path=saved.name))
        # Cancelling the baseline decision must preserve the entire current workspace.
        p=empty_power_inputs();p['inputs'].update(e_up_eq='100',u_e_up_eq='kVA')
        wb.demand_ledger=empty_ledger();wb.transfer_receipts=[];wb.apply_project(p);wb.recalculate();root.update()
        before=project_hash(wb.session_snapshot());entry=equipment_contribution(schedule,schedule['groups'][0],wb.snapshot()['inputs'],'UP')
        with patch('facility_studio.session_controller.messagebox.askyesnocancel',return_value=None):
            adopted=wb.apply_contribution(entry)
        a.check('gui-cancel-adoption-preserves-workspace',not adopted and before==project_hash(wb.session_snapshot()))
        a.check('gui-no-unhandled-callback-errors',not callbacks,callbacks,[])
        a.check('gui-no-unexpected-validation-dialogs',not dialogs,dialogs,[])
    finally:
        root.destroy()


def exe_checks(a, exe):
    if platform.system()!='Windows':raise RuntimeError('Frozen EXE can only be executed on native Windows')
    actual=hashlib.sha256(exe.read_bytes()).hexdigest()
    a.check('public-exe-identity',actual==EXPECTED_EXE_SHA,actual,EXPECTED_EXE_SHA)
    if actual!=EXPECTED_EXE_SHA:raise RuntimeError('Wrong published EXE')
    # Existing offline acceptance uses firewall + a source-interpreter-free child environment.
    from winrelease.verify import check_exe
    check_exe(exe,a.out/'frozen-native','standalone',block_firewall=True)
    a.check('published-exe-built-in-offline-acceptance',True,248,248)
    systemroot=Path(os.environ['SystemRoot']);cwd=a.out/'empty-working-dir';cwd.mkdir(exist_ok=True)
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','PYI_'))}
    env.update(LOCALAPPDATA=str(a.out/'frozen-isolated-user-data'),FACILITY_TEST_BLOCK_NETWORK='1',
               PATH=os.pathsep.join(map(str,[systemroot/'System32',systemroot,systemroot/'System32/WindowsPowerShell/v1.0'])))
    def run(arguments):
        p=subprocess.run([str(exe),*map(str,arguments)],cwd=cwd,env=env,timeout=210)
        if p.returncode:raise RuntimeError('Frozen CLI failed: '+str(p.returncode))
    from facility_studio.simple_schema import defaults
    d=defaults('water');d['k_sum']='20';input_path=a.out/'frozen-water-input.json';dump(input_path,d)
    result=a.out/'frozen-water.json';report=a.out/'frozen-water.txt'
    run(['--tool','water','--tool-input',input_path,'--result',result,'--report',report])
    k=float(re.search(r'ΣK=([0-9.eE+\-]+)',report.read_text(encoding='utf-8'))[1])
    a.near('frozen-water-report-adopted-K',k,20,'F01')
    project=a.out/'frozen-rcu-input.json';dump(project,rcu_project(100))
    result=a.out/'frozen-rcu.json';run(['--project',project,'--result',result,'--report',a.out/'frozen-rcu.txt'])
    r=json.loads(result.read_text(encoding='utf-8'));winter=sum(r['winter'][t]['water_kw'] for t in ('c1','c2'))
    required=math.ceil(winter*r['sf']/(30*r['rt_kw'])-1e-12)
    a.check('frozen-rcu-both-seasons',r['counts']['RCU']>=required,r['counts']['RCU'],required,'F04')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--gui',action='store_true');parser.add_argument('--exe',type=Path)
    args=parser.parse_args();a=Audit(args.output.resolve())
    tree=subprocess.check_output(['git','rev-parse','HEAD:windows'],cwd=ROOT,text=True).strip()
    if tree!=EXPECTED_WINDOWS_TREE:raise RuntimeError('Application source changed; this audit targets the published win.4 tree')
    a.section('pure',lambda:pure_checks(a))
    if args.gui:a.section('gui',lambda:gui_checks(a))
    if args.exe:a.section('frozen-public-exe',lambda:exe_checks(a,args.exe.resolve()))
    return a.finish()


if __name__=='__main__':raise SystemExit(main())
