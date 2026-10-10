"""Deterministic regressions for inactive inputs and independently checked sums.

Compare all derived outputs and the actual reports, not just HVAC flow. Saved
drafts and their document hashes are intentionally excluded: they must survive.
The read-only linked-main identifier is source metadata, not a design value.
"""

import copy
import itertools
import math
import random
import re

from .ahu_engine import nm_calculate
from .ahu_schema import NM_DEFAULTS, NM_FIELDS
from .engine import calculate, pressure_result
from .errors import InputError
from .field_state import ahu_inactive, main_inactive
from .reports import nm_report, report
from .schema import FIELDS, PD_DEFAULTS, default_project
from .utils import G, TEMP_FACTORS, DERATE_PIPES


def payload(result):
    metadata = {"project", "raw_inputs", "inputs", "effective_inputs", "hash"}
    return {key: value for key, value in result.items() if key not in metadata}


def assert_equal(actual, expected, path="result"):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), path + " keys"
        for key in expected:
            assert_equal(actual[key], expected[key], path + "." + str(key))
    elif isinstance(expected, (tuple, list)):
        assert len(actual) == len(expected), path + " length"
        for index, value in enumerate(expected):
            assert_equal(actual[index], value, path + "[" + str(index) + "]")
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9), path
    else:
        assert actual == expected, path


def mutation(spec, rng, mode):
    if mode in ("", "bad", "NaN", "-987654"):
        return mode
    options = spec.get("options")
    low, high = spec.get("low"), spec.get("high")
    if "limit" in spec:
        limit = spec["limit"]
        if isinstance(limit, list):
            options = limit
        elif isinstance(limit, tuple):
            low, high = limit
        else:
            return "retained draft"
    if options:
        return options[-1] if mode == "upper" else rng.choice(options)
    if spec.get("text"):
        return "retained draft"
    if low is None or high is None:
        return "987654"
    return format(high if mode == "upper" else rng.uniform(low, high), ".12g")


