"""Lighting-only audit of unchanged Windows win.4; no application mutations."""
from pathlib import Path
from decimal import Decimal, ROUND_CEILING
import argparse
import json
import math
import os
import platform
import random
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'windows'))


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--gui',action='store_true');args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
 tree=subprocess.check_output(['git','rev-parse','HEAD:windows'],cwd=ROOT,text=True).strip()
 assert tree=='5edfb03e3d2ceaf1ed572162eaf871f0613a5c59'
 from facility_studio.simple_schema import defaults
 from facility_studio.simple_engines import lighting
 from facility_studio.engine import lighting as main_lighting
 from facility_studio.schema import default_project
 checks=[];errors=[];cases=[]
 def check(name,passed,actual,expected,issue=None):
  checks.append(dict(name=name,passed=bool(passed),actual=actual,expected=expected,issue_id=issue))
 rng=random.Random(20261018)
 for index in range(500):
  length=Decimal(rng.randint(4,200))/2;width=Decimal(rng.randint(4,200))/2;area=length*width
  lux=Decimal(rng.choice([100,300,500,750,1000]));lm=Decimal(rng.choice([2000,3000,4000,6400,8000]))
  u=Decimal(rng.choice(['0.35','0.6','0.75','0.9']));m=Decimal(rng.choice(['0.6','0.8','0.9']))
  expected=int((lux*area/(lm*u*m)).to_integral_value(rounding=ROUND_CEILING))
  for mode in ['面積 m²','面積 坪','長×寬','體積 m³']:
   d=defaults('lighting');d.update(mode='反算燈數',area_mode=mode,length=str(length),width=str(width),
      height='3',area=str(area*Decimal(121)/400 if mode=='面積 坪' else area*3 if mode=='體積 m³' else area),
      lumen_mode='燈具型錄流明',lumens=str(lm),target=str(lux),utilization=str(u),maintenance=str(m))
   r=lighting(d);check(f'formula/{index}/{mode}',r['quantity']==expected,r['quantity'],expected)
  p=default_project();i=p['inputs'];i.update(en_L_A=str(length),en_W_A=str(width),en_L_B='0',en_W_B='0',
       light_lux=str(lux),light_lm=str(lm),light_u=str(u),light_m=str(m))
  r=main_lighting(i);check(f'workbench-formula/{index}',r['qty']==expected,r['qty'],expected)
 if args.gui:
  os.environ['FACILITY_STUDIO_PREFERENCES']=str(out/'isolated-prefs.json')
  os.environ['LOCALAPPDATA']=str(out/'isolated-user-data')
  from facility_studio.localized_tk import tk
  from facility_studio.simple_desktop import SimpleToolsApp
  from facility_studio import i18n
  i18n.set_language('zh-Hant',persist=False)
  root=tk.Tk();callbacks=[];root.report_callback_exception=lambda *x:callbacks.append(''.join(traceback.format_exception(*x)))
  app=SimpleToolsApp(root);app.show_tool('lighting');page=app.active_page();root.update()
  try:
   for name,mode,value in [('75-m2','面積 m²','75'),('75-m2-from-ping','面積 坪','22.6875'),
                          ('225-m3','體積 m³','225'),('real-15x5','長×寬',None)]:
    page.reset();page.variables['mode'].set('反算燈數');page.variables['lumen_mode'].set('燈具型錄流明')
    page.variables['area_mode'].set(mode)
    if value is not None:page.variables['area'].set(value)
    else:page.variables['length'].set('15');page.variables['width'].set('5')
    page.calculate();root.update();before=dict(page.result);before_inputs=page.data()
    page.dialux_button.invoke();root.update();after=dict(page.result);after_inputs=page.data()
    case=dict(name=name,button_label=str(page.dialux_button.cget('text')),before_inputs=before_inputs,
        before=before,after_inputs=after_inputs,after=after,
        quantity_change_percent=100*(after['quantity']/before['quantity']-1))
    cases.append(case)
    check('preset-preserves-area/'+name,math.isclose(after['area_m2'],before['area_m2'],rel_tol=1e-10),
          after['area_m2'],before['area_m2'],'F07')
    check('preset-preserves-count/'+name,after['quantity']==before['quantity'],after['quantity'],before['quantity'],'F07')
   check('gui-no-unhandled-callback-errors',not callbacks,callbacks,[])
  except Exception:errors.append(traceback.format_exc())
  finally:root.destroy()
 result=dict(audit_completed=not errors,host=platform.platform(),source_tree=tree,
   formula_checks=2500,checks=checks,failed_checks=sum(not c['passed'] for c in checks),
   unexpected_formula_mismatches=[c for c in checks if not c['passed'] and not c['issue_id']],
   gui_cases=cases,execution_errors=errors)
 (out/'lighting-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ['checks','gui_cases']},ensure_ascii=False))
 for case in cases:print(json.dumps({k:case[k] for k in ['name','button_label','quantity_change_percent']}|dict(before_area=case['before']['area_m2'],after_area=case['after']['area_m2'],before_count=case['before']['quantity'],after_count=case['after']['quantity']),ensure_ascii=False))
 return 2 if errors else 0


if __name__=='__main__':raise SystemExit(main())
