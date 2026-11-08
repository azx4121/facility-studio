"""Adversarial v22 contract derived from preserved v21 before implementation review.

Headless Linux source tests, not native/product/electrical approval. Preserved
numeric fixtures bind the independent frozen v21 identity. No table replacement.
"""
import copy, hashlib, inspect, json, math, os, re, sys
from pathlib import Path
from types import SimpleNamespace
import pytest

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('FACILITY_SOURCE_TREE',Path(__file__).resolve().parents[1])).resolve()
PLATFORM=os.environ['FACILITY_TEST_PLATFORM']
sys.path.insert(0,str(ROOT/PLATFORM))
from facility_studio import i18n
from facility_studio.simple_engines import electrical,calculate_tool
from facility_studio.simple_schema import defaults
from facility_studio.simple_reports import presentation,tool_report,pipeline_report
from facility_studio.engine import electrical_from_inputs,calculate
from facility_studio.reports import executive_summary,report
from facility_studio.html_report import html_report
from facility_studio.quick_tools import electrical_quick
from facility_studio.tools_view import result_text
from facility_studio.display_helpers import engineering_result_rows
from facility_studio.equipment_analysis import analyze_equipment,equipment_report,group_metrics
from facility_studio.equipment_io import Cell
from facility_studio.equipment_schema import SCHEMA_ID
from facility_studio.contributions import equipment_contribution
from facility_studio.errors import ValidationError

assert Path(inspect.getfile(electrical)).resolve().is_relative_to(ROOT/PLATFORM)
RESOURCES=HERE/'independent_ampacity_resources'
FIXTURE_MANIFEST=json.loads((RESOURCES/'fixture_manifest.json').read_text())
assert FIXTURE_MANIFEST['baseline_inventory_sha256']=='03237baf958aa78e27f8789ffa4dcda50592fca26fbaf3893cf8049da0b66ee9'
for artifact in FIXTURE_MANIFEST['files']:
 assert hashlib.sha256((RESOURCES/artifact['path']).read_bytes()).hexdigest()==artifact['sha256'],artifact['path']
FIX=json.loads((RESOURCES/(PLATFORM+'-v21-independent-fixture.json')).read_text())
SIMPLE={c['id']:c for c in FIX['simple']};MAIN={c['id']:c for c in FIX['main']}
BLOCKED='blocked_unverified_ampacity_basis';ZERO='no_electrical_load'
SAFE_SIMPLE=('input_value','power_value','power_unit','power_kw','eta','motor_efficiency','shaft_kw','electrical_input_kw','equivalent_hp','apparent_kva','power_w','equivalents','supply','phases','voltage','pf','current_a','design_a','design_breaker_a','kind','length_m','insulation','ambient_c','loaded_conductors','drop_limit_pct','dt','dp','terminal_c','drop_basis','formula')
SAFE_MAIN=('kw','hp','kind','current_a','design_current_a','design_breaker_a','voltage','pf','eff','ambient_c','dt','dp','largest_hp','has_motor')
PENDING=re.compile(r'待核|待選|未核實|受限|暫停|隔離|pending|unverified|restricted|suspend|quarantin',re.I)
BAD_SIZING=re.compile(r'(?:300\s*AT|250(?:[.]0+)?\s*mm[²2]|PE[^\n<>]{0,35}\b22\s*mm[²2]|22\s*mm[²2][^\n<>]{0,35}PE)',re.I)
FALSE_ZERO=re.compile(r'無(?:用電)?需求|無電氣負載|no (?:electrical )?(?:load|demand)',re.I)

def pending(text):
 text=str(text)
 assert PENDING.search(text),text[:1500]
 assert not BAD_SIZING.search(text),text[:2000]
 assert not FALSE_ZERO.search(text),text[:2000]

def render_simple(result,route,language):
 if route=='presentation':
  cards,details=presentation(result);value='\n'.join(map(str,cards+details))
 elif route=='display':value=str(engineering_result_rows(result))
 elif route=='summary':value=str(executive_summary(result))
 elif route=='txt':return tool_report(result,SIMPLE['boundary']['data'],language=language)
 elif route=='html':return html_report(result,language=language)
 elif route=='pipeline-txt':return pipeline_report({'pipeline':{'electrical':result,'adopted_inputs':{'electrical':SIMPLE['boundary']['data']}}},language=language)
 elif route=='pipeline-html':return html_report({'pipeline':{'electrical':result,'adopted_inputs':{'electrical':SIMPLE['boundary']['data']}}},language=language)
 return i18n.translate(value,language)