def run_checks(random_repeats=4):
    """Return evidence; any missed invariant raises and prevents publication."""
    evidence = []
    rng = random.Random(55720261009)

    def record(name, action):
        action()
        evidence.append({"name": name, "passed": True})

    main_scenarios = 0
    for system, kind, hp in itertools.product(
        FIELDS["sys_type"]["options"],
        FIELDS["e_up_type"]["options"],
        (False, True),
    ):
        p = default_project()
        i = p["inputs"]
        i.update(sys_type=system, e_up_type=kind, e_np_type=kind)
        if hp:
            i.update(e_up_eq="100", u_e_up_eq="HP", e_up_oven="0",
                     e_np_fan="20", u_e_np_fan="HP")
        baseline = calculate(p)
        expected = payload(baseline)
        baseline_text = str(report(baseline))
        off = main_inactive(i)
        modes = ["", "bad", "NaN", "-987654", "upper"] + ["random"] * random_repeats
        for index, mode in enumerate(modes):
            candidate = copy.deepcopy(p)
            for key in off:
                candidate["inputs"][key] = mutation(FIELDS[key], rng, mode)

            def compare_main():
                result = calculate(candidate)
                assert_equal(payload(result), expected)
                assert str(report(result)) == baseline_text, "main report changed"
                assert result["project"]["inputs"] == candidate["inputs"], "draft lost"

            record("main/%d/mutation-%d" % (main_scenarios, index), compare_main)
        main_scenarios += 1

    ahu_scenarios = 0
    for humidifier, recovery, source in itertools.product(
        NM_FIELDS["humidifier"]["limit"],
        NM_FIELDS["recovery"]["limit"],
        NM_FIELDS["h1_source"]["limit"],
    ):
        i = dict(NM_DEFAULTS, humidifier=humidifier, recovery=recovery,
                 h1_source=source, h2_source=source)
        if recovery.startswith("二期"):
            i.update(h1_hw_kw="200", h2_hw_kw="140")
        baseline = nm_calculate(i)
        expected = payload(baseline)
        baseline_text = str(nm_report(baseline))
        off = ahu_inactive(i)
        modes = ["", "bad", "NaN", "-987654", "upper"] + ["random"] * random_repeats
        for index, mode in enumerate(modes):
            candidate = dict(i)
            for key in off:
                if key != "linked_main_hash":
                    candidate[key] = mutation(NM_FIELDS[key], rng, mode)

            def compare_ahu():
                result = nm_calculate(candidate)
                assert_equal(payload(result), expected)
                assert str(nm_report(result)) == baseline_text, "AHU report changed"
                assert result["raw_inputs"] == candidate, "AHU draft lost"

            record("ahu/%d/mutation-%d" % (ahu_scenarios, index), compare_ahu)
        ahu_scenarios += 1

    # Independent electrical arithmetic, activation and error-field contracts.
    for panel in ("up", "np"):
        load = "eq" if panel == "up" else "fan"
        for kind, largest in itertools.product(FIELDS["e_up_type"]["options"], (0, 30, 60)):
            p = default_project()
            for key in (("eq", "oven") if panel == "up" else ("fan", "heat", "humid", "exh", "pump")):
                p["inputs"][f"e_{panel}_{key}"] = "0"
            p["inputs"].update({f"e_{panel}_{load}": "100", f"u_e_{panel}_{load}": "HP",
                                f"e_{panel}_type": kind, f"e_{panel}_largest_hp": str(largest)})
            result = calculate(p)
            electric = result["electric"][panel.upper()]
            operating = (100 * 0.745699871582 / 0.9) * 1000 / (math.sqrt(3) * 380 * 0.85)
            expected = operating * 1.25 if kind == "連續負載" or largest == 0 else operating * (1 + 0.25 * largest / 100)

            def check_electric():
                assert math.isclose(electric["design_current_a"], expected, rel_tol=1e-10)
                disabled = f"e_{panel}_largest_hp" in main_inactive(p["inputs"])
                assert disabled == (kind == "連續負載")
                candidate = electric["selected"]
                assert expected <= candidate["nfb_candidate_a"] <= candidate["iz_a"]

            record("motor/%s/%s/%d" % (panel, kind, largest), check_electric)
        bad = default_project()
        bad["inputs"].update({f"e_{panel}_{load}": "100", f"u_e_{panel}_{load}": "HP",
                              f"e_{panel}_type": "一般負載", f"e_{panel}_largest_hp": "101"})

        def error_field():
            try:
                calculate(bad)
            except InputError as error:
                assert error.field_name == f"e_{panel}_largest_hp"
            else:
                raise AssertionError("invalid active largest motor accepted")

        record("motor/%s/error-location" % panel, error_field)

    pressure_scenarios = 0
    for simple, known, opened, fitting, manual, water, unit in itertools.product(
        (False, True), (False, True), (False, True), (False, True),
        (False, True), (False, True), ("Pa", "kPa", "mmAq", "mH2O"),
    ):
        config = dict(PD_DEFAULTS, estimate_mode="簡易估算" if simple else "詳細計算",
                      equipment_known="已知設備壓差" if known else "尚無資料（不含設備）",
                      boundary="開式系統" if opened else "閉式循環", static_m="7.5",
                      fitting_mode="直接 K 值" if fitting else "等效長 L/D",
                      mode="手動阻力率" if manual else "Darcy 自動", unit=unit, equipment_drop="2")
        result = pressure_result(config, 0.002, 0.05, math.pi * 0.05**2 / 4, 1, 1000 if water else 1.2, .001 if water else .000018, .045, water)

        def pressure_balance():
            expected_static = 1000 * G * 7.5 if water and opened else 0
            assert math.isclose(result["static_pa"], expected_static, abs_tol=1e-8)
            assert math.isclose(result["total_pa"], sum(result[key] for key in ("friction_pa", "local_pa", "equipment_pa", "static_pa")), rel_tol=1e-10)
            assert result["equipment_included"] == known
            assert bool(result["static_note"])

        record("pressure/%d" % pressure_scenarios, pressure_balance)
        pressure_scenarios += 1

    # Current range-only adapter must preserve the physically adopted factors.
    for temp, pipe in itertools.product(FIELDS["e_temp"]["options"], FIELDS["e_pipe"]["options"]):
        p = default_project()
        p["inputs"].update(e_temp=temp, e_pipe=pipe)
        electric = calculate(p)["electric"]["UP"]
        ambient = 35 if temp.startswith("35") else int(re.findall(r"\d+", temp)[-1])
        factor = next(value for upper, value in TEMP_FACTORS[90] if ambient <= upper)

        def adopted_derating():
            assert electric["ambient_c"] == ambient
            assert electric["dt"] == factor
            assert electric["dp"] == DERATE_PIPES[pipe]

        record("derating/%s/%s" % (temp, pipe), adopted_derating)

    def eta_reactivation():
        for tag in ("h1", "h2"):
            i = dict(NM_DEFAULTS, **{tag + "_source": "回收熱水", tag + "_eta": "0.05"})
            nm_calculate(i)
            i[tag + "_source"] = "電熱"
            try:
                nm_calculate(i)
            except InputError as error:
                assert error.field_name == tag + "_eta"
            else:
                raise AssertionError("reactivated invalid efficiency accepted")

    record("eta/reactivation", eta_reactivation)

    for target_mode, override in itertools.product(("共用送風目標", "主案分季需求"), (False, True)):
        # Use schema spelling for the independent target mode.
        target_mode = NM_DEFAULTS["target_mode"] if target_mode != "主案分季需求" else target_mode
        i = dict(NM_DEFAULTS, target_mode=target_mode, h1_source="熱水＋電熱",
                 h2_source="熱水＋電熱", recovery="二期可用（依已填能力）",
                 h1_water_mode="本段獨立設定", h2_water_mode="本段獨立設定",
                 h1_eta="0.9", h2_eta="0.8", summer_c1_mode="指定出口乾球",
                 summer_c1_t="22", winter_c1_mode="旁通")
        if not override:
            i.update(h1_eta="0e0", h2_eta="0.0", heat_eta="0.95")
        baseline = nm_calculate(i)
        candidate = dict(i)
        for key in ahu_inactive(i):
            if key != "linked_main_hash":
                candidate[key] = mutation(NM_FIELDS[key], rng, "upper")

        def advanced_ahu():
            result = nm_calculate(candidate)
            assert_equal(payload(result), payload(baseline))
            assert nm_report(result) == nm_report(baseline)
            eta = 0.9 if override else 0.95
            assert result["winter"]["h1"]["effective_electric_eta"] == eta
            assert result["winter"]["h1"]["effective_water"]["hw_in"] == 30
            assert abs(result["winter"]["energy_residual_kw"]) < 1e-5
            assert abs(result["winter"]["moisture_residual_kg_h"]) < 1e-5

        record("ahu/independent-water-and-eta/%s/%s" % (target_mode, override), advanced_ahu)

    def steam_power_and_reporting():
        i = dict(NM_DEFAULTS, humidifier="電熱式蒸汽", h1_source="回收熱水",
                 h2_source="停用", h1_kw="987", h2_kw="654", steam_kw="50", drift_lph="321")
        result = nm_calculate(i)
        expected = float(i["fan_qty"]) * float(i["fan_unit_kw"]) + 50
        assert result["installed_electric_kw"] == result["active_installed_electric_kw"] == expected
        assert result["circulation_lpm"] is None and result["pump_head_m"] is None
        assert result["makeup_plus_allowance_lph"] == 0
        assert result["winter"]["h1"]["effective_water"] is None
        assert "循環水量：" not in nm_report(result)

    record("report/selected-power-and-wash-scope", steam_power_and_reporting)
    return {"main_scenarios": main_scenarios, "ahu_scenarios": ahu_scenarios,
            "pressure_scenarios": pressure_scenarios, "checks": evidence,
            "passed": True, "seed": 55720261009}


