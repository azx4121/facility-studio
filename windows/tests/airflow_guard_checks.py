"""F-1 regression: a supply airflow that is a limit point at infinity must never be accepted, and ordinary
designs must not change. Also covers the quality-gate status vocabulary, the chilled-water margin note and the
PV pressure range, which were fixed in the same change.

Layers under test (see facility_studio/airflow_guard.py)
  numerical    humidity test independent of the trial airflow; search stops where the coil solver can follow
  physical     no finite airflow -> rejected with cause and remedy ("未達條件：…")
  engineering  load-driven airflow judged by its inflation over the baseline, never by a fixed air-change rate

Set FS_SRC to test another copy of the package (the mutation test does). Needs no display.
"""
import json
import math
import os
import re
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FS_SRC") or TESTS.parent).resolve()
sys.path.insert(0, str(ROOT))
from facility_studio import airflow_guard, api, i18n  # noqa: E402
from facility_studio.engine import pv_to_torr  # noqa: E402
from facility_studio.errors import InputError, ValidationError  # noqa: E402
from facility_studio.quality import STATUS_DEFERRED, STATUS_FAIL, STATUS_PENDING  # noqa: E402
from facility_studio.schema import FIELDS, default_project  # noqa: E402

checks = []
CJK = re.compile(r"[㐀-鿿]")
SYSTEMS = FIELDS["sys_type"]["options"]
AHU, MAU = SYSTEMS[1], SYSTEMS[0]
GATE = "供風量合理性"


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:300]))


def project(**over):
    p = default_project()
    for k, v in over.items():
        p["inputs"][k] = v if isinstance(v, str) else format(v, ".12g")
    return p


def run(**over):
    try:
        return api.calculate(project(**over)), None
    except ValidationError as exc:
        return None, exc


def gate(r):
    return next((i for i in r["quality"]["items"] if i["name"] == GATE), None)


def english(text):
    i18n.set_language("en", persist=False)
    try:
        return i18n.translate(text, "en")
    finally:
        i18n.set_language("zh-Hant", persist=False)


try:
    # 1. The reproducer from the stress campaign (room 22 C / 40 %RH, chilled water 7.06 C): physically impossible.
    F1 = {"oa_t": 45.69, "oa_rh": 53.81, "ra_t": 22, "ra_rh": 40, "chw2_in": 7.06, "eq_kw": 199.09, "en_L_A": 75.19, "en_W_A": 34.58, "en_H_A": 4.57, "ppl_A": 1}
    r, err = run(sys_type=AHU, **F1)
    check("F-1 reproducer is rejected, not solved at an absurd airflow", r is None and err is not None, "accepted" if r else "")
    msg = str(err)
    check("F-1 message states 未達條件, the cause and the chilled-water limit", msg.startswith("未達條件") and "任何風量都無法除濕" in msg and "冰水供水溫度須低於" in msg, msg[:160])
    check("F-1 message points at the chilled-water supply field", getattr(err, "field_name", None) == "chw2_in", getattr(err, "field_name", None))
    limit = float(re.search(r"須低於 ([\d.]+)°C", msg).group(1))
    check("F-1 message translates to English without Chinese", not CJK.search(english(msg)), english(msg)[:200])
    below, _ = run(sys_type=AHU, **{**F1, "chw2_in": limit - 0.05})
    check("following the stated limit makes the design solvable", below is not None and below["supply_room_cmh"] < 1e6, below and below["supply_room_cmh"])


except Exception as _exc:  # a crash is a failure with a name, not a traceback
    check('section 1 (The reproducer from the stress campaign (room 22 C / 40 %RH,) raised ' + type(_exc).__name__, False, repr(_exc))

