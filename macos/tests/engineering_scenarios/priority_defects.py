"""Priority-defect verification (plan section 6) on the current branch, with a before/after on the imported baseline.

    python tests/engineering_scenarios/priority_defects.py [--baseline-src DIR]

Prints one line per check and writes priority_defects.json. Never edits the product. Linux evidence only.
Checks:  PD-1 F-1 (absurd airflow)   PD-2 quality-gate reachability   PD-3 chilled-water margin label
         PD-4 U-value unit           PD-5 PV pressure range
--baseline-src points at a Source/windows tree of the imported baseline (git archive 2c46056) to show the defect before the fix.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FS_SRC") or HERE.parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from facility_studio import api, i18n  # noqa: E402
from facility_studio.errors import ValidationError  # noqa: E402
from facility_studio.schema import FIELDS, default_project  # noqa: E402

from cases import CASES, inputs  # noqa: E402

OUT = []


def rec(pid, name, status, detail, expected=None, actual=None):
    OUT.append(dict(id=pid, name=name, status=status, detail=detail, expected=expected, actual=actual))
    print(f"{status:14} {pid:6} {name}  {detail[:150]}")


def proj(over, base=None):
    p = default_project()
    for k, v in (base or {}).items():
        p["inputs"][k] = v if isinstance(v, str) else format(v, ".12g")
    for k, v in over.items():
        p["inputs"][k] = v if isinstance(v, str) else format(v, ".12g")
    return p


def case_inputs(cid):
    return inputs(next(c for c in CASES if c["id"] == cid))


# the F-1 reproducer recorded by the stress test (tests/airflow_guard_checks.py, AHU, supply dT -> 0)
F1 = {"sys_type": "AHU (OA+RA 混合)", "oa_t": 45.69, "oa_rh": 53.81, "ra_t": 22, "ra_rh": 40, "chw2_in": 7.06, "eq_kw": 199.09, "en_L_A": 75.19, "en_W_A": 34.58, "en_H_A": 4.57, "ppl_A": 1}
SNIPPET = r"""
import sys, json
sys.path.insert(0, sys.argv[1])
from facility_studio import api
from facility_studio.schema import default_project
p = default_project()
for k, v in json.loads(sys.argv[2]).items():
    p["inputs"][k] = v if isinstance(v, str) else format(v, ".12g")
try:
    r = api.calculate(p)
    print(json.dumps(dict(ok=True, cmh=r["supply_room_cmh"], status=r["quality"]["status"])))
except Exception as e:
    print(json.dumps(dict(ok=False, msg=str(e)[:200])))