@pytest.mark.parametrize('case',FIX['simple'],ids=lambda c:c['id'])
def test_fresh_simple_quarantines_and_preserves_demands(case):
 data=copy.deepcopy(case['data']);before=copy.deepcopy(data)
 actual=electrical(data,**case.get('options',{}));old=case['result']
 assert {k:actual[k] for k in SAFE_SIMPLE}=={k:old[k] for k in SAFE_SIMPLE}
 assert actual['selected'] is None and actual['recommended_breaker_at'] is None
 expected=ZERO if old['power_kw']==old['current_a']==old['design_a']==0 else BLOCKED
 assert actual.get('selection_status')==expected
 assert data==before

@pytest.mark.parametrize('case',FIX['main'],ids=lambda c:c['id'])
def test_main_panels_quarantine_without_replacing_loads_or_manual_inputs(case):
 data=copy.deepcopy(case['data']);before=copy.deepcopy(data)
 actual=electrical_from_inputs(data)
 for key,old in case['result'].items():
  panel=actual[key]
  assert {k:panel[k] for k in SAFE_MAIN}=={k:old[k] for k in SAFE_MAIN}
  assert panel['selected'] is None
  expected=ZERO if old['kw']==old['current_a']==old['design_current_a']==0 else BLOCKED
  assert panel.get('selection_status')==expected
  if expected==BLOCKED:assert panel.get('candidate_count') is None
 assert data==before

@pytest.mark.parametrize('flags',[{'ampacity_verified':True},{'allow_unverified':True},{'table_verified':True},{'engineering_approved':True},{'selection_status':'verified'},{'nfb_finalized':True},{'user_confirmed':True}])
def test_user_flags_never_unlock_simple_or_main(flags):
 data=dict(SIMPLE['boundary']['data'],**flags)
 assert electrical(data)['selected'] is None
 data=dict(MAIN['boundary']['data'],**flags)
 assert all(p['selected'] is None for p in electrical_from_inputs(data).values())

@pytest.mark.parametrize('route',['presentation','display','summary','txt','html','pipeline-txt','pipeline-html'])
@pytest.mark.parametrize('language',['zh-Hant','en'])
@pytest.mark.parametrize('legacy',[False,True])
def test_simple_routes_quarantine_fresh_and_unchanged_legacy(route,language,legacy):
 result=copy.deepcopy(SIMPLE['boundary']['result']) if legacy else electrical(SIMPLE['boundary']['data'])
 # Metadata cannot bless historical candidates. Numeric history remains intact.
 result.update(ampacity_verified=True,table_verified=True,selection_status='verified',warnings=[])
 before=copy.deepcopy(result)
 text=render_simple(result,route,language)
 pending(text)
 assert result==before
 if language=='en':assert not re.search(r'[\u3400-\u9fff]',str(text)),str(text)[:1500]

@pytest.mark.parametrize('field,value',[('power_kw',None),('power_kw',0),('current_a',None),('current_a',0),('design_a',None),('design_a',30)])
@pytest.mark.parametrize('route',['presentation','summary','txt','html'])
def test_unknown_or_positive_design_never_becomes_no_demand(field,value,route):
 result=copy.deepcopy(SIMPLE['zero']['result']);result[field]=value
 if value==0:result['design_a']=30
 before=copy.deepcopy(result)
 text=render_simple(result,route,'en');pending(text)
 assert result==before

@pytest.mark.parametrize('route',['presentation','summary','txt','html'])
def test_known_zero_is_explicit_and_has_no_sizing(route):
 result=electrical(SIMPLE['zero']['data'])
 text=render_simple(result,route,'en')
 assert FALSE_ZERO.search(str(text)),str(text)
 assert not BAD_SIZING.search(str(text))