try:
    # 2. Boundary scan: moisture-limited designs must be solved smoothly, flagged when impractical, rejected beyond the edge.
    for label, over in (("moderate latent load", dict(ra_rh=40, ppl_A=30, process_latent_kw=8)),
                        ("small latent load", dict(ra_rh=45, ppl_A=5)),
                        ("larger room", dict(ra_rh=40, ppl_A=60, en_L_A=40, en_W_A=30, process_latent_kw=15))):
        rows, rejected_from = [], None
        for k in range(0, 400):
            t = 5.0 + k * 0.01
            r, err = run(sys_type=AHU, chw2_in=t, **over)
            if r is None:
                rejected_from = t
                break
            rows.append((t, r))
        check(f"scan [{label}]: a feasible range exists and the edge is a rejection", len(rows) > 20 and rejected_from is not None, (len(rows), rejected_from))
        flows = [r["supply_room_cmh"] for _, r in rows]
        check(f"scan [{label}]: airflow never decreases as the chilled water gets warmer", all(b >= a * (1 - 1e-9) for a, b in zip(flows, flows[1:])))
        searched = [(t, r) for t, r in rows if r["airflow_basis"]["load_driven"]]
        check(f"scan [{label}]: moisture-limited designs are solved, not all rejected", len(searched) >= 3, len(searched))
        bad = [t for t, r in rows if r["airflow_basis"]["inflation"] > airflow_guard.INFLATION_FAIL + 1e-9 and (r["quality"]["status"] != STATUS_FAIL or gate(r)["status"] != "未達")]
        check(f"scan [{label}]: inflation above the feasible multiple is always 未達條件", not bad, bad[:3])
        ok_gate = [t for t, r in rows if r["airflow_basis"]["load_driven"] and r["airflow_basis"]["inflation"] <= airflow_guard.INFLATION_FAIL
                   and (r["airflow_basis"]["condition_number"] or 0) <= airflow_guard.CONDITION_FAIL and gate(r)["status"] != "通過"]
        check(f"scan [{label}]: designs inside both limits pass the gate", not ok_gate, ok_gate[:3])
        ill = [t for t, r in rows if (r["airflow_basis"]["condition_number"] or 0) > airflow_guard.CONDITION_FAIL and gate(r)["status"] != "未達"]
        check(f"scan [{label}]: an ill-conditioned moisture limit is 未達條件 even when the inflation is small", not ill, ill[:3])
        advice = [(t, gate(r)["detail"]) for t, r in rows if gate(r) and gate(r)["status"] == "未達"]
        nonsense = [(t, d[-110:]) for t, d in advice if (m := re.search(r"降至 ([\d.]+)°C 以下（目前 ([\d.]+)°C", d)) and float(m.group(1)) >= float(m.group(2))]
        check(f"scan [{label}]: the advice always asks for a lower chilled-water temperature than the current one", not nonsense, nonsense[:2])
        obeyed = []
        for t, d in advice[:6]:
            m = re.search(r"降至 ([\d.]+)°C 以下", d)
            if m:
                again, _ = run(sys_type=AHU, chw2_in=float(m.group(1)) - 0.005, **over)
                if again is not None and (gate(again) or {}).get("status") == "未達":
                    obeyed.append((t, m.group(1)))
        check(f"scan [{label}]: following the advice clears the gate", not obeyed, obeyed[:3])
        flipped = [i for i in range(1, len(rows)) if (gate(rows[i][1]) or {}).get("status") != (gate(rows[i - 1][1]) or {}).get("status") and (gate(rows[i - 1][1]) or {}).get("status") == "未達"]
        check(f"scan [{label}]: once 未達 the gate never recovers while the water warms", not flipped, flipped[:3])
        # When the sensible design airflow is the baseline, an inflation of 5 is exactly a 2 K supply difference.
        # When the circulation floor is the baseline the room already moves more air, and inflation is the criterion.
        dts = [r["airflow_basis"]["supply_dt_k"] for _, r in searched
               if r["airflow_basis"]["inflation"] <= airflow_guard.INFLATION_FAIL and r["airflow_basis"]["m_start_kg_s"] <= abs(r["qs"]) / airflow_guard.DESIGN_SUPPLY_DT_K * (1 + 1e-9)]
        check(f"scan [{label}]: passing designs on the sensible baseline keep the supply difference at or above the practical minimum",
              all(d >= airflow_guard.MIN_PRACTICAL_SUPPLY_DT_K * 0.95 for d in dts), min(dts) if dts else None)
        if label == "moderate latent load":
            fail_t, fail_r = next(((t, r) for t, r in rows if (gate(r) or {}).get("status") == "未達"), (None, None))
            needed = fail_r["airflow_basis"]["chw_needed_c"]
            text = gate(fail_r)["detail"]
            check("the advice names a chilled-water temperature and the numbers add up",
                  f"{math.floor(needed * 100) / 100:.2f}°C 以下" in text and "基準" in text and "倍" in text, text[:200])
            good, _ = run(sys_type=AHU, chw2_in=needed - 0.005, **over)
            bad_, _ = run(sys_type=AHU, chw2_in=needed + 0.005, **over)
            check("following the advice passes the gate; just above it does not",
                  good is not None and gate(good)["status"] == "通過" and bad_ is not None and gate(bad_)["status"] == "未達", (needed,))
            check("the gate text translates to English without Chinese", not CJK.search(english(text)), english(text)[:200])
            check("a moisture-limited airflow is also reported as a warning once it doubles",
                  any("供風量由" in w for _, r in rows if r["airflow_basis"]["inflation"] > 2 for w in r["warnings"]))


