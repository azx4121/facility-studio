"""V5.5 independent invariants, reversals, persistence and input boundaries."""

import sys, math, json, copy, tempfile, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio import quick_tools as q
from facility_studio.engine import calculate
from facility_studio.schema import default_project, FIELDS
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.ahu_engine import nm_calculate
from facility_studio.design_workflow import (
    ahu_requirement_updates,
    ahu_utility_preview,
    compare_results,
)
from facility_studio.project_store import save_project_file, validate_provenance
from facility_studio.database import load_tables
from facility_studio.errors import ValidationError
from facility_studio.reports import report, nm_report
from facility_studio.html_report import summary_html

checks = []
cases = []


def check(name, actual, expected, tol=1e-7):
    ok = (
        abs(actual - expected) <= tol * max(1, abs(expected))
        if isinstance(actual, (int, float))
        else actual == expected
    )
    checks.append(dict(name=name, actual=actual, expected=expected, passed=ok))
    assert ok, checks[-1]


def reject(name, fn):
    try:
        fn()
    except (ValueError, TypeError):
        check(name, True, True)
    else:
        raise AssertionError(name + " should reject")


# Five winter weather / load designs, independently reconstruct room conservation.
for idx, (temp, gain, moisture) in enumerate(
    [(8, 100, 100), (0, 0, 0), (-5, 25, 30), (15, 150, 80), (5, 80, 120)]
):
    p = default_project()
    p["inputs"].update(
        ow_t=str(temp), winter_gain_ratio=str(gain), winter_moisture_ratio=str(moisture)
    )
    r = calculate(p)
    w = r["winter"]
    wr = r["winter_room"]
    m = w["mass"]
    room = r["room"]
    sa = w["supply"]
    check(
        f"winter{idx}_heat",
        m * (1.006 + 1.86 * sa["w"]) * (room["t"] - sa["t"]) + wr["dcc_kw"],
        wr["sensible_kw"],
    )
    check(f"winter{idx}_water", m * (room["w"] - sa["w"]), wr["moisture_kg_s"])
    check(f"winter{idx}_DCC_design", r["dcc_design_kw"], max(wr["dcc_kw"], r["dcc_kw"]))
    check(f"winter{idx}_report_scope", "冬季室內熱濕平衡" in report(r), True)
    cases.append(dict(id="W" + str(idx), condition=p["inputs"], winter=wr))
    (ROOT / "evidence" / f"V55_Winter_{idx}.txt").write_text(
        report(r), encoding="utf-8"
    )
# Five climates, each inverted through wet bulb, dew point, and h/w.
for idx, (t, rh, pres) in enumerate(
    [(35, 70, 101.325), (22, 50, 101.325), (5, 80, 95), (-5, 60, 101.325), (40, 25, 85)]
):
    a = q.psychrometric("乾球＋RH", t, rh, pres)
    for mode, first, second in [
        ("乾球＋濕球", t, a["wetbulb_c"]),
        ("乾球＋露點", t, a["dewpoint_c"]),
        ("焓＋含濕比", a["h"], a["w"] * 1000),
    ]:
        b = q.psychrometric(mode, first, second, pres)
        check(f"psy{idx}_{mode}_T", b["t"], t, 1e-5)
        check(f"psy{idx}_{mode}_RH", b["rh"], rh, 1e-5)
    cases.append(dict(id="P" + str(idx), t=t, rh=rh, pressure=pres, state=a))
for idx, (flow, dt, rho, cp) in enumerate(
    [
        (400, 5, 1000, 4.1868),
        (100, 10, 998, 4.18),
        (0, 5, 1000, 4.1868),
        (320, 3, 1040, 3.7),
    ]
):
    x = q.water_heat("熱量 kW", flow, dt, rho, cp)
    check("water" + str(idx), x["kw"], flow / 60000 * rho * cp * dt)
    check(
        "water_reverse" + str(idx),
        q.water_heat("流量 LPM", x["kw"], dt, rho, cp)["lpm"],
        flow,
    )
    cases.append(dict(id="Q" + str(idx), result=x))
for idx, flow in enumerate([1, 10, 100]):
    x = q.valve("Kv", flow, 0.2, 1.1)
    check(
        "valve_reverse" + str(idx),
        q.valve("流量 m³/h", x["kv"], 0.2, 1.1)["flow_m3h"],
        flow,
    )
    check(
        "valve_dp" + str(idx), q.valve("壓差 bar", flow, x["kv"], 1.1)["drop_bar"], 0.2
    )
    cases.append(dict(id="K" + str(idx), result=x))
