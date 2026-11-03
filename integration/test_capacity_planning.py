"""Deterministic synthetic capacity checks; not real-project engineering validation."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

PLATFORM = os.environ.get("FACILITY_TEST_PLATFORM", "windows")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / PLATFORM))
from facility_studio import capacity_planning as m
from facility_studio.contributions import empty_ledger
from facility_studio.design_workflow import capacity_plan_from_ledger, capacity_source_binding
from facility_studio.errors import ValidationError


def row(kind, ident, system="ELECTRIC", value=100):
    r = m.new_row(kind, ident, system)
    r.update(boundary="SYNTHETIC-SERVICE", source=dict(reference="SYNTHETIC-HAND-CHECK", revision="R1", fingerprint=""))
    r["conditions"] = {
        "ELECTRIC": dict(voltage_v=380, phases=3, frequency_hz=60),
        "CHW": dict(fluid="water", supply_c=7, return_c=12, rho_kg_m3=1000, cp_kj_kgk=4.1868),
        "PCW": dict(fluid="water", supply_c=25, return_c=30, rho_kg_m3=1000, cp_kj_kgk=4.1868),
        "EXHAUST": dict(exhaust_type="GEX", temperature_c=25, absolute_kpa=101.325, required_static_pa=500),
    }[system]
    r["values"] = dict(summer=value, winter=value)
    if kind == "capacity":
        r["derating"] = 1.0
    else:
        r["demand_complete"] = True
    return r


def plan(system="ELECTRIC"):
    p = m.new_plan("Synthetic independently hand-calculated example")
    p.update(scope="Only the explicitly listed synthetic service", scope_confirmed=True, synthetic=True,
             demands=[row("demand", "current", system)], capacities=[row("capacity", "supply", system, 100)])
    p["capacities"][0]["quantity"] = 3
    return p


def group(p, **kwargs):
    return m.evaluate_plan(p, **kwargs)["alternatives"][0]["groups"][0]


def test_electric_current_expansion_single_margin_and_n1():
    p = plan()
    b = row("demand", "new", value=60)
    b["phase"] = "expansion"
    p["demands"].append(b)
    p.update(additional_margin_pct=10, margin_reason="Synthetic owner-selected 10%, not a code default")
    p["capacities"][0]["derating"] = .9
    x = group(p)["cases"][0]
    # Independent arithmetic, not calls to product calculation helpers.
    assert x["design_demand"] == pytest.approx(176)
    assert x["normal_capacity"] == 270
    assert x["n_minus_one_capacity"] == 180
    assert x["normal_headroom"] == pytest.approx(94)
    assert x["n_minus_one_headroom"] == pytest.approx(4)
    assert x["normal_deficit"] == x["n_minus_one_deficit"] == 0


def test_coincident_seasons_sum_before_peak():
    p = plan("CHW")
    p["demands"][0]["values"] = dict(summer=100, winter=50)
    b = row("demand", "new", "CHW")
    b.update(phase="expansion", values=dict(summer=60, winter=100))
    p["demands"].append(b)
    g = group(p)
    assert [x["design_demand"] for x in g["cases"]] == [160, 150]
    assert g["peak_design_demand"] == 160  # not max(100,50)+max(60,100)=200


def test_pcw_flow_and_heat_are_same_load_not_added():
    p = plan("PCW")
    p["demands"][0].update(quantity=4, coincidence=.75, values=dict(summer=80, winter=80))
    x = group(p)["cases"][0]
    assert x["design_demand"] == 240
    assert x["equivalent_thermal_kw"] == pytest.approx(83.736, abs=1e-10)
    assert x["normal_headroom"] == 60  # 300-240, not 300-240-83.736
    assert x["n_minus_one_deficit"] == 40


def test_remove_largest_single_unit_not_largest_bank():
    p = plan()
    p["capacities"][0].update(quantity=100, values=dict(summer=10, winter=10))
    p["capacities"].append(row("capacity", "large", value=100))
    x = group(p)["cases"][0]
    assert x["normal_capacity"] == 1100
    assert x["n_minus_one_capacity"] == 1000
    p["capacities"] = [row("capacity", "only", value=100)]
    assert group(p)["cases"][0]["n_minus_one_capacity"] == 0


@pytest.mark.parametrize("system", list(m.UNITS))
@pytest.mark.parametrize("missing", ["demand", "capacity", "factor", "condition", "source", "margin", "scope"])
def test_unknowns_never_pass_or_become_zero(system, missing):
    p = plan(system)
    if missing == "demand":
        p["demands"][0]["values"]["winter"] = None
    elif missing == "capacity":
        p["capacities"][0]["values"]["winter"] = None
    elif missing == "factor":
        p["demands"][0]["coincidence"] = None
    elif missing == "condition":
        key = m.CONDITIONS[system][0]
        for r in p["demands"] + p["capacities"]:
            r["conditions"][key] = None
    elif missing == "source":
        p["demands"][0]["source"]["revision"] = ""
    elif missing == "margin":
        p["demands"][0]["included_margin_pct"] = None
    else:
        p["scope_confirmed"] = False
    g = group(p)
    assert g["normal_status"] == g["n_minus_one_status"] == "待資料／待覆核"
    if missing in ("demand", "factor"):
        assert g["cases"][1]["design_demand"] is None
        assert g["peak_design_demand"] is None
    if missing == "capacity":
        assert g["cases"][1]["normal_capacity"] is None
        assert g["cases"][1]["n_minus_one_capacity"] is None


@pytest.mark.parametrize("system", list(m.UNITS))
def test_wrong_boundary_and_conditions_cannot_offset_deficit(system):
    p = plan(system)
    for field in ("boundary", "conditions"):
        q = copy.deepcopy(p)
        if field == "boundary":
            q["capacities"][0][field] = "OTHER-SERVICE"
        else:
            key = next(k for k, v in q["capacities"][0][field].items() if isinstance(v, (float, int)))
            q["capacities"][0][field][key] += 1
        groups = m.evaluate_plan(q)["alternatives"][0]["groups"]
        assert len(groups) == 2
        assert all(g["normal_status"] == "待資料／待覆核" for g in groups)
        assert groups[0]["cases"][0]["normal_capacity"] is None


def test_number_spelling_not_mistaken_as_different_conditions():
    p = plan()
    p["capacities"][0]["conditions"]["voltage_v"] = 380.0
    assert len(m.evaluate_plan(p)["alternatives"][0]["groups"]) == 1


def test_upsert_and_asset_duplicate_guards_and_alternatives():
    p = plan()
    p = m.upsert_row(p, "demand", row("demand", "current", value=60))
    assert len(p["demands"]) == 1 and group(p)["cases"][0]["design_demand"] == 60
    other = copy.deepcopy(p["demands"][0])
    other["id"], other["phase"] = "option-B", "expansion"
    p["demands"].append(other)
    with pytest.raises(ValidationError, match="實體來源"):
        m.evaluate_plan(p)
    p["alternatives"] = [dict(id=ident, name=ident, demand_ids=[demand], capacity_ids=["supply"]) for ident, demand in (("A", "current"), ("B", "option-B"))]
    assert len(m.evaluate_plan(p)["alternatives"]) == 2
    p["alternatives"][0]["demand_ids"].append("current")
    with pytest.raises(ValidationError):
        m.evaluate_plan(p)


def test_stale_sources_and_export_recompute():
    p = plan()
    binding = dict(project_id="SYNTHETIC", fingerprint="revision1")
    p["binding"] = binding
    assert group(p, current_binding=binding)["normal_status"] == "初篩容量足夠"
    assert m.evaluate_plan(p)["stale"]
    assert m.evaluate_plan(p, dict(binding, fingerprint="revision2"))["stale"]
    r = m.evaluate_plan(p, binding)
    r["alternatives"][0]["groups"][0]["cases"][0]["normal_capacity"] = 999999
    assert "999999" not in m.capacity_report(r)
    r["plan"]["demands"][0]["values"]["summer"] = 200
    with pytest.raises(ValidationError, match="重新計算"):
        m.capacity_report(r)


def ledger_workspace(ident="s1", name="Synthetic source"):
    e = dict(id=ident, name=name, kind="設備表", source_hash="source-revision1", updates={"gex_q": "250", "u_gex": "CMH"}, water=[],
             power={"UP": dict(kw=100, kvar=10, design_kw=125, design_kvar=12.5, branch_floor_a=0, length_m=0, voltage=380)}, notes=[], pending=[])
    ledger = empty_ledger()
    ledger["entries"][ident] = e
    ledger["baseline"]["e_up_eq"] = 40
    return dict(project_id="synthetic", main=dict(inputs=dict(project_name="Synthetic", e_up_eq="140")), ahus=[], demand_ledger=ledger)


def test_ledger_adapter_excludes_adopted_totals_and_retains_unknowns():
    w = ledger_workspace()
    p = capacity_plan_from_ledger(w)
    assert len(p["demands"]) == 2
    assert p["demands"][0]["values"]["summer"] == 100  # not 100+140, and not design125
    assert p["demands"][1]["values"]["summer"] == 250
    assert p["demands"][0]["conditions"]["frequency_hz"] is None
    assert p["demands"][1]["conditions"]["required_static_pa"] is None
    assert not p["scope_confirmed"] and not p["capacities"]
    binding = capacity_source_binding(w)
    assert p["binding"] == binding
    w["main"]["inputs"]["e_up_eq"] = "141"
    assert m.evaluate_plan(p, capacity_source_binding(w))["stale"]


def test_ledger_maximum_id_and_name_and_invalid_flow():
    w = ledger_workspace("x" * 100, "y" * 1000)
    p = capacity_plan_from_ledger(w)
    assert len(p["demands"]) == 2
    assert all(len(r["id"]) <= 100 and len(r["source"]["reference"]) <= 1000 for r in p["demands"])
    w["demand_ledger"]["entries"]["x" * 100]["updates"]["gex_q"] = "unknown"
    with pytest.raises(ValidationError):
        capacity_plan_from_ledger(w)


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf"), "100", {}, []])
def test_bad_numbers_rejected(value):
    p = plan()
    p["demands"][0]["values"]["summer"] = value
    with pytest.raises(ValidationError):
        m.evaluate_plan(p)


def test_empty_lists_and_known_zero():
    assert m.evaluate_plan(m.new_plan())["alternatives"][0]["issues"]
    p = plan()
    p["demands"][0]["values"] = dict(summer=0, winter=0)
    assert group(p)["cases"][0]["design_demand"] == 0
    p["capacities"] = []
    assert group(p)["cases"][0]["normal_capacity"] is None


def test_roundtrip_and_cli_exit_codes(tmp_path):
    p = plan()
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(p), encoding="utf-8")
    assert m.read_plan(path) == p
    repo = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(repo / PLATFORM))
    command = [sys.executable, "-c", "from facility_studio.cli import main; raise SystemExit(main())", "--capacity-plan", str(path)]
    completed = subprocess.run(command, env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "合成驗證案例" in completed.stdout
    p["demands"][0]["values"]["winter"] = None
    path.write_text(json.dumps(p), encoding="utf-8")
    assert subprocess.run(command, env=env, capture_output=True).returncode == 3
    path.write_text('{"kind": "x"}', encoding="utf-8")
    assert subprocess.run(command, env=env, capture_output=True).returncode == 2


def test_duplicate_json_fields_refused(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"kind":"x", "kind":"y"}', encoding="utf-8")
    with pytest.raises(ValidationError, match="重複"):
        m.read_plan(path)


@pytest.mark.parametrize("boundary", [" ", "   ", "\u3000"])
def test_whitespace_boundary_is_unknown_not_adequate(boundary):
    p = plan()
    for r in p["demands"] + p["capacities"]:
        r["boundary"] = boundary
    g = group(p)
    assert g["normal_status"] == g["n_minus_one_status"] == "待資料／待覆核"
    assert g["issues"]


def test_oversized_integer_is_validation_error_and_cli_format_exit(tmp_path):
    p = plan()
    p["demands"][0]["values"]["summer"] = 10 ** 1000
    with pytest.raises(ValidationError):
        m.evaluate_plan(p)
    path = tmp_path / "oversized.json"
    path.write_text(json.dumps(p), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / PLATFORM))
    result = subprocess.run([sys.executable, "-c", "from facility_studio.cli import main; raise SystemExit(main())", "--capacity-plan", str(path)], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_new_and_captured_demands_require_separate_completeness_confirmation():
    assert m.new_row("demand", "new")["demand_complete"] is False
    workspace = ledger_workspace()
    workspace["demand_ledger"]["entries"]["s1"]["pending"] = ["An unmeasured pump is missing from the subtotal"]
    p = capacity_plan_from_ledger(workspace)
    p.update(scope_confirmed=True)
    # Capture must retain the known numbers, without treating them as full loads.
    d = p["demands"][0]
    assert d["values"]["summer"] == 100 and d["demand_complete"] is False
    p["demands"] = [d]
    d["conditions"]["frequency_hz"] = 60
    cap = row("capacity", "supply", value=100)
    cap.update(boundary=d["boundary"], quantity=3)
    p["capacities"] = [cap]
    g = group(p, current_binding=p["binding"])
    x = g["cases"][0]
    assert x["known_subtotal"] == 100
    for key in ("current", "combined", "design_demand", "normal_headroom", "n_minus_one_headroom", "normal_deficit", "n_minus_one_deficit"):
        assert x[key] is None, key
    # Deleting warning text or updating a reference is not completeness evidence.
    d["pending"] = []
    d["source"]["revision"] = "reviewed reference"
    assert group(p, current_binding=p["binding"])["cases"][0]["design_demand"] is None
    d["demand_complete"] = True
    assert group(p, current_binding=p["binding"])["cases"][0]["design_demand"] == 100


def test_incomplete_expansion_preserves_known_subtotal_without_false_deficit():
    p = plan("PCW")
    d = row("demand", "new", "PCW", value=60)
    d.update(phase="expansion", demand_complete=False)
    p["demands"].append(d)
    x = group(p)["cases"][0]
    assert x["current"] == 100 and x["expansion"] is None
    assert x["known_subtotal"] == 160
    assert x["design_demand"] is None and x["equivalent_thermal_kw"] is None
    assert x["normal_capacity"] == 300 and x["n_minus_one_capacity"] == 200
    assert x["normal_deficit"] is None and x["n_minus_one_deficit"] is None


def test_legacy_v1_migrates_to_unconfirmed_subtotals_without_mutating_input():
    old = plan()
    old["version"] = 1
    for r in old["demands"]:
        del r["demand_complete"]
    before = copy.deepcopy(old)
    migrated = m.validate_plan(old)
    assert old == before and migrated["version"] == 2
    assert migrated["demands"][0]["demand_complete"] is False
    assert migrated["demands"][0]["values"] == old["demands"][0]["values"]
    assert any("舊版計畫" in note for note in migrated["demands"][0]["pending"])
    assert m.validate_plan(migrated) == migrated
    assert group(old)["cases"][0]["design_demand"] is None


@pytest.mark.parametrize("value", [None, 0, 1, "true"])
def test_completeness_flag_must_be_explicit_boolean(value):
    p = plan()
    p["demands"][0]["demand_complete"] = value
    with pytest.raises(ValidationError):
        m.evaluate_plan(p)


def test_report_preserves_user_owned_pending_identifiers_and_binding_in_english():
    p = plan()
    p["demands"][0]["id"] = "電力配線來源"
    p["demands"][0]["pending"] = ["已儲存：電力配線文件待補資料"]
    p["demands"][0]["source"]["revision"] = ""
    p["binding"] = dict(project_id="電力配線主案", fingerprint="fixture")
    report = str(m.capacity_report(m.evaluate_plan(p, current_binding=p["binding"]), language="en"))
    assert "已儲存：電力配線文件待補資料" in report
    assert "電力配線來源 source document / revision is required" in report
    assert "電力配線主案" in report


def test_legacy_migration_preserves_maximum_pending_records():
    old = plan()
    old["version"] = 1
    d = old["demands"][0]
    del d["demand_complete"]
    d["pending"] = [f"Original pending record {i}" for i in range(100)]
    migrated = m.validate_plan(old)
    assert migrated["demands"][0]["pending"] == d["pending"]
    assert migrated["demands"][0]["demand_complete"] is False
    assert any("需求完整性尚未確認" in issue for issue in group(migrated)["issues"])


def test_seeded_complete_scenarios_match_explicit_single_unit_loss_enumeration():
    import random
    rng = random.Random(2701)
    for _ in range(500):
        p = plan()
        p.update(demands=[], capacities=[], additional_margin_pct=rng.randint(0, 20), margin_reason="Synthetic arithmetic fixture")
        demand = {case: 0 for case in p["cases"]}
        units = {case: [] for case in p["cases"]}
        for index in range(rng.randint(1, 8)):
            d = row("demand", f"D{index}")
            d.update(quantity=rng.randint(1, 8), phase=rng.choice(("current", "expansion")), coincidence=rng.choice((0, .25, .5, .75, 1)))
            for case in p["cases"]:
                d["values"][case] = rng.randint(0, 1000)
                demand[case] += d["values"][case] * d["quantity"] * d["coincidence"]
            p["demands"].append(d)
        for index in range(rng.randint(1, 8)):
            c = row("capacity", f"C{index}")
            c.update(quantity=rng.randint(1, 8), derating=rng.choice((0, .25, .5, .75, 1)))
            for case in p["cases"]:
                c["values"][case] = rng.randint(0, 1000)
                units[case].extend([c["values"][case] * c["derating"]] * c["quantity"])
            p["capacities"].append(c)
        for x in group(p)["cases"]:
            case = x["case"]
            after_loss = [sum(value for i, value in enumerate(units[case]) if i != failed) for failed in range(len(units[case]))]
            assert x["design_demand"] == pytest.approx(demand[case] * (1 + p["additional_margin_pct"] / 100), abs=1e-8)
            assert x["normal_capacity"] == sum(units[case])
            assert x["n_minus_one_capacity"] == min(after_loss)


def test_actual_ahu_unknown_pump_never_becomes_full_demand_surplus():
    from facility_studio.ahu_schema import NM_DEFAULTS
    from facility_studio.ahu_engine import nm_calculate
    from facility_studio.schema import default_project
    from facility_studio.contributions import ahu_contribution
    inputs = dict(NM_DEFAULTS, name="Synthetic missing pump fixture", humidifier="循環水洗濕膜", pump_input_kw="", fan_qty="2", fan_unit_kw="5.5")
    main = default_project()
    entry = ahu_contribution(nm_calculate(inputs), "ahu-1", main["inputs"])
    ledger = empty_ledger()
    ledger["entries"]["ahu-1"] = entry
    workspace = dict(project_id="synthetic", main=main, ahus=[dict(id="ahu-1", inputs=inputs)], demand_ledger=ledger)
    p = capacity_plan_from_ledger(workspace)
    d = next(d for d in p["demands"] if d["system"] == "ELECTRIC")
    d["conditions"]["frequency_hz"] = 60
    c = row("capacity", "supply")
    c.update(boundary="NP", quantity=3, conditions=d["conditions"].copy())
    p.update(capacities=[c], scope_confirmed=True)
    groups = m.evaluate_plan(p, capacity_source_binding(workspace))["alternatives"][0]["groups"]
    g = next(g for g in groups if g["system"] == "ELECTRIC")
    assert entry["power"]["NP"]["kw"] == g["cases"][0]["known_subtotal"] == 11
    assert any("額定耗電未知" in text for text in entry["pending"])
    assert g["cases"][0]["design_demand"] is None
    assert g["cases"][0]["normal_headroom"] is None
    assert g["cases"][0]["n_minus_one_headroom"] is None
    assert g["cases"][0]["normal_deficit"] is None
    assert g["cases"][0]["n_minus_one_deficit"] is None