except Exception as _exc:  # a crash is a failure with a name, not a traceback
    check('section 2 (Boundary scan: moisture-limited designs must be solved smoot) raised ' + type(_exc).__name__, False, repr(_exc))

try:
    # 3. Cleanroom circulation is part of the baseline: high ACH never trips the gate by itself.
    golden = json.loads((TESTS / "fixtures" / "airflow_golden.json").read_text(encoding="utf-8"))
    high = [c for c in golden["cases"] if float(c["overrides"]["en_ach_A"]) >= 150 and not c["overrides"]["sys_type"].startswith("MAU")]
    flagged = []
    for c in high:
        r, _ = run(**c["overrides"])
        g = gate(r)
        if g and g["status"] == "未達" and r["airflow_basis"]["inflation"] <= airflow_guard.INFLATION_FAIL:
            flagged.append(c["overrides"])
    check(f"{len(high)} cleanroom cases with 150-500 ACH: the gate fails only when inflation exceeds the multiple", not flagged, flagged[:1])
    for ach in (150, 300, 500):
        r, _ = run(sys_type=AHU, en_ach_A=ach, chw2_in=6.4, ra_rh=40, ppl_A=30, process_latent_kw=8)
        check(f"ACH {ach}: moisture limit sits under the circulation, so the airflow is the circulation and is not flagged",
              r is not None and r["airflow_basis"]["governing"] == "循環風量／外氣下限" and not r["airflow_basis"]["load_driven"] and gate(r) is None, r and r["airflow_basis"]["governing"])
    for t in (6.7, 6.78):
        r, _ = run(sys_type=AHU, en_ach_A=300, chw2_in=t, ra_rh=40, ppl_A=30, process_latent_kw=8)
        check(f"ACH 300, chilled water {t} C (inside the physical edge): solvable, judged against the 300 ACH circulation, not flagged",
              r is not None and r["airflow_basis"]["m_start_kg_s"] >= r["airflow_basis"]["m_floor_kg_s"] * (1 - 1e-12) and gate(r) is None, r and r["airflow_basis"]["inflation"])
    r, err = run(sys_type=AHU, en_ach_A=300, chw2_in=6.8, ra_rh=40, ppl_A=30, process_latent_kw=8)
    check("ACH 300 beyond the physical edge is still rejected: no amount of circulation dries a room the coil cannot reach", r is None and "任何風量都無法除濕" in str(err), str(err)[:80])


except Exception as _exc:  # a crash is a failure with a name, not a traceback
    check('section 3 (Cleanroom circulation is part of the baseline: high ACH neve) raised ' + type(_exc).__name__, False, repr(_exc))

