"""Developer-only reproduction of the beginner walkthrough's 20 conditions.

Normal desktop users open START_HERE.html; they do not run this script.
Run from a repository checkout: python docs/tutorial/verify_tutorial.py
    --platform windows --output tutorial-windows.json
"""

import argparse
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "macos"), default="windows")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-root", type=Path, help="Optional separate source checkout")
    args = parser.parse_args()
    root = args.source_root or Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / args.platform))
    from facility_studio.engine import calculate
    from facility_studio.workspace_store import read_workspace
    from facility_studio.ahu_engine import nm_calculate
    from facility_studio.design_workflow import ahu_requirement_updates, ahu_utility_preview
    from facility_studio.errors import ValidationError
    from facility_studio.reports import report
    from facility_studio import i18n

    directory = Path(__file__).parent
    a = read_workspace(directory / "01_Practice_AHU.json")
    b = read_workspace(directory / "02_Practice_MAU_and_AHU.json")
    base = calculate(a["main"])
    records, checks = [], 0

    def check(value):
        nonlocal checks
        assert value, "Tutorial condition failed"
        checks += 1

    def close(actual, expected):
        check(math.isclose(actual, expected, abs_tol=1e-8, rel_tol=1e-9))

    def changed(**values):
        project = copy.deepcopy(a["main"])
        project["inputs"].update({k: str(v) for k,v in values.items()})
        return calculate(project)

    def balance(result):
        close(result["mass_residual"], 0)
        close(result["sensible_residual"], 0)
        for season in ("summer", "winter"):
            close(result[season]["energy_residual_kw"], 0)

    def record(name, values):
        records.append(dict(case=len(records)+1, name=name, passed=True, values=values))

    close(base["light"]["area_m2"],96)
    close(base["zones"]["A"]["volume"],288)
    close(base["qs"],7.869996)
    close(base["ql"],0.44)
    close(base["circulation_cmh"],1728)
    close(base["supply_room_cmh"],2400.235496650782)
    check(base["light"]["qty"]==25 and base["quality"]["failed"]==0 and base["quality"]["pending"]>0)
    balance(base)
    record("01 Baseline workspace and room heat/moisture balance",dict(qs_kw=base["qs"],qty=25,quality=base["quality"]["status"]))

    r=changed(en_L_A=24)
    close(r["light"]["area_m2"],192)
    check(r["light"]["qty"]==50)
    close(r["circulation_cmh"],3456)
    balance(r)
    record("02 Double room length",dict(area_m2=192,qty=50))

    r=changed(en_H_A=4)
    close(r["zones"]["A"]["volume"],384)
    close(r["circulation_cmh"],2304)
    check(r["light"]["qty"]==base["light"]["qty"])
    record("03 Change height without changing lighting area",dict(volume_m3=384,circulation_cmh=2304))

    r=changed(ppl_A=12)
    close(r["parts"]["people"]-base["parts"]["people"],0.3)
    close(r["ql"]-base["ql"],0.22)
    close(r["minimum_oa_cmh"],288)
    balance(r)
    record("04 Eight to twelve people",dict(sensible_delta_kw=0.3,latent_delta_kw=0.22))

    r=changed(eq_kw=10)
    close(r["qs"]-base["qs"],5)
    balance(r)
    record("05 Equipment heat 5 to 10 kW",dict(qs_kw=r["qs"]))

    r=changed(light_lux=300)
    check(r["light"]["qty"]==15)
    close(r["light"]["kw"],0.6)
    record("06 Lighting target 500 to 300 lux",dict(qty=15,kw=0.6))

    r=changed(latent_mode="已知產濕量 kg/h",process_moisture_kg_h=1)
    close(r["latent"]["process_kw"],2501/3600)
    close(r["moisture"]*3600-base["moisture"]*3600,1)
    balance(r)
    record("07 One kg/h of room process moisture",dict(process_kw=r["latent"]["process_kw"]))

    r=changed(latent_mode="已知潛熱 kW",process_latent_kw=1,process_moisture_kg_h=99)
    close(r["latent"]["process_kw"],1)
    close(r["ql"],1.44)
    balance(r)
    record("08 Known latent kW does not also add inactive kg/h",dict(total_latent_kw=r["ql"]))

    r=changed(process_latent_kw=99,process_moisture_kg_h=99)
    close(r["ql"],base["ql"])
    record("09 No-additional-moisture excludes retained drafts",dict(total_latent_kw=r["ql"]))

    r=changed(gas2_q=800,gas_barg=6,gas_min_barg=5)
    rows=r["gas"]
    check(bool(rows))
    record("10 CDA sizing uses minimum rather than supply gauge pressure",dict(gas_result=rows))
    # Conversion and selected pressure are checked independently from result labels.
    expected_alpm=800*101.325/(5*100+101.325)
    close(rows["2"]["actual_lpm"],expected_alpm)
    close(rows["2"]["pressure_abs_pa"],601325)
    record_index=len(records)-1
    records[record_index]["values"]["expected_alpm"]=expected_alpm

    pv=changed(pv_q=60,pv_torr=150,pv_pressure_unit="Torr(abs)")
    pvk=changed(pv_q=60,pv_torr=150*101.325/760,pv_pressure_unit="kPa(abs)")
    pvm=changed(pv_q=60,pv_torr=150*1013.25/760,pv_pressure_unit="mbar(abs)")
    for other in (pvk,pvm):
        close(pv["gas"]["4"]["actual_lpm"],other["gas"]["4"]["actual_lpm"])
        close(pv["gas"]["4"]["pressure_abs_pa"],other["gas"]["4"]["pressure_abs_pa"])
        check(pv["gas"]["4"]["size"]==other["gas"]["4"]["size"])
    record("11 PV Torr, kPa and mbar absolute-pressure equivalence",dict(torr=150,kpa=150*101.325/760,mbar=150*1013.25/760))

    r=changed(gas1_q=0,gas2_q=0,gas3_q=0,pv_q=0)
    check(all(row["actual_lpm"]==0 and row["selected_id_mm"]==0 for row in r["gas"].values()))
    record("12 Unused gas and vacuum demand is zero",dict(active_gas_rows=0))

    r=changed(chw_q=999)
    close(r["water"]["CHW"]["lpm"],base["water"]["CHW"]["lpm"])
    record("13 Linked CHW ignores retained manual flow",dict(chw_lpm=r["water"]["CHW"]["lpm"]))

    r=changed(chw_link="獨立輸入",chw_q=100)
    close(r["water"]["CHW"]["lpm"],100)
    close(r["water"]["CHW"]["capacity_kw"],100/60000*1000*4.1868*5)
    check(not r["water"]["CHW"]["linked"])
    record("14 Independent CHW uses measured 100 LPM",dict(chw_lpm=100,capacity_kw=r["water"]["CHW"]["capacity_kw"]))

    r=changed(dt_chw=4)
    close(r["water"]["CHW"]["lpm"],base["water"]["CHW"]["lpm"]*5/4)
    record("15 Water delta-T 5 to 4 K increases flow",dict(chw_lpm=r["water"]["CHW"]["lpm"]))

    p=copy.deepcopy(a["main"]);p["pressure_drop"]["CHW"]["length_m"]="60"
    r=calculate(p)
    close(r["pressure"]["CHW"]["total_pa"],base["pressure"]["CHW"]["total_pa"]*2)
    check(not r["pressure"]["CHW"]["equipment_included"])
    record("16 Pipe-only pressure subtotal doubles with route length",dict(pa=r["pressure"]["CHW"]["total_pa"]))

    p=copy.deepcopy(a["main"]);p["pressure_drop"]["CHW"].update(equipment_known="已知設備壓差",equipment_drop="10",unit="kPa")
    r=calculate(p)
    close(r["pressure"]["CHW"]["total_pa"],base["pressure"]["CHW"]["total_pa"]+10000)
    check(r["pressure"]["CHW"]["equipment_included"])
    record("17 Known equipment pressure adds exactly 10 kPa",dict(pa=r["pressure"]["CHW"]["total_pa"]))

    rb=calculate(b["main"]);u=ahu_requirement_updates(rb);unit=b["ahus"][0]["inputs"]
    check(unit["linked_main_hash"]==u["linked_main_hash"])
    close(float(unit["summer_flow"]),rb["summer"]["mass"]*rb["summer"]["supply"]["v_da"]*3600)
    ra=nm_calculate(unit)
    for season in ("summer","winter"):
        close(ra[season]["energy_residual_kw"],0)
        close(ra[season]["moisture_residual_kg_h"],0)
    preview=ahu_utility_preview(ra)["updates"]
    close(float(preview["mchw_q"]),12.443068772362539)
    close(float(preview["chw_q"]),12.34847007002057)
    close(float(preview["e_np_heat"]),16)
    check(preview["chw_link"]=="獨立輸入" and ra["quality"]["failed"]==0)
    record("18 MAU link, stage balance and replacement transfer",dict(transfer=preview,quality=ra["quality"]["status"]))

    under=copy.deepcopy(unit);under["h1_kw"]="0.2"
    ru=nm_calculate(under)
    check(ru["quality"]["failed"]>0)
    check(not ru["winter"]["checks"]["H1 電熱全載備援"])
    record("19 Undersized H1 is reported as insufficient",dict(quality=ru["quality"]["status"],winter_required_kw=ru["winter"]["h1"]["air_kw"]))

    rejected=[]
    for label,action,field in [
        ("Mixed AHU must not link as a full-OA MAU",lambda:ahu_requirement_updates(base),"sys_type"),
        ("Manual outside air cannot undercut minimum",lambda:changed(en_manual_oa=1),"en_manual_oa"),
        ("Zero PF cannot produce a usable design report",lambda:changed(e_pf=0),"e_pf"),
    ]:
        try:action()
        except ValidationError as error:
            check(error.field_name==field)
            rejected.append(dict(reason=label,field=field))
        else:raise AssertionError(label)
    for language in ("zh-Hant","en"):
        i18n.set_language(language,persist=False)
        text=str(report(base))
        check(text==(directory/f'01_Expected_Report{".en" if language=="en" else ""}.txt').read_text())
    record("20 Invalid/boundary inputs are rejected and reference reports match",dict(rejected=rejected))

    check(len(records)==20)
    evidence=dict(app_version=base["version"],source_platform=args.platform,
                  execution="Headless calculation and report checks on the current host; native GUI checks are separate.",
                  cases=records,checks=checks,passed=True,
                  input_sha256={name:sha256((directory/name).read_bytes()).hexdigest() for name in ("01_Practice_AHU.json","02_Practice_MAU_and_AHU.json")})
    if args.output:args.output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(dict(platform=args.platform,cases=len(records),checks=checks,passed=True)))


if __name__=="__main__":
    main()
