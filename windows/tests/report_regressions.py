"""Run report semantic regressions; --gui exercises real export buttons."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from facility_studio.report_acceptance import run_checks,run_ui


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--gui",action="store_true")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    checks=run_checks();formulas=len(checks);errors=[]
    if args.gui:
        with tempfile.TemporaryDirectory(prefix="report-ui-") as temp:
            os.environ["FACILITY_STUDIO_PREFERENCES"]=str(Path(temp)/"preferences.json")
            os.environ["LOCALAPPDATA"]=temp
            from facility_studio.localized_tk import tk
            from facility_studio.simple_desktop import SimpleToolsApp
            root=tk.Tk();root.report_callback_exception=lambda *exc:errors.append(''.join(traceback.format_exception(*exc)))
            def check(name,action):
                assert action() is not False,name
                checks.append(dict(name=name,passed=True))
            try:run_ui(root,SimpleToolsApp(root),check,root.update,args.output)
            finally:root.destroy()
            assert not errors,errors
    result=dict(passed=True,platform=platform.platform(),numeric_and_report_checks=formulas,gui_checks=len(checks)-formulas,checks=checks,callback_errors=errors)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))


if __name__=='__main__':main()