@pytest.mark.parametrize('legacy',[False,True])
@pytest.mark.parametrize('language',['en','zh-Hant'])
@pytest.mark.parametrize('route',['txt','html','summary'])
def test_full_routes_hide_legacy_candidates_and_keep_hvac(legacy,language,route):
 r=copy.deepcopy(FIX['full_result']) if legacy else calculate(copy.deepcopy(FIX['full_input']))
 before=copy.deepcopy(r)
 if route=='txt':text=report(r,language=language)
 elif route=='html':text=html_report(r,language=language)
 else:text=i18n.translate(str(executive_summary(r)),language)
 assert PENDING.search(str(text)),str(text)[:1500]
 assert not BAD_SIZING.search(str(text)),str(text)[:1500]
 assert r==before
 if language=='en':assert not re.search(r'[\u3400-\u9fff]',str(text))


def test_full_result_unrelated_calculations_manual_inputs_and_ledger_unchanged():
 data=copy.deepcopy(FIX['full_input']);before=copy.deepcopy(data);r=calculate(data)
 old=FIX['full_result']
 for key,value in old.items():
  if key not in ('electric','warnings','quality'):assert json.loads(json.dumps(r[key]))==value,key
 # Only the explicitly electrical safety item changes; all other quality content stays.
 oldq=copy.deepcopy(old['quality']);newq=copy.deepcopy(r['quality'])
 olditems=oldq.pop('items');newitems=newq.pop('items');assert newq==oldq
 assert len(olditems)==len(newitems)
 for olditem,newitem in zip(olditems,newitems):
  if olditem['name']=='配電候選覆核':
   assert newitem['status']==olditem['status'] and PENDING.search(newitem['name']+newitem['detail'])
   assert {k:v for k,v in olditem.items() if k not in ('name','detail')}=={k:v for k,v in newitem.items() if k not in ('name','detail')}
  else:assert newitem==olditem
 assert data==before


def equipment():
 values=FIX['equipment_values'];imp={'schema_id':SCHEMA_ID,'source_name':'Synthetic independent safety test','records':[{'system':'電力','row':6,'cells':{k:Cell(value=v) for k,v in values.items()}}]}
 return analyze_equipment(imp)


def test_equipment_loads_group_handoff_and_original_inputs_survive():
 r=equipment();old=FIX['equipment_result']
 for group,previous in zip(r['groups'],old['groups']):
  for key,value in previous.items():
   if key not in ('candidate','warnings','basis','pending'):assert json.loads(json.dumps(group[key]))==value,key
  assert group['candidate']['selected'] is None
 handoff=equipment_contribution(r,r['groups'][0],MAIN['boundary']['data'],target='UP')
 from facility_studio.utils import project_hash
 assert handoff['source_hash']==project_hash(r['groups'][0])
 assert {k:v for k,v in handoff.items() if k!='source_hash'}=={k:v for k,v in FIX['equipment_handoff'].items() if k!='source_hash'}

@pytest.mark.parametrize('legacy',[False,True])
def test_equipment_report_and_group_metrics_never_recommend_history(legacy):
 r=copy.deepcopy(FIX['equipment_result']) if legacy else equipment();before=copy.deepcopy(r)
 pending(equipment_report(r));pending(str(group_metrics(r['groups'][0])))
 assert r==before

@pytest.mark.parametrize('power',[0,294])
def test_flat_quick_never_misrepresents_blocked_as_numeric_zero(power):
 r=electrical_quick(power,power_unit='A',pf=1,length=30,insulation='PVC')
 assert r['current_a']==power and r['design_a']==power
 assert r.get('selection_status')==(BLOCKED if power else ZERO)
 for key in ('nfb_a','wire_mm2','pe_mm2','runs','ampacity_a','drop_pct'):assert r[key] is None,(key,r)
 if power:pending(result_text(r))
 else:assert FALSE_ZERO.search(result_text(r))
 assert '無有限露點' not in result_text(r)

@pytest.mark.parametrize('tool',[x for x in FIX['non_electrical'] if 'result' in x],ids=lambda c:c['tool'])
def test_negative_control_other_tools_numerically_identical(tool):
 assert_negative_control_result(tool, json.loads(json.dumps(calculate_tool(tool['tool'],tool['data']))))

