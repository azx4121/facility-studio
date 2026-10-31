"""Group D: robustness. Boundaries, out-of-range, garbage text, random multi-field combinations."""
import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import collections
import json
import random
import sys
import time

from fs_lib import DEFAULT, NUMERIC, OPTIONS, SYSTEMS, bad_numbers, run

rng = random.Random(20261031)
out = collections.OrderedDict()
findings = []


def finding(kind, **detail):
    findings.append(dict(kind=kind, **detail))


# Which fields are live depends on the system type; inactive drafts are ignored on purpose (checked in group C).
INACTIVE = {}
for system in SYSTEMS:
    status, res = run(sys_type=system)
    INACTIVE[system] = set(res["inactive_fields"])

# D1. every ACTIVE numeric field at its exact low/high (accepted or cleanly rejected) and just outside (must be rejected)
edge = collections.Counter()
GARBAGE_MUST_REJECT = {"abc", "nan", "NaN", "inf", "-inf", "1e999", "None", "null", "--3", "1e", "0x10", "1,5"}
garbage = ["abc", "", "   ", "nan", "NaN", "inf", "-inf", "1e999", "1,5", "55", "0x10", "--3", "1e", "None", "null"]
garb = collections.Counter()
for system in SYSTEMS:
    live = [k for k in NUMERIC if k not in INACTIVE[system]]
    for key in live:
        f = NUMERIC[key]
        low, high = f["low"], f["high"]
        span = (high - low) or 1
        for label, value, must_reject in (("low", low, False), ("high", high, False),
                                          ("below", low - max(abs(span) * 1e-6, 1e-9), True),
                                          ("above", high + max(abs(span) * 1e-6, 1e-9), True)):
            status, res = run(sys_type=system, **{key: value})
            edge[(label, status)] += 1
            if status == "crash":
                finding("crash_at_edge", system=system, field=key, case=label, value=value, trace=res.splitlines()[-1])
            elif must_reject and status == "ok":
                finding("accepted_outside_bounds", system=system, field=key, case=label, value=value, bounds=[low, high])
            elif status == "ok" and bad_numbers(res):
                finding("nan_or_inf_at_edge", system=system, field=key, case=label, value=value, where=bad_numbers(res)[:2])
        for text in garbage:
            status, res = run(sys_type=system, **{key: text})
            garb[status] += 1
            if status == "crash":
                finding("crash_on_text", system=system, field=key, value=text, trace=res.splitlines()[-1])
            elif status == "ok" and text in GARBAGE_MUST_REJECT:
                finding("accepted_garbage", system=system, field=key, value=text)
            elif status == "ok" and bad_numbers(res):
                finding("nan_after_text", system=system, field=key, value=text)
out["D1_edge_counts"] = {f"{a}/{b}": n for (a, b), n in sorted(edge.items())}
out["D3_garbage_counts"] = dict(garb)

# D2. random multi-field combinations inside bounds, all four systems
N = int(sys.argv[1]) if len(sys.argv) > 1 else 800
keys = list(NUMERIC)
outcome = collections.Counter()
slow = []
status_hist = collections.Counter()
bad_gate = []
t_all = time.perf_counter()
for i in range(N):
    system = SYSTEMS[i % len(SYSTEMS)]
    over = {"sys_type": system}
    for key in rng.sample(keys, rng.randint(3, 12)):
        f = NUMERIC[key]
        low, high = f["low"], f["high"]
        # bounds are sometimes absurd (1e7); sample log-uniformly near the default so most runs are plausible, and at the edges 15% of the time
        d = float(DEFAULT[key]) if DEFAULT[key] not in ("", None) else low
        r = rng.random()
        if r < 0.075:
            v = low
        elif r < 0.15:
            v = high
        elif r < 0.6:
            v = min(high, max(low, d * rng.uniform(0.5, 1.6) if d else rng.uniform(low, min(high, low + 10))))
        else:
            v = rng.uniform(low, min(high, low + (high - low) * rng.choice((0.02, 0.1, 1.0))))
        over[key] = v
    for key in rng.sample(list(OPTIONS), rng.randint(0, 4)):
        over[key] = rng.choice(OPTIONS[key]["options"])
    t0 = time.perf_counter()
    status, res = run(**over)
    dt = time.perf_counter() - t0
    if dt > 2.0:
        slow.append((round(dt, 2), i))
    outcome[status] += 1
    if status == "crash":
        finding("crash_random", system=system, overrides={k: v for k, v in over.items() if k != "sys_type"}, trace=res.splitlines()[-1])
    elif status == "ok":
        nb = bad_numbers(res)
        if nb:
            finding("nan_or_inf_random", system=system, where=nb[:3])
        q = res["quality"]
        status_hist[q["status"]] += 1
        # gating consistency: status must follow the item list
        item_status = [it.get("status") for it in q["items"]]
        if q["status"] == "通過" and any(s in ("未達",) for s in item_status):
            bad_gate.append("pass_with_fail")
        if q["status"] == "通過" and any(s == "待資料" for s in item_status):
            bad_gate.append("pass_with_pending")
        if q["failed"] != sum(1 for s in item_status if s == "未達"):
            bad_gate.append("failed_count_mismatch")
    else:
        outcome["reject:" + type(res).__name__] += 0
out["D2_runs"] = N
out["D2_outcomes"] = dict(outcome)
out["D2_quality_status_of_ok_runs"] = dict(status_hist)
out["D2_gate_inconsistencies"] = dict(collections.Counter(bad_gate))
out["D2_slow_runs_over_2s"] = slow[:10]
out["D2_seconds"] = round(time.perf_counter() - t_all, 1)

counts = collections.Counter(f["kind"] for f in findings)
out["findings_by_kind"] = dict(counts)
Path = __import__("pathlib").Path
Path(sys.argv[2] if len(sys.argv) > 2 else "stress_d.json").write_text(json.dumps(dict(summary=out, findings=findings), ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
for kind in counts:
    print("==", kind, counts[kind])
    for f in [x for x in findings if x["kind"] == kind][:6]:
        print("   ", json.dumps(f, ensure_ascii=False)[:230])
