"""Record key outputs of ordinary feasible projects, to prove a later change leaves them untouched.

Run ONCE on the commit before the F-1 fix (63c9f2b); the result is tests/fixtures/airflow_golden.json.
It keeps every ordinary case the old solver accepted for a physical reason and drops the ones it accepted
only through the 1e-10 kg/kg tolerance (the defect itself), so the file never encodes the bug.
High circulation rates (cleanroom ACH up to 500) and the circulation-floor mode are included on purpose.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from facility_studio import api  # noqa: E402
from facility_studio.errors import ValidationError  # noqa: E402
from facility_studio.schema import default_project, FIELDS  # noqa: E402
from facility_studio.utils import state_trh  # noqa: E402

SYSTEMS = FIELDS["sys_type"]["options"]
CLIMATES = [(35, 70, 8, 70, 101.325), (33, 90, 22, 85, 101.325), (46, 15, -5, 40, 95), (30, 50, -25, 60, 100),
            (28, 50, -10, 40, 70), (30, 100, 5, 100, 101.325), (26, 55, 10, 65, 101.325)]
rng = random.Random(20261031)


def run(overrides):
    p = default_project()
    for k, v in overrides.items():
        p["inputs"][k] = v if isinstance(v, str) else format(v, ".12g")
    try:
        return api.calculate(p)
    except ValidationError:
        return None


def digest(r):
    return dict(
        supply_room_cmh=r["supply_room_cmh"], mass=r["summer"]["mass"], qs=r["qs"], q_total_kw=r["q_total_kw"],
        supply=r["summer"]["supply"], enter=r["summer"]["enter"], winter_mass=r["winter"]["mass"],
        water={k: [w["lpm"], w["load_kw"], w["velocity_mps"]] for k, w in r["water"].items()},
        counts=r["counts"], circulation_cmh=r["circulation_cmh"], oa_mass=r["oa_mass"],
        status=r["quality"]["status"], failed=r["quality"]["failed"],
    )


cases, dropped = [], 0
attempts = 0
while len(cases) < 560 and attempts < 4000:
    attempts += 1
    st, sr, wt, wr, pk = CLIMATES[rng.randrange(len(CLIMATES))]
    o = dict(sys_type=SYSTEMS[attempts % 4], atm_kpa=pk, oa_t=st + rng.uniform(-2, 2), oa_rh=min(100, max(0, sr + rng.uniform(-8, 8))),
             ow_t=wt + rng.uniform(-3, 3), ow_rh=min(100, max(0, wr + rng.uniform(-8, 8))), ra_t=rng.choice((20, 22, 23, 24, 26)),
             ra_rh=rng.choice((30, 35, 40, 45, 50, 55, 60)), chw2_in=rng.uniform(5, 10), dt_chw=rng.choice((4, 5, 6, 7)),
             eq_kw=rng.uniform(0, 150), sf=rng.choice((0, 10, 15, 20)), en_L_A=rng.uniform(10, 60), en_W_A=rng.uniform(8, 40),
             en_H_A=rng.uniform(3, 6), en_ach_A=rng.choice((0, 8, 8, 30, 60, 150, 300, 500)), ppl_A=rng.randint(0, 80))
    if rng.random() < 0.15:
        o["airflow_search_floor"] = "circulation"
    r = run(o)
    if r is None:
        continue
    if not r["summer"]["mass"] or r["summer"]["mass"] <= 0:
        continue
    e, room, oa = r["effective_inputs"], r["room"], r["oa"]
    if not o["sys_type"].startswith("MAU"):
        minw = state_trh(float(e["chw2_in"]) + float(e["coil_approach"]), 100, float(e["atm_kpa"]))["w"]
        lam = r["oa_mass"] * (oa["w"] - room["w"]) + r["moisture"]
        exact = (room["w"] - r["moisture"] / r["summer"]["mass"]) >= minw - 1e-10 or lam <= 1e-12
        if not exact:
            dropped += 1  # the defect: feasible only by tolerance at an enormous airflow
            continue
    cases.append(dict(overrides={k: (v if isinstance(v, str) else format(v, ".12g")) for k, v in o.items()}, expect=digest(r)))

out = ROOT / "tests" / "fixtures" / "airflow_golden.json"
out.write_text(json.dumps(dict(
    recorded_on="63c9f2b (before the F-1 fix)", cases=cases, dropped_tolerance_only=dropped, attempts=attempts,
    by_system={s[:3]: sum(1 for c in cases if c["overrides"]["sys_type"] == s) for s in SYSTEMS},
    high_ach_cases=sum(1 for c in cases if float(c["overrides"]["en_ach_A"]) >= 150),
    circulation_floor_cases=sum(1 for c in cases if c["overrides"].get("airflow_search_floor") == "circulation"),
), ensure_ascii=False, indent=0), encoding="utf-8")
print(len(cases), "cases recorded;", dropped, "tolerance-only (defect) cases excluded;", out.stat().st_size // 1024, "KiB")