def assert_negative_control_result(tool, actual):
 # Exactly one documented portability allowance: binary64 CFM conversion for
 # this frozen 1000 CMH fixture. No other number, metadata, or shape is relaxed.
 expected = tool['result']
 if tool['tool'] == 'units' and tool['data'] == {'category':'風量','value':'1000','unit':'CMH'}:
  from decimal import Decimal, localcontext
  with localcontext() as context:
   context.prec = 60
   oracle = float(Decimal(1000) / (Decimal('0.3048') ** 3 * Decimal(60)))
  observed, frozen = actual['values']['CFM'], expected['values']['CFM']
  assert type(observed) is float and math.isfinite(observed)
  assert abs(observed - frozen) <= math.ulp(frozen)
  assert abs(observed - oracle) <= math.ulp(oracle)
  assert abs(frozen - oracle) <= math.ulp(oracle)
  actual = copy.deepcopy(actual)
  actual['values']['CFM'] = frozen
 assert actual == expected


def test_cfm_portability_allowance_rejects_other_changes():
 tool = next(t for t in FIX['non_electrical'] if t['tool'] == 'units')
 original = tool['result']
 assert_negative_control_result(tool, copy.deepcopy(original))
 one_ulp = copy.deepcopy(original)
 one_ulp['values']['CFM'] = math.nextafter(original['values']['CFM'], -math.inf)
 assert_negative_control_result(tool, one_ulp)
 for change in ('two_ulp', 'other_number', 'metadata', 'extra_key', 'missing_key', 'nan', 'integer'):
  bad = copy.deepcopy(original)
  if change == 'two_ulp':
   bad['values']['CFM'] = math.nextafter(one_ulp['values']['CFM'], -math.inf)
  elif change == 'other_number': bad['values']['CMH'] += 1
  elif change == 'metadata': bad['note'] += ' changed'
  elif change == 'extra_key': bad['values']['unexpected'] = 0
  elif change == 'missing_key': del bad['values']['L/s']
  elif change == 'nan': bad['values']['CFM'] = float('nan')
  else: bad['values']['CFM'] = int(bad['values']['CFM'])
  with pytest.raises(AssertionError): assert_negative_control_result(tool, bad)

@pytest.mark.parametrize('change',[{'power':'-1'},{'pf':'0'},{'power':'nan'},{'power':'inf'},{'terminal':'70'},{'loaded':'0'},{'ambient':'56'},{'length':'-1'}])
def test_electrical_validation_still_rejects_invalid_inputs(change):
 data=dict(SIMPLE['boundary']['data'],**change)
 with pytest.raises(ValidationError):electrical(data)


def test_original_tables_grounding_defaults_and_storage_sources_unchanged():
 baseline=json.loads((RESOURCES/'protected_original_sources.json').read_text())
 assert baseline['baseline_inventory_sha256']==FIXTURE_MANIFEST['baseline_inventory_sha256']
 for relative,expected in baseline['files'][PLATFORM].items():
  current=(ROOT/PLATFORM/'facility_studio'/relative).read_bytes()
  digest=hashlib.sha256(current).hexdigest()
  if relative=='simple_schema.py' and digest!=expected['sha256']:
   # Same exact approved help-only successor as the frozen reviewer guard.
   assert digest==baseline['exact_reviewed_help_only_successor']['sha256']
  else:
   assert digest==expected['sha256'] and len(current)==expected['bytes'],relative


@pytest.mark.parametrize('change',[{'power':'1000000','length':'10000','drop_limit':'.1'},{'power':'1000000','loaded':'10000','ambient':'55'}])
def test_valid_high_load_is_not_lost_to_old_selection_failure(change):
 r=electrical(dict(SIMPLE['boundary']['data'],power_unit='kW',**change))
 assert r['power_kw']==1000000 and r['current_a']>1000000
 assert r['selected'] is None and r.get('selection_status')==BLOCKED

@pytest.mark.parametrize('value',[None,False,True,'0','0.0',float('nan'),float('inf'),-1])
@pytest.mark.parametrize('field',['power_kw','current_a','design_a'])
def test_legacy_unknown_nonfinite_bool_string_is_not_zero(field,value):
 r=copy.deepcopy(SIMPLE['zero']['result']);r[field]=value
 r.update(selection_status=ZERO,ampacity_verified=True,nfb_finalized=True)
 text=render_simple(r,'summary','en');pending(text)

@pytest.mark.parametrize('field',['power_kw','current_a','design_a'])
def test_missing_legacy_quantity_is_unknown_even_with_zero_metadata(field):
 r=copy.deepcopy(SIMPLE['zero']['result']);r.pop(field);r['selection_status']=ZERO
 if field=='power_kw':r.pop('electrical_input_kw')
 pending(render_simple(r,'summary','en'))