try:
    # 4. MAU outdoor air and FFU circulation are separate quantities and this search does not touch them.
    r, _ = run(sys_type=MAU)
    check("MAU: the airflow search does not apply", r is not None and r["airflow_basis"]["applicable"] is False and gate(r) is None)
    check("MAU: outdoor air (oa_room_cmh) and FFU circulation (ffu_total_cmh) stay distinct", r["oa_room_cmh"] != r["ffu_total_cmh"] or r["ffu_total_cmh"] == 0, (r["oa_room_cmh"], r["ffu_total_cmh"]))
    unchanged = 0
    for c in golden["cases"]:
        if c["overrides"]["sys_type"].startswith("MAU"):
            r, _ = run(**c["overrides"])
            e = c["expect"]
            unchanged += r is not None and r["oa_mass"] == e["oa_mass"] and r["circulation_cmh"] == e["circulation_cmh"] and r["counts"] == e["counts"] and r["supply_room_cmh"] == e["supply_room_cmh"]
    check("MAU golden cases: outdoor air, circulation, FFU/DCC counts identical to before", unchanged == golden["by_system"]["MAU"], (unchanged, golden["by_system"]["MAU"]))


except Exception as _exc:  # a crash is a failure with a name, not a traceback
    check('section 4 (MAU outdoor air and FFU circulation are separate quantities ) raised ' + type(_exc).__name__, False, repr(_exc))

