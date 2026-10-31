"""Optional calculation inputs: workspace persistence and inactive-draft validation.

Limits follow v2's engine.validate_project. Absent keys use each reader's own
default; this suite never assumes a default device limit for c2_bf_min.
"""

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio import api as a
from facility_studio.errors import ValidationError
from facility_studio.field_state import effective_main, main_inactive, optional_inactive
from facility_studio.optional_inputs import FIELD_EXTRA_BOUNDS, OPTIONAL_INPUTS
from facility_studio.project_store import save_project_file
from facility_studio.schema import FIELDS, default_project
from facility_studio.workspace_store import new_workspace, read_workspace, validate_workspace

checks = []


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:200]))


def rejects(name, fn, field=None):
    try:
        fn()
    except ValidationError as e:
        check(name, field is None or e.field_name == field, f"field={e.field_name} {e}")
        return
    except Exception as e:  # any other exception type is itself a failure
        check(name, False, f"{type(e).__name__}: {e}")
        return
    check(name, False, "accepted")


def accepts(name, fn):
    try:
        value = fn()
    except Exception as e:
        check(name, False, f"{type(e).__name__}: {e}")
        return None
    check(name, True)
    return value


MAU = next(o for o in FIELDS["sys_type"]["options"] if o.startswith("MAU"))
AHU = next(o for o in FIELDS["sys_type"]["options"] if o.startswith("AHU"))
ROOM = "室內熱濕平衡（定風量）"
LEGACY_WINTER = "外氣處理基準（舊版）"
# Reader defaults reported for v2: winter.py 100/40, quality.py 0.5,
# engine.py c2_bf_min 0.0, contributions.py largest motor 0.
READER_DEFAULTS = {
    "winter_ffu_ratio": "100",
    "winter_mau_max_t": "40",
    "coil_pinch_min_k": "0.5",
    "c2_bf_min": "0",
    "e_up_largest_motor_kw": "0",
    "e_np_largest_motor_kw": "0",
}


def project(**inputs):
    p = default_project()
    p["inputs"].update(inputs)
    return p


def flat(x, path=""):
    out = {}
    if isinstance(x, dict):
        for k, v in x.items():
            if not path and k in ("project", "hash"):
                continue
            out.update(flat(v, f"{path}/{k}"))
    elif isinstance(x, (list, tuple)):
        for n, v in enumerate(x):
            out.update(flat(v, f"{path}[{n}]"))
    else:
        out[path] = x
    return out


def same_outputs(r1, r2, echo=True):
    a1, a2 = flat(r1), flat(r2)
    if not echo:  # effective_inputs echoes which optional keys were present
        a1 = {k: v for k, v in a1.items() if not k.startswith("/effective_inputs/")}
        a2 = {k: v for k, v in a2.items() if not k.startswith("/effective_inputs/")}
    diff = [k for k in set(a1) | set(a2) if a1.get(k) != a2.get(k)]
    return not diff, diff[:5]


# 1. Workspace persistence (Codex finding 1).
shipped = json.loads((ROOT / "Default_Project.json").read_text(encoding="utf-8"))
shipped["inputs"]["winter_ffu_ratio"] = "50"
ws = accepts("Default_Project + winter_ffu_ratio=50 creates workspace", lambda: new_workspace(shipped))
if ws:
    check("workspace keeps optional value", ws["main"]["inputs"].get("winter_ffu_ratio") == "50")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "ws.json"
        save_project_file(path, ws)
        back = accepts("workspace file reads back", lambda: read_workspace(path))
        check("workspace JSON round trip is lossless", back == ws)
        main = accepts("read_project extracts main from workspace", lambda: a.read_project(path))
        check("read_project keeps optional value", bool(main) and main["inputs"].get("winter_ffu_ratio") == "50")
        check("second validate_workspace is idempotent", validate_workspace(copy.deepcopy(back)) == back)

r = accepts("active winter_ffu_ratio=50 calculates", lambda: a.calculate(project(sys_type=MAU, winter_model=ROOM, winter_ffu_ratio="50")))
check("active optional value reaches calculation", bool(r) and r["winter_room"]["winter_ffu_ratio"] == 50.0)

# 2. Legacy files and reader defaults; no assumed bypass-factor floor.
for system in (MAU, AHU):
    old = project(sys_type=system, winter_model=ROOM)
    for key in OPTIONAL_INPUTS:
        old["inputs"].pop(key, None)
    accepts(f"{system[:3]} legacy project without optional keys creates workspace", lambda old=old: new_workspace(old))
    legacy = accepts(f"{system[:3]} legacy project calculates", lambda old=old: a.calculate(old))
    explicit = copy.deepcopy(old)
    explicit["inputs"].update(READER_DEFAULTS)
    if legacy:
        ok, diff = same_outputs(legacy, a.calculate(explicit), echo=False)
        check(f"{system[:3]} absent optional keys equal reader defaults", ok, diff)
        check(f"{system[:3]} c2 bypass floor stays 0 without project basis", legacy["summer"]["c2"].get("bf_min", 0.0) == 0.0,
              legacy["summer"]["c2"].get("bf_min"))
check("effective_main adds no c2_bf_min", "c2_bf_min" not in effective_main(default_project()["inputs"]))