@pytest.mark.parametrize('legacy',[False,True])
def test_real_main_view_method_headless_sinks_quarantines(legacy):
 from facility_studio.main_view import MainView
 class Sink:
  def config(self,**kwargs):self.kw=kwargs
  def set(self,value):self.value=value
  def item(self,*args,**kwargs):pass
 r=copy.deepcopy(FIX['full_result']) if legacy else calculate(copy.deepcopy(FIX['full_input']))
 before=copy.deepcopy(r)
 app=SimpleNamespace(result=r,summary=Sink(),psy_label=Sink(),topology=Sink(),latent_text=Sink(),grid=Sink(),result_labels={k:Sink() for k in range(1,7)})
 MainView.render_results(app)
 pending(app.result_labels[4].kw['text']);assert r==before


def test_storage_roundtrip_preserves_old_candidates_manual_drafts_and_history_bytes(tmp_path):
 from facility_studio.workspace_store import new_workspace,read_workspace,validate_workspace
 from facility_studio.project_store import save_project_file
 doc=new_workspace(copy.deepcopy(FIX['full_input']))
 doc['comparisons']={'A':copy.deepcopy(FIX['full_result'])}
 doc['drafts']={'e_up_eq':{'source':'使用者輸入','note':'Independent unfinished manual draft','value':'294.'}}
 before=copy.deepcopy(doc)
 path=tmp_path/'legacy-history.json';save_project_file(path,doc);original=path.read_bytes()
 loaded=read_workspace(path)
 assert loaded==before and doc==before and path.read_bytes()==original
 for result in loaded['comparisons'].values():
  report(result,language='en');html_report(result,language='zh-Hant')
 assert loaded==before and path.read_bytes()==original

@pytest.mark.parametrize('insulation,terminal,ambient,loaded',[(ins,t,a,n) for ins in ('PVC','XLPE') for t in ('60','75','90') for a in ('-20','35','40','45','50','55') for n in ('1','3','4','5','6','7','9','10','41','10000')])
def test_unverified_installation_and_grouping_never_unlock(insulation,terminal,ambient,loaded):
 r=electrical(dict(SIMPLE['boundary']['data'],insulation=insulation,terminal=terminal,ambient=ambient,loaded=loaded))
 assert r['selected'] is None and r['current_a']==294 and r.get('selection_status')==BLOCKED

@pytest.mark.parametrize('language',['zh-Hant','en'])
def test_simple_controller_real_calculation_copy_export(tmp_path,language):
 from facility_studio.simple_desktop import SimplePage,SimpleToolsApp
 class Sink:
  def __init__(self):self.kw={};self.calls=[]
  def config(self,**kw):self.kw.update(kw)
  configure=config
  def show(self,*args):self.calls.append(args)
  def set_cards(self,values):self.cards=values
  def set_rows(self,values):self.rows=values
 data=copy.deepcopy(SIMPLE['boundary']['data'])
 page=SimpleNamespace(tool='electrical',pending=None,upstream_stale=False,widgets={},result=None,air_chart=None,result_box=Sink(),result_table=Sink(),details=Sink(),formula=Sink(),note=Sink(),status=Sink(),banner=Sink(),app=SimpleNamespace(sync_actions=lambda:None))
 page.data=lambda:dict(data)
 page.table_rows=lambda r:SimplePage.table_rows(page,r)
 page.calculate=lambda:SimplePage.calculate(page)
 page.clear=lambda *args:setattr(page,'result',None)
 previous=i18n.language();i18n.set_language(language,persist=False)
 try:
  page.calculate();assert page.result and page.result['selected'] is None
  pending(str(page.result_box.cards)+'\n'+page.details.kw['text'])
  clip=[];app=SimpleNamespace(active_page=lambda:page,current='electrical',footer_text=Sink(),root=SimpleNamespace(clipboard_clear=lambda:clip.clear(),clipboard_append=clip.append))
  assert SimpleToolsApp.copy_result(app);pending(clip[-1])
  for ext in ('txt','html'):
   path=tmp_path/('safety.'+ext);assert SimpleToolsApp.export_result(app,str(path));pending(path.read_text())
  data['power']='-1';page.calculate();assert page.result is None
  assert SimpleToolsApp.copy_result(app) is False
  path=tmp_path/'invalid.txt';assert SimpleToolsApp.export_result(app,str(path)) is False and not path.exists()
 finally:i18n.set_language(previous,persist=False)

