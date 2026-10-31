"""Mutation test of the stress suite: plant a known engineering error, the suite must notice."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import os
HERE = Path(__file__).resolve().parent
SRC = Path(os.environ["FS_SRC"]).resolve()  # the Source/windows directory under test
PY = sys.executable
OUT = HERE / "mutants"
OUT.mkdir(exist_ok=True)

MUTATIONS = [  # (name, file, old, new, scripts that should notice)
    ("M1 latent term of enthalpy off by 100 kJ/kg", "utils.py", "return CP_DA * t + w * (H_V0 + CP_V * t)", "return CP_DA * t + w * (H_V0 - 100 + CP_V * t)", ["ab"]),
    ("M2 air volume ignores atmospheric pressure", "utils.py", "(1 + w / MW_RATIO) / p\n", "(1 + w / MW_RATIO) / 101.325\n", ["ab"]),
    ("M3 condensate heat dropped from coil water load", "engine.py", 'liquid = max(0, cond) * 4.1868 * b["t"]', "liquid = 0", ["ab"]),
    ("M4 chilled-water flow uses fixed cp 4.0", "engine.py", 'loads[key] * 60000 / (fluid["rho"] * fluid["cp"] * n(delta))', 'loads[key] * 60000 / (fluid["rho"] * 4.0 * n(delta))', ["ab"]),
    ("M5 pipe friction 30 % too high", "utils.py", "f * length / diameter * velocity_pressure\n            if mode", "f * length / diameter * velocity_pressure * 1.3\n            if mode", ["ab"]),
    ("M6 US refrigeration ton constant 3.0 kW", "utils.py", "US_RT_KW = 3.5168528420667", "US_RT_KW = 3.0", ["ab"]),
    ("M7 numeric upper bound no longer enforced", "utils.py", "    if high is not None and x > high:\n        raise InputError", "    if False:\n        raise InputError", ["d"]),
    ("M8 inactive FFU field leaks into room heat (guard removed too)", [("engine.py", '"fan": n("fan_room_kw") + ffu_count * n("ffu_w") / 1000,', '"fan": n("fan_room_kw") + ffu_count * n("ffu_w") / 1000 + n("ffu_w") / 1000,'), ("field_state.py", "        out[k] = DEFAULTS[k]\n    for k in optional_inactive", "        out[k] = DEFAULTS[k] if k != \"ffu_w\" else i[k]\n    for k in optional_inactive")], ["c"]),
    ("M9 DCC unit count ignores the capacity margin", "engine.py", 'math.ceil(dcc_design * sf / rtkw / n("en_dcc_rt") - 1e-12) if is_mau else 0', 'math.ceil(dcc_design / rtkw / n("en_dcc_rt") - 1e-12) if is_mau else 0', ["f"]),
    ("M10 floor heat gain sign reversed", "engine.py", '* (n("floor_adj_t") - n("ra_t"))', '* (n("ra_t") - n("floor_adj_t"))', ["f"]),
    ("M11 continuous-load design current factor 1.0 instead of 1.25", "utils.py", "if kind == \"連續負載\":\n            design = current * 1.25", "if kind == \"連續負載\":\n            design = current * 1.0", ["f"]),
]


def run(script, args, cwd):
    p = subprocess.run([PY, str(HERE / script)] + args, cwd=cwd, capture_output=True, text=True, timeout=1500)
    return p.stdout + p.stderr


rows = []
only = sys.argv[1:]
for name, *spec, scripts in MUTATIONS:
    edits = spec[0] if isinstance(spec[0], list) else [tuple(spec)]
    if only and not any(name.startswith(o) for o in only):
        continue
    work = OUT / name.split()[0]
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(SRC / "facility_studio", work / "facility_studio", ignore=shutil.ignore_patterns("__pycache__"))
    applied = True
    for f, old, new in edits:
        path = work / "facility_studio" / f
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            rows.append((name, "MUTATION NOT APPLIED", f"{f}: {text.count(old)} matches"))
            applied = False
            break
        path.write_text(text.replace(old, new), encoding="utf-8")
    if not applied:
        print("NOT APPLIED", name, rows[-1][2]); continue
    killed_by = []
    for sc in scripts:
        if sc == "ab":
            out = run("stress_ab.py", ["300", str(work / "ab.json")], work)
            fails = [l.split()[1] for l in out.splitlines() if l.startswith("FAIL")]
            if fails or "Traceback" in out:
                killed_by.append("AB:" + ",".join(fails or ["crash"]))
        elif sc == "d":
            out = run("stress_d.py", ["60", str(work / "d.json")], work)
            kinds = [l for l in out.splitlines() if l.startswith("== ")]
            if kinds or "Traceback" in out:
                killed_by.append("D:" + ",".join(k[3:].split()[0] for k in kinds or ["crash"]))
        elif sc == "f":
            out = run("stress_f.py", [str(work / "f.json")], work)
            fails = [l.split()[1] for l in out.splitlines() if l.startswith("FAIL")]
            if fails or "Traceback" in out:
                killed_by.append("F:" + ",".join(fails or ["crash"]))
        elif sc == "c":
            out = run("stress_c.py", [str(work / "c.json")], work)
            fails = [" ".join(l.split()[1:3]) for l in out.splitlines() if l.startswith("FAIL")]
            if fails or "Traceback" in out:
                killed_by.append("C:" + ",".join(fails or ["crash"]))
    rows.append((name, "KILLED" if killed_by else "SURVIVED", killed_by))
    print(f"{rows[-1][1]:9} {name}  {killed_by}", flush=True)

json.dump(rows, open(HERE / "results" / "mutation.json", "w"), ensure_ascii=False, indent=1)
print(f"\nkilled {sum(1 for r in rows if r[1]=='KILLED')} / {len(rows)}")
