"""Run the 20 cases and 5 sweeps of the 2026-10-31 verification plan and write results.json.

    python tests/engineering_scenarios/run_scenarios.py               everything
    python tests/engineering_scenarios/run_scenarios.py --case CR-02  one case (prints its checks)
    python tests/engineering_scenarios/run_scenarios.py --cases       the 20 cases only
    python tests/engineering_scenarios/run_scenarios.py --sweeps      the 5 sweeps only

It never edits the product and never edits a case to make it pass. Linux evidence only: not a Windows-native acceptance.
Needs psychrolib==2.5.0. Exit code is 0 unless a check FAILs; BLOCKED and NOT APPLICABLE are reported, not hidden.
"""
import json
import os
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FS_SRC") or HERE.parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "feed_stress"))
from facility_studio import api, i18n  # noqa: E402
from facility_studio.errors import ValidationError  # noqa: E402
from facility_studio.schema import DEFAULTS, default_project  # noqa: E402

import checks  # noqa: E402
from cases import ASSUMPTIONS, CASES, inputs  # noqa: E402

# what the plan asks for that the engine cannot express (plan 5.1: BLOCKED, never faked)
BLOCKED_ASPECTS = {
    "CR-01": [("FFU 備援與故障台數、單台阻力", "引擎沒有備援或阻力欄位（見 S-03）")],
    "CR-05": [("正壓概念", "規格未給壓差值，引擎只接受 >= 0 的壓差輸入")],
    "CR-06": [("壓差", "規格未給漏風／開口資料；不得由 58000-52000 的風量差推定壓差")],
    "H-01": [("手術室正壓值與感染控制", "未給壓差值與漏風資料；規範未對應")],
    "H-03": [("保護性環境正壓值", "未給壓差值與漏風資料；規範未對應")],
    "P-01": [("局部 ISO 5", "背景 ACH 不能推定局部 ISO 5；引擎沒有局部潔淨區模型")],
    "P-02": [("壓差梯度與門開啟影響", "未給門縫、開門次數與壓差值")],
    "D-01": [("設備備援（N+1）", "引擎沒有備援欄位；台數是無備援需求值")],
    "D-02": [("電池安全通風", "引擎沒有電池化學種類、充放電與氫氣排放模型；顯熱不能證明通風安全")],
    "F-02": [("±0.5°C 控制精度與穩定性", "引擎是穩態需求計算，沒有控制回路模型")],
}
WHOLE_BLOCKED = {"H-02": "負壓、轉移風量與排風大於外氣", "H-04": "排風櫃補風與轉移風量；排風大於外氣", "F-03": "排氣大於外氣的補風來源"}


def reproduce(cid):
    return f"python tests/engineering_scenarios/run_scenarios.py --case {cid}"


def run_project(o):
    p = default_project()
    for k, v in o.items():
        p["inputs"][k] = v if isinstance(v, str) else format(v, ".12g")
    return api.calculate(p)


def changed(o):
    return {k: (v if isinstance(v, str) else format(v, ".12g")) for k, v in o.items() if str(DEFAULTS.get(k)) != (v if isinstance(v, str) else format(v, ".12g"))}


def run_case(c):
    o = inputs(c)
    rec = dict(id=c["id"], scenario=c["scenario"], spec={k: c[k] for k in ("area_m2", "height_m", "room_t", "room_rh", "oa_cmh", "exhaust_cmh", "ach_kind", "ach", "equip_kw", "focus")},
               system=c["system"], engine_inputs=changed(o), reproduce=reproduce(c["id"]), blocked_aspects=[dict(aspect=a, reason=b) for a, b in BLOCKED_ASPECTS.get(c["id"], [])])
    try:
        r = run_project(o)
    except ValidationError as exc:
        msg = str(exc)
        rec.update(outcome="rejected", message=msg, checks=checks.check_rejected(c, o, msg), warnings=[], quality=None)
        verified = [k for k in rec["checks"] if k["id"] == "R2" and k["status"] == "PASS"]
        rec["conclusion"] = "FAIL" if any(k["status"] == "FAIL" for k in rec["checks"] if k["id"] in ("R1", "R2")) else "BLOCKED"
        rec["conclusion_note"] = ("engine refuses; the cause is verified independently" if verified else "engine refuses; cause not verified") + (
            f" | {WHOLE_BLOCKED[c['id']]}" if c["id"] in WHOLE_BLOCKED else " | the plan omits the data the case needs (assumption A-CHW)")
        rec["conclusion_L2"] = "BLOCKED"
        return rec
    i18n.set_language("zh-Hant", persist=False)
    zh = str(api.report(r))
    i18n.set_language("en", persist=False)
    en = str(api.report(r))
    i18n.set_language("zh-Hant", persist=False)
    cs = checks.check_accepted(c, o, r, zh, en, DEFAULTS)
    rec.update(outcome="accepted", checks=cs, warnings=list(r["warnings"]), quality=dict(status=r["quality"]["status"], failed=r["quality"]["failed"], pending=r["quality"]["pending"], deferred=r["quality"]["deferred"],
                                                                                    items=[dict(name=i["name"], status=i["status"], detail=i["detail"]) for i in r["quality"]["items"] if i["status"] != "通過"]),
               engine=dict(circulation_cmh=r["circulation_cmh"], oa_room_cmh=r["oa_room_cmh"], ffu_count=r["counts"]["FFU"], dcc_count=r["counts"]["DCC"], rcu_count=r["counts"]["RCU"], qs_kw=r["qs"], q_total_kw=r["q_total_kw"],
                           supply_room_cmh=r["supply_room_cmh"], coverage_ratio=r["coverage_ratio"], chw_lpm=r["water"]["CHW"]["lpm"], airflow_governing=r["airflow_basis"].get("governing")))
    l1 = [k["status"] for k in cs if k["layer"] == "L1"]
    rec["conclusion"] = "FAIL" if "FAIL" in l1 or any(k["status"] == "FAIL" and k["layer"] == "L3" for k in cs) else "PASS"
    l2 = [k for k in cs if k["layer"] == "L2" and k["status"] == "FAIL"]
    rec["conclusion_L2"] = "FLAG: " + "; ".join(k["name"] for k in l2) if l2 else "no engineering concern found by the independent checks"
    rec["conclusion_note"] = "calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED"
    return rec