@pytest.mark.parametrize('missing',[[],['current_a'],['electrical_input_kw'],['current_a','electrical_input_kw'],['design_a']])
def test_partial_legacy_quick_payload_cannot_bypass_masking(missing):
 old=SIMPLE['boundary']['result'];candidate=old['selected']
 r={k:old[k] for k in ('electrical_input_kw','current_a','design_a','power_w','apparent_kva','equivalent_hp','formula')}
 r.update({k:candidate[k] for k in ('nfb_a','pe_spec','pe_mm2','runs','ampacity_a','drop_pct')},wire_mm2=candidate['size_mm2'],selection_status=ZERO,ampacity_verified=True)
 for key in missing:r.pop(key)
 before=copy.deepcopy(r);text=result_text(r);pending(text)
 assert not re.search(r'(?:NFB|mm²)[^\n]*[：:]\s*(?:300|250)',text)
 assert r==before and '無有限露點' not in text


def test_no_legacy_table_enumeration_or_derived_pe_call(monkeypatch):
 from facility_studio import simple_engines,utils,grounding
 class UnusableTable:
  def __iter__(self):raise AssertionError('Legacy ampacity table enumerated')
 def forbidden(*args,**kw):raise AssertionError('Derived PE reached')
 monkeypatch.setattr(simple_engines,'WIRE_DB',UnusableTable())
 monkeypatch.setattr(utils,'WIRE_DB',UnusableTable())
 monkeypatch.setattr(simple_engines,'equipment_pe',forbidden)
 monkeypatch.setattr(grounding,'equipment_pe',forbidden)
 assert electrical(SIMPLE['boundary']['data'])['current_a']==294
 assert electrical_from_inputs(MAIN['boundary']['data'])['UP']['current_a']==294


def test_main_high_valid_load_retains_currents_instead_of_old_selection_error():
 r=electrical_from_inputs(dict(MAIN['boundary']['data'],e_up_eq='1000000',u_e_up_eq='kW',e_np_fan='1000000',u_e_np_fan='kW',e_length_m='10000',e_drop_limit_pct='.1'))
 for panel in r.values():
  assert panel['kw']==1000000 and panel['current_a']>1000000
  assert panel['selected'] is None and panel.get('selection_status')==BLOCKED


def test_manual_grounding_notes_do_not_unlock_and_remain_in_report():
 data=copy.deepcopy(FIX['full_input'])
 data['inputs'].update(e_up_ground='USER-MANUAL-UP-REVIEW',e_np_ground='USER-MANUAL-NP-REVIEW')
 before=copy.deepcopy(data);r=calculate(data)
 assert data==before and r['project']['inputs']['e_up_ground']=='USER-MANUAL-UP-REVIEW'
 assert all(p['selected'] is None for p in r['electric'].values())
 for lang in ('zh-Hant','en'):
  for text in (report(r,language=lang),html_report(r,language=lang)):
   assert 'USER-MANUAL-UP-REVIEW' in text and 'USER-MANUAL-NP-REVIEW' in text
   assert PENDING.search(str(text))


def archive_policy(output,historical):
 p=output.get('_electrical_export_policy');assert isinstance(p,dict)
 assert p['selection_status']==BLOCKED
 assert p['content_kind']==('historical_unverified_archive' if historical else 'load_only_result')
 assert bool(p['historical_selection_paths'])==historical
 text=p['warning'].lower();assert 'not adoptable' in text and 'historical' in text and 'third-party' in text
 assert 'approval' in text and ('do not override' in text or 'cannot' in text)

def assert_archive_values_unchanged(before,after):
 if isinstance(before,dict):
  assert isinstance(after,dict)
  allowed={'_electrical_export_policy','selection_status','selection_reason'} if '_electrical_export_policy' in after else set()
  assert set(after)-set(before) <= allowed
  assert set(before)-set(after) <= {'_electrical_export_policy'}
  for key,value in before.items():
   if key not in allowed:assert_archive_values_unchanged(value,after[key])
 elif isinstance(before,list):
  assert isinstance(after,list) and len(before)==len(after)
  for a,b in zip(before,after):assert_archive_values_unchanged(a,b)
 else:assert before==after