def same(a, b, rel=1e-9):
    """Equal up to floating-point round-off between platforms (libm differs in the last digits); a real change is >= 1e-6."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], rel) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y, rel) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(a - b) <= rel * max(1.0, abs(a), abs(b))
        except TypeError:
            return False
    return a == b


try:
    # 5. Ordinary designs are untouched: numbers identical to the recording made before the fix.
    lost, differ, status_ok = [], [], 0
    for c in golden["cases"]:
        r, err = run(**c["overrides"])
        if r is None:
            lost.append(str(err)[:60]); continue
        e = c["expect"]
        got = dict(supply_room_cmh=r["supply_room_cmh"], mass=r["summer"]["mass"], qs=r["qs"], q_total_kw=r["q_total_kw"], supply=r["summer"]["supply"], enter=r["summer"]["enter"],
                   winter_mass=r["winter"]["mass"], water={k: [w["lpm"], w["load_kw"], w["velocity_mps"]] for k, w in r["water"].items()}, counts=r["counts"],
                   circulation_cmh=r["circulation_cmh"], oa_mass=r["oa_mass"])
        d = [k for k in got if not same(got[k], e[k])]
        if d:
            differ.append((d[:2], c["overrides"]["sys_type"][:3]))
        if r["quality"]["status"] == e["status"]:
            status_ok += 1
        elif not (r["quality"]["status"] == STATUS_FAIL and gate(r) and gate(r)["status"] == "未達" and r["airflow_basis"]["inflation"] > airflow_guard.INFLATION_FAIL):
            differ.append(("status changed without the gate", e["status"], r["quality"]["status"]))
    check(f"{len(golden['cases'])} ordinary cases (high ACH {golden['high_ach_cases']}, circulation floor {golden['circulation_floor_cases']}): every number identical", not differ and not lost, (differ[:2], lost[:2]))
    check("status of an ordinary case changes only when the new gate finds an impractical airflow", status_ok >= len(golden["cases"]) - 40, status_ok)


except Exception as _exc:  # a crash is a failure with a name, not a traceback
    check('section 5 (Ordinary designs are untouched: numbers identical to the rec) raised ' + type(_exc).__name__, False, repr(_exc))

try:
    # 6. Quality-gate vocabulary: what the user can fix and what needs a later stage are different.
    r, _ = run()
    q = r["quality"]
    check("default project: user-fixable items and later-stage items are counted separately", q["status"] == STATUS_PENDING and q["pending"] >= 1 and q["deferred"] >= 1, (q["pending"], q["deferred"]))
    p = project(e_np_fan="30", c2_bf_min="0.1")
    p["pressure_drop"]["CHW"].update(equipment_known="已知設備壓差", equipment_drop="60")
    r = api.calculate(p)
    check("with the data supplied only later-stage items remain, and the status says so", r["quality"]["status"] == STATUS_DEFERRED and r["quality"]["pending"] == 0 and r["quality"]["failed"] == 0 and r["quality"]["deferred"] >= 1,
          (r["quality"]["status"], r["quality"]["pending"], r["quality"]["deferred"]))
    check("item statuses use a closed vocabulary", {i["status"] for i in r["quality"]["items"]} <= {"通過", "待資料", "待後續", "未達"})
    from facility_studio.ui_common import quality_text  # noqa: E402
    check("the status line shows the three counts", "待後續階段" in quality_text(r["quality"]), quality_text(r["quality"])[:80])
    check("status words translate to English", all(not CJK.search(english(w)) for w in (STATUS_FAIL, STATUS_PENDING, STATUS_DEFERRED, quality_text(r["quality"]))))


except Exception as _exc:  # a crash is a failure with a name, not a traceback
    check('section 6 (Quality-gate vocabulary: what the user can fix and what need) raised ' + type(_exc).__name__, False, repr(_exc))

try:
    # 7. Chilled-water pipe and pump flows say whether they include the capacity margin.
    for sf, expect in ((10, "含 10% 容量餘裕"), (0, "未加容量餘裕"), (20, "含 20% 容量餘裕")):
        r, _ = run(sf=sf)
        text = str(api.report(r))
        pipe = next(l for l in text.splitlines() if "MCHW" in l and "LPM" in l and "計算需求值" in l)
        pump = [l for l in text.splitlines() if "揚程" in l and "計算需求值" in l]
        check(f"sf={sf}: the pipe flow line states the margin basis", expect in pipe, pipe[:120])
        check(f"sf={sf}: the pump flow line states it too", pump and expect in pump[0], pump[:1])
        check(f"sf={sf}: chiller line still says the peak is without margin", "未加餘裕" in text)
    check("the margin note translates to English", all(not CJK.search(english(w)) for w in ("（含 10% 容量餘裕）", "（未加容量餘裕）")))


except Exception as _exc:  # a crash is a failure with a name, not a traceback
    check('section 7 (Chilled-water pipe and pump flows say whether they include t) raised ' + type(_exc).__name__, False, repr(_exc))

try:
    # 8. PV absolute pressure: the stated range is the enforced range, in every unit.
    for unit in ("Torr(abs)", "kPa(abs)", "mbar(abs)"):
        try:
            pv_to_torr("1e9", unit)
        except InputError as exc:
            text = str(exc)
        lo, hi = map(float, re.search(r"介於 ([\d.e+-]+)～([\d.e+-]+) ", text).groups())
        inside = []
        for v in (lo, hi):
            try:
                pv_to_torr(repr(v), unit); inside.append(True)
            except InputError:
                inside.append(False)
        outside = []
        for v in (lo * 0.999, hi * 1.001):
            try:
                pv_to_torr(repr(v), unit); outside.append(True)
            except InputError:
                outside.append(False)
        check(f"PV {unit}: the bounds quoted in the message are accepted and just outside is rejected", all(inside) and not any(outside), (lo, hi, inside, outside))
        check(f"PV {unit}: the message translates to English", not CJK.search(english(text)), english(text)[:160])
    from facility_studio.schema import FIELD_HELP  # noqa: E402
    check("PV hint lists the range for each unit", all(x in FIELD_HELP["pv_torr"] for x in ("760 Torr", "101.325 kPa", "1013.25 mbar")), FIELD_HELP["pv_torr"][:80])
    check("PV field envelope matches the model range instead of 1e-06..1e6", (FIELDS["pv_torr"]["low"], FIELDS["pv_torr"]["high"]) == (0.133322, 1013.25), (FIELDS["pv_torr"]["low"], FIELDS["pv_torr"]["high"]))


except Exception as _exc:  # a crash is a failure with a name, not a traceback
    check('section 8 (PV absolute pressure: the stated range is the enforced range) raised ' + type(_exc).__name__, False, repr(_exc))

failed = [c for c in checks if not c["passed"]]
if "FS_SRC" not in os.environ:
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence" / "Airflow_Guard_Checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"airflow guard checks: {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