def run_ui(main, check, pump):
    """Exercise real Tk interlocks in the delivered native application."""
    from .ahu_desktop import AHUWindow
    from .workspace_store import new_workspace
    from . import i18n

    original = copy.deepcopy(main.session_snapshot())
    original_path = main.path
    original_language = i18n.language()
    original_view = main.view_mode.get()
    original_pd = main.selected_pd
    original_saved = main.saved_workspace_hash
    original_hash = main.saved_hash
    child = None
    try:
        i18n.set_language("zh-Hant", persist=False)
        main.apply_workspace(new_workspace(default_project()))
        main.view_mode.set("進階模式")
        main.variables["e_up_type"].set("一般負載")
        main.variables["u_e_up_eq"].set("HP")
        main.variables["e_up_eq"].set("100")
        main.variables["e_up_largest_hp"].set("30")
        main.recalculate()
        pump()
        check("V557 general HP load enables largest-motor field", lambda: main.widgets["e_up_largest_hp"].instate(["!disabled"]) and main.result is not None)
        main.variables["e_up_type"].set("連續負載")
        main.variables["e_up_largest_hp"].set("999999")
        main.recalculate()
        pump()
        check("V557 continuous load ignores retained largest motor", lambda: main.widgets["e_up_largest_hp"].instate(["disabled"]) and main.result["electric"]["UP"]["largest_hp"] == 0)
        main.variables["e_up_type"].set("一般負載")
        main.recalculate()
        pump()
        check("V557 reactivated invalid largest motor locates its field", lambda: main.result is None and main.bad_key == "e_up_largest_hp")
        main.variables["e_up_largest_hp"].set("30")
        main.recalculate()
        child = AHUWindow(main.root, main)
        child.vars["h1_source"].set("回收熱水")
        child.vars["h1_eta"].set("0.05")
        child.vars["humidifier"].set("電熱式蒸汽")
        child.calculate()
        pump()
        check("V557 recovery-only heater ignores inactive efficiency", lambda: child.widgets["h1_eta"].instate(["disabled"]) and child.result is not None)
        check("V557 steam-only report omits wash-pump sizing", lambda: "循環水量：" not in nm_report(child.result))
        main.selected_pd = "CHW"
        main.update_visibility()
        pump()
        check("V557 closed-loop rationale is visible", lambda: "樓高" in main.pd_hint.cget("text"))
    finally:
        if child is not None and child.win.winfo_exists():
            child.close(force=True)
        main.apply_workspace(original, original_path)
        main.view_mode.set(original_view)
        main.selected_pd = original_pd
        main.saved_workspace_hash = original_saved
        main.saved_hash = original_hash
        i18n.set_language(original_language, persist=False)
        main.update_visibility()
        pump()