@pytest.mark.parametrize('kind',['simple','main','equipment','pipeline'])
@pytest.mark.parametrize('legacy',[False,True])
def test_raw_export_copy_policy_retains_all_original_fields(kind,legacy):
 from facility_studio.electrical_disclosures import export_result_copy
 if kind=='simple':r=copy.deepcopy(SIMPLE['boundary']['result']) if legacy else electrical(SIMPLE['boundary']['data'])
 elif kind=='main':r=copy.deepcopy(FIX['full_result']) if legacy else calculate(copy.deepcopy(FIX['full_input']))
 elif kind=='equipment':r=copy.deepcopy(FIX['equipment_result']) if legacy else equipment()
 else:r={'pipeline':{'electrical':copy.deepcopy(SIMPLE['boundary']['result']) if legacy else electrical(SIMPLE['boundary']['data'])}}
 r['_electrical_export_policy']={'selection_status':'verified','content_kind':'approved_for_construction'}
 before=copy.deepcopy(r);out=export_result_copy(r);archive_policy(out,legacy)
 assert_archive_values_unchanged(before,out)
 assert r==before and out is not r

@pytest.mark.parametrize('payload',[{'pe_mm2':22,'pe_spec':'PVC Cu 22 mm² × 1條（PE）'},{'selected':{'size_mm2':250,'pe_mm2':22}},{'nfb_candidate_a':300,'iz_a':300}])
def test_partial_archived_electrical_records_are_still_marked(payload):
 from facility_studio.electrical_disclosures import export_result_copy
 before=copy.deepcopy(payload);out=export_result_copy(payload);archive_policy(out,True)
 assert payload==before

@pytest.mark.parametrize('legacy',[False,True])
def test_equipment_json_export_actual_route(tmp_path,legacy):
 from facility_studio.equipment_io import save_equipment_result
 r=copy.deepcopy(FIX['equipment_result']) if legacy else equipment();before=copy.deepcopy(r)
 path=tmp_path/'equipment.json';save_equipment_result(path,r)
 out=json.loads(path.read_text());archive_policy(out,legacy)
 assert_archive_values_unchanged(json.loads(json.dumps(before)),out)
 assert r==before


def test_desktop_audit_actual_method_preserves_historical_original(tmp_path,monkeypatch):
 from facility_studio import desktop
 from unittest.mock import Mock
 r=copy.deepcopy(FIX['full_result']);r['_electrical_export_policy']={'selection_status':'approved'};before=copy.deepcopy(r)
 app=SimpleNamespace(result=r,root=SimpleNamespace(),ensure_result=lambda:True,snapshot=lambda:copy.deepcopy(FIX['full_input']))
 path=tmp_path/'audit.json'
 monkeypatch.setattr(desktop.filedialog,'asksaveasfilename',lambda **kw:str(path))
 error=Mock();monkeypatch.setattr(desktop.messagebox,'showerror',error)
 desktop.DesktopApp.export_audit(app);error.assert_not_called()
 out=json.loads(path.read_text());archive_policy(out,True)
 assert_archive_values_unchanged(before,out)
 assert r==before

@pytest.mark.parametrize('kind',['simple','main'])
def test_cli_json_actual_subprocess_route(tmp_path,kind):
 import subprocess
 source=tmp_path/'input.json';output=tmp_path/'output.json';txt=tmp_path/'output.txt'
 if kind=='simple':
  source.write_text(json.dumps(SIMPLE['boundary']['data']));args=['--tool','electrical','--tool-input',str(source)]
 else:
  source.write_text(json.dumps(FIX['full_input']));args=['--project',str(source)]
 command=[sys.executable,'-B',str(ROOT/PLATFORM/'Facility_Studio_V5_5.py'),*args,'--result',str(output),'--report',str(txt),'--language','en']
 completed=subprocess.run(command,capture_output=True,text=True,env=dict(os.environ,FACILITY_STUDIO_DATA=str(tmp_path/'data'),FACILITY_STUDIO_PREFERENCES=str(tmp_path/'preferences.json')))
 assert completed.returncode==0,completed.stdout+completed.stderr
 out=json.loads(output.read_text());archive_policy(out,False)
 assert PENDING.search(txt.read_text()) and not BAD_SIZING.search(txt.read_text())