x = q.mix_air(35, 70, 1000, 22, 50, 4000)
a = q.psychrometric("乾球＋RH", 35, 70)
b = q.psychrometric("乾球＋RH", 22, 50)
m1 = 1000 / 3600 / a["v_da"]
m2 = 4000 / 3600 / b["v_da"]
check("mix_enthalpy", x["state"]["h"] * (m1 + m2), m1 * a["h"] + m2 * b["h"])
check("mix_moisture", x["state"]["w"] * (m1 + m2), m1 * a["w"] + m2 * b["w"])
cases.append(dict(id="M1", result=x))
x = q.air_process(35, 70, 15, 95, 5000)
check(
    "air_net",
    x["net_air_kw"],
    5000 / 3600 / x["inlet"]["v_da"] * (x["outlet"]["h"] - x["inlet"]["h"]),
)
cases.append(dict(id="A1", result=x))
x = q.energy_cost(100, 12, 30, 0.8, 4)
check("energy", x["kwh"], 28800)
check("cost", x["cost"], 115200)
cases.append(dict(id="E1", result=x))
check("gpm_US", q.convert_all("水量", 1, "US GPM")["LPM"], 3.785411784)
check("gpm_UK", q.convert_all("水量", 1, "UK GPM")["LPM"], 4.54609)
check("Torr", q.convert_all("壓力", 760, "Torr")["Pa"], 101325)
check("absolutezero", q.convert_all("溫度", 0, "K")["°C"], -273.15)
for name, fn in [
    ("absolute_below", lambda: q.convert_all("溫度", -1, "K")),
    ("wetbulb_above", lambda: q.psychrometric("乾球＋濕球", 20, 22)),
    ("dewpoint_above", lambda: q.psychrometric("乾球＋露點", 20, 22)),
    ("RH101", lambda: q.psychrometric("乾球＋RH", 20, 101)),
    ("NaN", lambda: q.convert_all("風量", "nan", "CMH")),
    ("water_zero_dt", lambda: q.water_heat("流量 LPM", 100, 0)),
    ("valve_zero_Kv", lambda: q.valve("壓差 bar", 10, 0)),
    ("mix_zero", lambda: q.mix_air(20, 50, 0, 25, 50, 0)),
]:
    reject(name, fn)
# Links use each season's actual supply volume; electric preview is idempotent.
p = default_project()
p["inputs"]["sys_type"] = FIELDS["sys_type"]["options"][0]
r = calculate(p)
i = copy.deepcopy(NM_DEFAULTS)
i.update(ahu_requirement_updates(r))
ahu = nm_calculate(i)
for season in ["summer", "winter"]:
    check("linked_mass_" + season, ahu[season]["mass"], r[season]["mass"])
check("seasonal_report", "分季送風目標" in nm_report(ahu), True)
preview = ahu_utility_preview(ahu)
check("utility_idempotent", preview, ahu_utility_preview(ahu))
check(
    "fan_rating",
    float(preview["updates"]["e_np_fan"]),
    float(i["fan_qty"]) * float(i["fan_unit_kw"]),
)
check("AB_zero", all(x["delta"] == 0 for x in compare_results(r, r)["metrics"]), True)
check(
    "HTML_escape",
    "&lt;script&gt;"
    in summary_html(
        dict(
            r,
            project=dict(
                r["project"],
                inputs=dict(r["project"]["inputs"], project_name="<script>"),
            ),
        )
    ),
    True,
)
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "p.json"
    save_project_file(path, {"version": 1})
    save_project_file(path, {"version": 2})
    check(
        "save_backup",
        json.loads(path.with_suffix(".json.bak").read_text(encoding="utf-8")),
        {"version": 1},
    )
    db = json.loads(
        (ROOT / "facility_studio/resources/engineering_tables.json").read_text(
            encoding="utf-8"
        )
    )
    db["tables"]["WIRE_DB"].reverse()
    bad = Path(td) / "bad.json"
    bad.write_text(json.dumps(db), encoding="utf-8")
    reject("table_order", lambda: load_tables(bad))
pr = default_project()["provenance"]
pr["oa_t"] = {"source": "原廠資料", "note": ""}
reject("OEM_needs_document", lambda: validate_provenance(pr, pr.keys()))
e = ValidationError("改寫提示內容，不含括號", field_name="oa_t")
check("structured_error", e.field_name, "oa_t")
proc = subprocess.run(
    [
        sys.executable,
        "-c",
        "import sys;sys.path.insert(0,"
        + repr(str(ROOT))
        + ");import facility_studio.engine;assert 'tkinter' not in sys.modules;print('OK')",
    ],
    capture_output=True,
    text=True,
)
check("headless_engine", proc.returncode, 0)
(ROOT / "evidence/V55_Feature_Checks.json").write_text(
    json.dumps(dict(cases=cases, checks=checks), ensure_ascii=False, indent=2),
    encoding="utf-8",
)
(ROOT / "Default_Project.json").write_text(
    json.dumps(default_project(), ensure_ascii=False, indent=2), encoding="utf-8"
)
(ROOT / "evidence/Design_Summary.html").write_text(summary_html(r), encoding="utf-8")
print(f"{len(cases)} new numerical conditions / {len(checks)} feature checks passed")