# 3. Unknown and missing keys stay rejected.
unknown = project(foo="1")
rejects("validate_project rejects unknown key", lambda: a.validate_project(unknown), "foo")
rejects("new_workspace rejects unknown key", lambda: new_workspace(unknown), "foo")
missing = default_project()
del missing["inputs"]["oa_t"]
rejects("validate_project rejects missing FIELDS key", lambda: a.validate_project(missing), "oa_t")
rejects("new_workspace rejects missing FIELDS key", lambda: new_workspace(missing), "oa_t")
doc = new_workspace(default_project())
doc["drafts"] = {"winter_ffu_ratio": {"source": "使用者輸入", "note": "草稿"}}
accepts("drafts accept optional key", lambda: validate_workspace(doc))
doc["drafts"] = {"foo": {"source": "使用者輸入", "note": "草稿"}}
rejects("drafts reject unknown key", lambda: validate_workspace(doc))

# 4. Active values: v2 limits kept; NaN/Inf/blank/text rejected with the field name.
active_context = {
    "winter_ffu_ratio": dict(sys_type=MAU, winter_model=ROOM),
    "winter_mau_max_t": dict(sys_type=MAU, winter_model=ROOM, mau_supply_t="15"),
    "coil_pinch_min_k": dict(),
    "c2_bf_min": dict(),
    "e_up_largest_motor_kw": dict(e_up_type="馬達負載"),
    "e_np_largest_motor_kw": dict(e_np_type="馬達負載"),
}
for key, context in active_context.items():
    p = project(**context)
    check(f"{key} is active in its test context", key not in optional_inactive(p["inputs"]))
    low, high = OPTIONAL_INPUTS[key]["bounds"]
    for value in (str(low), str(high)):
        q = copy.deepcopy(p)
        q["inputs"][key] = value
        # Bounds are an input-validation concern; an extreme value may still be
        # physically unreachable in calculate (for example a high BF floor).
        accepts(f"active {key}={value} (v2 limit) accepted", lambda q=q: a.validate_project(q))
    for value in ("nan", "inf", "-inf", "", "bad", "1e999", str(low - 0.001), str(high * 1.001 + 0.001)):
        q = copy.deepcopy(p)
        q["inputs"][key] = value
        rejects(f"active {key}={value!r} rejected", lambda q=q: a.calculate(q), key)
for key, (low, high) in FIELD_EXTRA_BOUNDS.items():
    p = project(**{key.replace("largest_hp", "type"): "馬達負載", key: str(high * 2)})
    rejects(f"active {key} above v2 limit rejected", lambda p=p: a.calculate(p), key)
rejects("winter_mau_max_t below mau_supply_t rejected",
        lambda: a.calculate(project(sys_type=MAU, winter_model=ROOM, mau_supply_t="22", winter_mau_max_t="20")),
        "winter_mau_max_t")
accepts("airflow_search_floor keeps v2 free text when active",
        lambda: a.calculate(project(sys_type=AHU, airflow_search_floor="circulation")))
rejects("non-string optional value rejected",
        lambda: a.validate_project(project(sys_type=AHU, coil_pinch_min_k=0.5)), "coil_pinch_min_k")

# 5. Inactive drafts are preserved and change no output.
inactive_context = {
    "winter_ffu_ratio": dict(sys_type=AHU),
    "winter_mau_max_t": dict(sys_type=MAU, winter_model=LEGACY_WINTER),
    "airflow_search_floor": dict(sys_type=MAU),
    "e_up_largest_motor_kw": dict(e_up_type="一般負載"),
    "e_np_largest_motor_kw": dict(e_np_type="連續負載"),
}
for key, context in inactive_context.items():
    base = project(**context)
    check(f"{key} is inactive in its test context", key in optional_inactive(base["inputs"]))
    baseline = a.calculate(base)
    for value in ("bad", "nan", "", "-1e999", "999999999"):
        q = copy.deepcopy(base)
        q["inputs"][key] = value
        result = accepts(f"inactive {key}={value!r} calculates", lambda q=q: a.calculate(q))
        if result:
            ok, diff = same_outputs(baseline, result)
            check(f"inactive {key}={value!r} leaves full output unchanged", ok, diff)
            check(f"inactive {key}={value!r} draft preserved", result["project"]["inputs"][key] == value)
            saved = accepts(f"inactive {key}={value!r} saves in workspace", lambda q=q: new_workspace(q))
            check(f"inactive {key}={value!r} survives workspace", bool(saved) and saved["main"]["inputs"][key] == value)

# 6. FIELDS-owned largest_hp: v557 behaviour restored, v2 cap kept when active.
for panel in ("up", "np"):
    key = f"e_{panel}_largest_hp"
    for value in ("bad", "nan", "", "2e6"):
        p = default_project()
        check(f"{key} inactive in default project", key in main_inactive(p["inputs"]))
        p["inputs"][key] = value
        accepts(f"inactive {key}={value!r} calculates", lambda p=p: a.calculate(p))
    q = project(**{f"e_{panel}_type": "馬達負載", key: "bad"})
    rejects(f"active {key}=bad rejected", lambda q=q: a.calculate(q), key)

# 7. Reactivation exposes the stored invalid draft.
p = project(sys_type=AHU, winter_model=ROOM, winter_ffu_ratio="bad")
accepts("invalid winter_ffu_ratio kept while inactive", lambda: a.calculate(p))
p["inputs"]["sys_type"] = MAU
rejects("reactivated invalid winter_ffu_ratio rejected", lambda: a.calculate(p), "winter_ffu_ratio")

failed = [c for c in checks if not c["passed"]]
destination = ROOT / "evidence" / "Optional_Inputs_Checks.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"optional input checks: {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