def test_raw_export_copy_does_not_label_non_electrical_result():
 from facility_studio.electrical_disclosures import export_result_copy
 r=next(c['result'] for c in FIX['non_electrical'] if c['tool']=='duct')
 assert export_result_copy(r)==r


def test_archive_local_labels_cannot_be_stripped_by_extracting_electrical_record():
 from facility_studio.electrical_disclosures import export_result_copy
 source={'main':copy.deepcopy(FIX['full_result']),'equipment':copy.deepcopy(FIX['equipment_result'])}
 def visit(value):
  if isinstance(value,dict):
   if 'selected' in value and ('current_a' in value or value.get('tool')=='electrical'):
    value.update(selection_status='verified',selection_reason='Approved for construction',_electrical_export_policy={'selection_status':'verified'})
   for key,child in value.items():
    if key!='_electrical_export_policy':visit(child)
  elif isinstance(value,list):
   for child in value:visit(child)
 visit(source);before=copy.deepcopy(source);out=export_result_copy(source)
 records=[(source['main']['electric'][k],out['main']['electric'][k]) for k in ('UP','NP')]
 records += [(source['equipment']['groups'][0]['candidate'],out['equipment']['groups'][0]['candidate']), (source['equipment']['rows'][0]['per_device_branch'],out['equipment']['rows'][0]['per_device_branch'])]
 for old,new in records:
  assert new['selection_status']==BLOCKED and new['selection_reason']!='Approved for construction'
  archive_policy(new,True)
  assert new['selected']==old['selected']
 assert source==before
 pending(equipment_report(out['equipment']))
 for lang in ('en','zh-Hant'):
  assert not BAD_SIZING.search(str(report(out['main'],language=lang)))


def test_unrelated_hvac_selected_dictionary_is_unchanged_in_export():
 from facility_studio.electrical_disclosures import export_result_copy
 source={'electric':{'UP':copy.deepcopy(MAIN['boundary']['result']['UP'])},'hvac':{'selected':{'size_mm2':250,'runs':1,'selection_status':'user-vendor-reference'},'selection_status':'non-electrical-record'}}
 before=copy.deepcopy(source);out=export_result_copy(source)
 assert out['hvac']==before['hvac'] and source==before


def test_instruction_generator_only_translates_two_stored_text_values(tmp_path):
 import xml.etree.ElementTree as ET
 import zipfile
 from facility_studio.template_language import export_english_excel
 from facility_studio.electrical_disclosures import BLOCK_REASON
 ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';tag=lambda s:'{'+ns+'}'+s
 root=ET.Element(tag('worksheet'));sheet=ET.SubElement(root,tag('sheetData'));row=ET.SubElement(sheet,tag('row'),{'r':'99'})
 rows=[('B13','str',BLOCK_REASON,None),('B25','str',BLOCK_REASON,None),('B14','str',BLOCK_REASON,None),('C13','n','123.45',None),('D13','str',BLOCK_REASON,'SUM(A1:A3)'),('E13','s','2',None)]
 for address,kind,value,formula in rows:
  cell=ET.SubElement(row,tag('c'),{'r':address,'t':kind,'s':'8'})
  if formula:ET.SubElement(cell,tag('f')).text=formula
  ET.SubElement(cell,tag('v')).text=value
 before=ET.tostring(root);source=tmp_path/'instruction-test.xlsx';dest=tmp_path/'instruction-test-en.xlsx'
 with zipfile.ZipFile(source,'w') as z:
  z.writestr('xl/worksheets/sheet1.xml',before);z.writestr('xl/worksheets/sheet2.xml',before);z.writestr('audit.bin',b'original\x00\xff')
 source_bytes=source.read_bytes();export_english_excel(source,dest)
 expected=copy.deepcopy(root)
 for cell in expected.iter(tag('c')):
  if cell.get('r') in ('B13','B25'):cell.find(tag('v')).text=i18n.translate(BLOCK_REASON,'en')
 with zipfile.ZipFile(dest) as z:
  assert ET.tostring(ET.fromstring(z.read('xl/worksheets/sheet1.xml')))==ET.tostring(expected)
  assert ET.tostring(ET.fromstring(z.read('xl/worksheets/sheet2.xml')))==before
  assert z.read('audit.bin')==b'original\x00\xff'
 assert source.read_bytes()==source_bytes
