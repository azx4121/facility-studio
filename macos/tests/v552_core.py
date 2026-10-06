"""Activation, physical invariants, and whole-document persistence contracts."""
from pathlib import Path
import sys, copy, json, tempfile, math
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.engine import calculate, read_project, pressure_result
from facility_studio.ahu_engine import nm_calculate
from facility_studio.schema import default_project, FIELDS, PD_DEFAULTS
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.field_state import main_inactive, ahu_inactive
from facility_studio.workspace_store import new_workspace, validate_workspace, read_workspace
from facility_studio.project_store import save_project_file
from facility_studio.design_workflow import ahu_requirement_updates, ahu_source_hash
from facility_studio.reports import report, nm_report
from facility_studio.utils import project_hash
checks = []
def check(name, ok, detail=''):
    checks.append(dict(name=name, passed=bool(ok), detail=detail))
def close(a, b):
    return math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9)

# Every inactive main field is blanked independently in four architectures.
for system in FIELDS['sys_type']['options']:
    p = default_project();p['inputs']['sys_type'] = system
    baseline = calculate(p)
    for key in main_inactive(p['inputs']):
        candidate = copy.deepcopy(p);candidate['inputs'][key] = ''
        try:
            r=calculate(candidate)
            check(system+':inactive:'+key, close(r['qs'],baseline['qs']) and close(r['summer']['mass'],baseline['summer']['mass']) and bool(report(r)))
        except Exception as e:
            check(system+':inactive:'+key,False,str(e))
# Inactive stage conditions also cover bypass / no humidification / electric-only.
for mode in ['循環水洗濕膜','電極式蒸汽','不加濕']:
    inp=dict(NM_DEFAULTS);inp['humidifier']=mode;inp['summer_c1_mode']='旁通';inp['h1_source']='電熱'
    baseline=nm_calculate(inp)
    for key in ahu_inactive(inp):
        candidate=dict(inp);candidate[key]=''
        try:
            r=nm_calculate(candidate)
            check(mode+':inactive:'+key,close(r['summer']['mass'],baseline['summer']['mass']) and bool(nm_report(r)))
        except Exception as e:check(mode+':inactive:'+key,False,str(e))
# Reactivation must expose the original bad draft, not silently substitute a default.
p=default_project();p['inputs'].update(sys_type=FIELDS['sys_type']['options'][1],en_dcc_rt='')
calculate(p);p['inputs']['sys_type']=FIELDS['sys_type']['options'][0]
try:calculate(p);check('reactivate_invalid_DCC',False)
except ValueError as e:check('reactivate_invalid_DCC',getattr(e,'field_name',None)=='en_dcc_rt')

for mode, extra in [('簡易估算',{'elbows':'bad','rate':'bad','sum_k':'bad'}),('詳細計算',{'fitting_mode':'直接 K 值','elbows':'bad','sum_k':'2'})]:
    for boundary,static in [('閉式循環','8'),('閉式循環','bad'),('開式系統','8')]:
        c={**PD_DEFAULTS,**extra,'estimate_mode':mode,'boundary':boundary,'static_m':static,'equipment_known':'尚無資料（不含設備）','equipment_drop':'bad'}
        try:
            r=pressure_result(c,.002,.05,math.pi*.05**2/4,1,1000,.001,.045)
            check('pressure:'+mode+boundary+static,close(r['static_pa'],0 if boundary=='閉式循環' else 1000*9.80665*8) and not r['equipment_included'])
            check('pressure_sum:'+mode+boundary+static,close(r['total_pa'],r['friction_pa']+r['local_pa']+r['equipment_pa']+r['static_pa']))
        except Exception as e:check('pressure:'+mode+boundary+static,False,str(e))

p=default_project();p['inputs']['sys_type']=FIELDS['sys_type']['options'][0];r=calculate(p);original=ahu_requirement_updates(r)['linked_main_hash']
for key,value,stable in [('project_name','另一份案名',True),('e_np_fan','52',True),('light_lux','850',True),('ra_t','23',False),('oa_t','36',False)]:
    alt=copy.deepcopy(p);alt['inputs'][key]=value
    check('boundary_scope:'+key,(ahu_requirement_updates(calculate(alt))['linked_main_hash']==original)==stable)
base=ahu_source_hash(NM_DEFAULTS)
for key,value,stable in [('name','設備乙',True),('summer_h1_t','55',True),('fan_unit_kw','5',False)]:
    alt={**NM_DEFAULTS,key:value};check('AHU_source_scope:'+key,(ahu_source_hash(alt)==base)==stable)

with tempfile.TemporaryDirectory() as td:
    d=new_workspace(p);d['ahus']=[dict(id='AHU1',inputs={**NM_DEFAULTS,'steam_kw':''},source_project_id=d['project_id'])]
    d['comparisons']={'A':r};d['main']['inputs']['oa_t']=''
    path=Path(td)/'整案.json';save_project_file(path,validate_workspace(d))
    check('save_invalid_main_and_AHU_drafts',read_workspace(path)==d)
    d['main']=p;save_project_file(path,d)
    check('CLI_reads_main_inside_workspace',read_project(path)==p)
    check('previous_file_backup_exists',path.with_suffix('.json.bak').exists())
    for field,bad in [('qs','NaN'),('summer',{}),('hash','wrong')]:
        corrupt=copy.deepcopy(d);corrupt['comparisons']['A'][field]=bad
        try:validate_workspace(corrupt);check('reject_corrupt_AB:'+field,False)
        except ValueError:check('reject_corrupt_AB:'+field,True)
(ROOT/'evidence/V552_Core_Checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
failed=[x for x in checks if not x['passed']]
print(json.dumps(dict(checks=len(checks),failed=failed),ensure_ascii=False,indent=2))
assert not failed
