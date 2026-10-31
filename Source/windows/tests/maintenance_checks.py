"""Psychrometric round trips, printed-report checks and corrupt table inputs."""

import copy
import itertools
import json
import math
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from facility_studio.database import load_tables
from facility_studio.errors import ValidationError
from facility_studio.quick_tools import air_process, mix_air, psychrometric
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_reports import tool_report
from facility_studio.simple_schema import defaults

checks = []
cases = []


def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))
    assert condition, name


def close(name, actual, expected, absolute=1e-8):
    check(name, math.isclose(actual, expected, rel_tol=1e-8, abs_tol=absolute))


def reject(name, callback, field=None, code=None):
    try:
        callback()
    except ValidationError as error:
        check(name, (field is None or error.field_name == field)
              and (code is None or error.code == code))
    else:
        check(name, False)


for index, (t, rh, p) in enumerate(itertools.product(
    (-50, -20, 0, 22, 35), (1, 10, 50, 70, 99, 100), (60, 101.325, 120)
)):
    name = f"air_{index:03d}"
    original = psychrometric("乾球＋RH", t, rh, p)
    for mode, first, second in (
        ("乾球＋露點", t, original["dewpoint_c"]),
        ("乾球＋濕球", t, original["wetbulb_c"]),
        ("焓＋含濕比", original["h"], original["w"] * 1000),
    ):
        restored = psychrometric(mode, first, second, p)
        close(name + mode + "_w", restored["w"], original["w"], 1e-10)
        close(name + mode + "_rh", restored["rh"], rh, 1e-7)
        close(name + mode + "_h", restored["h"], original["h"], 1e-8)

    inputs = defaults("air")
    inputs.update(temperature=str(t), rh=str(rh), atmosphere=str(p))
    result = calculate_tool("air", inputs)
    text = tool_report(result, inputs)
    # Back-calculate from the printed values, allowing only display rounding.
    printed_w = float(re.search(r"含濕比 ([\d,.-]+)g/kg", text)[1].replace(",", "")) / 1000
    printed_h = float(re.search(r"空氣焓值：([\d,.-]+)", text)[1].replace(",", ""))
    from_printed_w = 1.006 * t + printed_w * (2501 + 1.86 * t)
    tolerance = 0.005 + 0.0000005 * abs(2501 + 1.86 * t) + 1e-8
    close(name + "_report_enthalpy", printed_h, from_printed_w, tolerance)
    close(name + "_report_w", printed_w, result["state"]["w"], 0.0000005 + 1e-10)
    check(name + "_finite", math.isfinite(result["state"]["wetbulb_c"]))
    cases.append(dict(id=name, dry_bulb_c=t, rh_percent=rh, pressure_kpa=p))

for function, args in (
    (psychrometric, ("乾球＋RH", 22, 50)),
    (mix_air, (35, 70, 1000, 22, 50, 4000)),
    (air_process, (35, 70, 15, 95, 5000)),
):
    for pressure in ("", "NaN", 0, 50, 59.999, 120.001):
        reject(function.__name__ + "_pressure_" + str(pressure),
               lambda f=function, a=args, p=pressure: f(*a, pressure=p), "pressure")

for function, args, bad_index, field in (
    (psychrometric, ["乾球＋RH", 22, 50], 1, "first"),
    (psychrometric, ["乾球＋RH", 22, 50], 2, "second"),
    (mix_air, [35, 70, 1000, 22, 50, 4000], 0, "t1"),
    (mix_air, [35, 70, 1000, 22, 50, 4000], 4, "rh2"),
    (air_process, [35, 70, 15, 95, 5000], 2, "t2"),
    (air_process, [35, 70, 15, 95, 5000], 3, "rh2"),
):
    args[bad_index] = "bad"
    reject(function.__name__ + "_structured_" + field,
           lambda f=function, a=args: f(*a), field)

table = load_tables()
documents = [[], None, True, {**table, "schema_version": True},
             {**table, "source": []}, {**table, "version": " "},
             {**table, "tables": None}]
for key, bad in (
    ("NFB_SIZES", None), ("NFB_SIZES", {}), ("NFB_SIZES", [10, 10]),
    ("NFB_SIZES", [20, 10]), ("NFB_SIZES", [True]),
    ("VOLTAGE_MAP", []), ("VOLTAGE_MAP", {"": 380}),
    ("GAS_DESIGN_VELOCITY_MPS", True), ("CLEANROOM_DB", []),
    ("CLEANROOM_DB", {}), ("CLEANROOM_DB", {"test": True}),
    ("CLEANROOM_DB", {"test": {"ach": True, "pressure": 10}}),
    ("WIRE_DB", [None]), ("PIPE_DB", [{"id": 16.1, "name": []}]),
    ("HVAC_PIPES", [{"id_mm": 15.8, "size": " ", "max_flow_lpm": 12}]),
):
    candidate = copy.deepcopy(table)
    candidate["tables"][key] = bad
    documents.append(candidate)

with tempfile.TemporaryDirectory(prefix="facility_table_validation_") as directory:
    path = Path(directory) / "tables.json"
    for index, document in enumerate(documents):
        path.write_text(json.dumps(document), encoding="utf-8")
        reject(f"database_structure_{index}", lambda: load_tables(path), code="invalid_database")
    for content in (b"{broken", b"\xff"):
        path.write_bytes(content)
        reject("database_content_" + repr(content), lambda: load_tables(path), code="invalid_database")
    path.unlink()
    reject("database_missing", lambda: load_tables(path), code="invalid_database")

record = dict(conditions=cases, checks=checks, failed=sum(not c["passed"] for c in checks))
(ROOT / "evidence/Maintenance_Checks.json").write_text(
    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"{len(cases)} air/report conditions; {len(checks)} maintenance checks passed")