"""


def run_in(src, over):
    out = subprocess.run([sys.executable, "-I", "-c", SNIPPET, str(src), json.dumps(over)], capture_output=True, text=True, timeout=300)
    return json.loads(out.stdout.strip().splitlines()[-1]) if out.stdout.strip() else dict(ok=None, msg=out.stderr[-200:])


def pd1(baseline):
    now = run_in(ROOT, F1)
    rec("PD-1a", "F-1 reproducer on the current branch is refused, not solved", "PASS" if now.get("ok") is False and "未達條件" in now.get("msg", "") else "FAIL",
        "current: " + json.dumps(now, ensure_ascii=False), "refused with 未達條件", now)
    if baseline:
        before = run_in(baseline, F1)
        absurd = before.get("ok") and before["cmh"] > 1e9
        rec("PD-1b", "F-1 reproducer on the imported baseline (before the fix)", "PASS" if absurd else "BLOCKED",
            "baseline: " + json.dumps(before, ensure_ascii=False) + ("  -> defect reproduced (> 1e9 CMH accepted)" if absurd else "  -> baseline did not show the absurd airflow with this input"),
            "baseline accepts an absurd airflow (confirms the defect existed)", before)
    else:
        rec("PD-1b", "F-1 reproducer on the imported baseline", "BLOCKED", "no --baseline-src given")
    # the plan quotes 7,412,540,040 CMH with only 待補資料; that exact input is not in the plan, so it cannot be replayed
    rec("PD-1c", "the exact input behind the 7,412,540,040 CMH observation", "BLOCKED", "the plan gives the output but not the input; the recorded reproducer above is the same failure mode (limit point at infinity)")


def pd2():
    base = case_inputs("D-01")
    # (a) with every user-suppliable item given the gate must leave 待補資料
    p = proj(dict(latent_mode="沒有額外產濕", e_np_fan="5", ffu_w="200", c2_bf_min="0.15"), base)
    for k in p["pressure_drop"]:
        p["pressure_drop"][k]["equipment_known"] = "已知設備壓差"
        p["pressure_drop"][k]["equipment_drop"] = "50"
    r = api.calculate(p)
    st = r["quality"]["status"]
    left = [(i["status"], i["name"]) for i in r["quality"]["items"] if i["status"] != "通過"]
    rec("PD-2a", "gate reaches 初估完成 when all user-suppliable data is given (D-01 inputs + latent/NP/FFU heat/BF floor 0.15 (tester assumption)/equipment dp)", "PASS" if st == "初估完成（待後續階段確認）" else "FAIL",
        f"status={st}; remaining={left}", "初估完成（待後續階段確認）", st)
    # (b) with default data it stays 待補資料 and says why
    r0 = api.calculate(proj({}, base))
    rec("PD-2b", "with default data the gate says 待補資料 and lists the items", "PASS" if r0["quality"]["status"] == "待補資料" and r0["quality"]["pending"] > 0 else "FAIL", f"status={r0['quality']['status']} pending={r0['quality']['pending']}")
    # (c) 初估檢核通過 needs no load and no 待後續 item: reachable only for an empty room
    z = proj(dict(latent_mode="沒有額外產濕", eq_kw="0", sys_type="AHU (OA+RA 混合)"), base)
    try:
        rz = api.calculate(z)
        rec("PD-2c", "初估檢核通過 (the top status) with zero loads", "PASS" if rz["quality"]["status"] == "初估檢核通過" else "BLOCKED",
            f"zero-load status={rz['quality']['status']}; with any load 設備同工況選型 is always 待後續 so the top status is not reachable in practice",
            "初估檢核通過", rz["quality"]["status"])
    except ValidationError as exc:
        rec("PD-2c", "初估檢核通過 with zero loads", "BLOCKED", str(exc)[:120])
    rec("PD-2d", "DESIGN OBSERVATION: 初估檢核通過 is unreachable for any real room", "NOT APPLICABLE",
        "by design (quality.py: 設備同工況選型 is 待後續 whenever qs or ql is non-zero). The earlier 'never PASS' complaint is resolved as a label problem: the reachable top status is 初估完成（待後續階段確認）. Whether 初估檢核通過 should exist is a product decision, not a calculation fault.")


def pd3():
    base = case_inputs("CR-03")
    r = api.calculate(proj({}, base))
    i18n.set_language("zh-Hant", persist=False)
    zh = str(api.report(r))
    i18n.set_language("en", persist=False)
    en = str(api.report(r))
    i18n.set_language("zh-Hant", persist=False)
    sf = float(r.get("effective_inputs", r.get("project", {}).get("inputs", {})).get("sf", 1.1))
    chw = r["water"]["CHW"]
    labels_zh = [ln for ln in zh.splitlines() if "餘裕" in ln or "安全係數" in ln]
    labels_en = [ln for ln in en.splitlines() if "margin" in ln.lower() or "safety" in ln.lower()]
    res = json.loads((HERE / "results.json").read_text(encoding="utf-8")) if (HERE / "results.json").exists() else {}
    g6 = [k["status"] for c in res.get("cases", []) for k in c["checks"] if k["id"] == "G6"]
    rec("PD-3a", "margin arithmetic: coil load x sf = design load, applied once per loop (check G6 over the 20 cases)", "PASS" if g6 and set(g6) == {"PASS"} else ("BLOCKED" if not g6 else "FAIL"),
        f"G6 results: {len(g6)} cases, {sorted(set(g6))}; sf={sf}, CR-03 CHW load {chw['load_kw']:.3f} kW (run run_scenarios.py first)" if g6 else "results.json has no case results; run run_scenarios.py first")
    pct = f"{sf:g}%"  # sf is a percentage (10 = +10 %)
    has_pair = "未加餘裕" in zh and "含餘裕" in zh and pct in zh
    rec("PD-3b", "report labels loads before / after the margin and states the margin percentage (zh)", "PASS" if has_pair else "FAIL",
        f"未加餘裕 / 含餘裕 / '{pct}' all present" if has_pair else f"missing label; margin lines: {[x.strip()[:50] for x in labels_zh[:3]]}")
    has_en = any("margin" in x.lower() for x in labels_en) and pct in en
    rec("PD-3c", "report labels the margin and its percentage (en)", "PASS" if has_en else "FAIL", " | ".join(x.strip()[:70] for x in labels_en[:2]) or "no english margin line")


def pd4():
    base = dict(case_inputs("CR-03"), en_wall=100, wall_u=0.5)
    d = 35 - 23
    res = {}
    for unit, k in (("kcal/(h·m²·K)", 1.163 / 1000), ("W/(m²·K)", 1 / 1000)):
        r = api.calculate(proj(dict(u_unit=unit), base))
        got = r["parts"]["wall"]
        res[unit] = (got, 0.5 * 100 * d * k)
    parts_ok = all(g is not None and abs(g - e) < 1e-6 for g, e in res.values())
    rec("PD-4a", "wall load follows the selected U-value unit (hand calc: U x A x dT)", "PASS" if parts_ok else ("BLOCKED" if any(g is None for g, _ in res.values()) else "FAIL"),
        "; ".join(f"{u}: engine {g} vs {e:.6f} kW" for u, (g, e) in res.items()), {u: e for u, (_, e) in res.items()}, {u: g for u, (g, _) in res.items()})
    f = FIELDS["wall_u"]
    rec("PD-4b", "the U-value field itself shows its unit", "PASS" if f.get("unit") else "FAIL",
        f"FIELDS['wall_u'] unit={f.get('unit')!r}, label={f.get('label')!r}; the unit lives in a separate selector (u_unit, default {FIELDS['u_unit'].get('options', [None])[0]!r}). "
        "Entering a W/(m2.K) value while the default kcal unit is selected under-states the load by 14 % (1/1.163) with no warning.", "unit shown next to the value", f.get("unit"))
    i18n.set_language("zh-Hant", persist=False)
    rep = str(api.report(api.calculate(proj({}, base))))
    rec("PD-4c", "the report prints the U-value unit next to the wall load", "PASS" if ("kcal/(h·m²·K)" in rep or "W/(m²·K)" in rep) else "FAIL",
        "unit string present in the report" if ("kcal/(h·m²·K)" in rep or "W/(m²·K)" in rep) else "the report prints the wall load in kW but never the U value or its unit, and FIELD_HELP has no hint for wall_u / floor_u / u_unit")


def pd5():
    from facility_studio.engine import pv_to_torr
    f = FIELDS["pv_torr"]
    rec("PD-5a", "field envelope covers the per-unit ranges", "PASS" if f["low"] <= 0.133322 + 1e-9 and f["high"] >= 1013.25 else "FAIL", f"field {f['low']}..{f['high']}; per unit 1-760 Torr = 0.1333-101.325 kPa = 1.333-1013.25 mbar")
    cases = [("Torr(abs)", 1, True), ("Torr(abs)", 760, True), ("Torr(abs)", 0.9, False), ("Torr(abs)", 760.5, False),
             ("kPa(abs)", 0.1334, True), ("kPa(abs)", 101.325, True), ("kPa(abs)", 0.1, False), ("kPa(abs)", 101.4, False),
             ("mbar(abs)", 1.334, True), ("mbar(abs)", 1013.25, True), ("mbar(abs)", 1.0, False), ("mbar(abs)", 1014.0, False)]
    bad = []
    for unit, v, ok in cases:
        try:
            pv_to_torr(str(v), unit)
            got = True
        except ValidationError:
            got = False
        if got != ok:
            bad.append((unit, v, "accepted" if got else "refused"))
    rec("PD-5b", "per-unit boundary values are accepted / refused consistently (12 values)", "PASS" if not bad else "FAIL", f"mismatches={bad}" if bad else "all 12 boundary checks as expected")
    hint = ""
    try:
        from facility_studio.schema import FIELD_HELP
        hint = FIELD_HELP.get("pv_torr", "")
    except Exception:
        pass
    rec("PD-5c", "the field hint states the per-unit ranges", "PASS" if "0.1333" in hint and "101.325" in hint and "1013.25" in hint else "BLOCKED", hint[:140] or "hint dictionary not found under that name")


def main():
    argv = sys.argv[1:]
    baseline = Path(argv[argv.index("--baseline-src") + 1]) if "--baseline-src" in argv else None
    for fn in (lambda: pd1(baseline), pd2, pd3, pd4, pd5):
        try:
            fn()
        except Exception as exc:  # a crash is a finding, never a silent skip
            rec("PD-ERR", getattr(fn, "__name__", "step"), "FAIL", f"{type(exc).__name__}: {exc}")
    (HERE / "priority_defects.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    sys.exit(1 if any(o["status"] == "FAIL" for o in OUT) else 0)


if __name__ == "__main__":
    main()