def probe(cid, label, over, note):
    """A clearly labelled variant of a refused case: it is NOT the plan case, it checks the engine's own advice."""
    c = next(x for x in CASES if x["id"] == cid)
    o = inputs(c)
    o.update(over)
    try:
        r = run_project(o)
        return dict(case=cid, label=label, changes=over, outcome="accepted", status=r["quality"]["status"], note=note,
                    result=dict(supply_room_cmh=r["supply_room_cmh"], circulation_cmh=r["circulation_cmh"], q_total_kw=r["q_total_kw"], dcc_count=r["counts"]["DCC"], chw_lpm=r["water"]["CHW"]["lpm"]))
    except ValidationError as exc:
        return dict(case=cid, label=label, changes=over, outcome="rejected", message=str(exc)[:200], note=note)


def main():
    argv = sys.argv[1:]
    only = argv[argv.index("--case") + 1] if "--case" in argv else None
    do_cases = "--sweeps" not in argv
    do_sweeps = "--cases" not in argv and only is None
    out = dict(plan="Facility Studio V5.6.0 win.9 20-case verification plan, 2026-10-31", environment="Linux; Windows-native GUI / EXE not verified",
               assumptions=[dict(id=a, item=b, used=c_, note=d) for a, b, c_, d in ASSUMPTIONS])
    if do_cases:
        recs = [run_case(c) for c in CASES if only in (None, c["id"])]
        out["cases"] = recs
        if only is None:
            out["probes"] = [
                probe("CR-05", "dry-coil supply water raised to the advice (dew point 14.4 C + 1 K margin -> 15.5 C)", {"dccw_in": 15.5}, "NOT the plan case: checks that the engine's stated remedy works"),
                probe("P-01", "chilled water lowered to the advice (below dew point 7.72 C - 1 K -> 6.5 C)", {"chw2_in": 6.5}, "NOT the plan case: checks that the engine's stated remedy works"),
            ]
        obs = {}
        for rec in recs:
            for k in rec["checks"]:
                if k["note"].startswith("OBS"):
                    obs.setdefault(k["note"], []).append(rec["id"])
        out["observations"] = [dict(note=n, cases=v) for n, v in obs.items()]
        for rec in recs:
            if only:
                print(json.dumps({k: rec[k] for k in ("id", "scenario", "outcome", "conclusion", "conclusion_L2", "conclusion_note")}, ensure_ascii=False, indent=1))
                for k in rec["checks"]:
                    print(f"  {k['status']:14} {k['layer']} {k['id']:5} {k['name'][:80]}  {('exp ' + str(k['expected'])[:40]) if k['expected'] is not None else ''} {('act ' + str(k['actual'])[:40]) if k['actual'] is not None else ''} {k['note'][:90]}")
    if do_sweeps:
        import sweeps  # noqa: E402
        out["sweeps"] = sweeps.run_all(run_project, inputs, CASES)
    if only is None:
        (HERE / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        cases = out.get("cases", [])
        tally = {}
        for r in cases:
            tally[r["conclusion"]] = tally.get(r["conclusion"], 0) + 1
        print("cases:", tally, "| checks:", {s: sum(1 for r in cases for k in r["checks"] if k["status"] == s) for s in ("PASS", "FAIL", "BLOCKED", "NOT APPLICABLE")})
        if "sweeps" in out:
            for s in out["sweeps"]:
                print(f"{s['id']} {s['conclusion']:10} {s['summary']}")
        bad = [r["id"] for r in cases if r["conclusion"] == "FAIL"] + [s["id"] for s in out.get("sweeps", []) if s["conclusion"] == "FAIL"]
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
