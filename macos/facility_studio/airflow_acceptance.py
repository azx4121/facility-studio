"""OA capability, FFU continuity, room outflow and historical project checks."""
import copy
import math
import sys
import tempfile
import unittest
import io
from pathlib import Path

from . import api
from .engine import migrate_project
from .design_workflow import ahu_requirement_updates
from .field_state import main_inactive
from .project_store import save_project_file
from .schema import BASIC_KEYS, FIELDS, GROUPS, V556_INPUT_KEYS, V560_INPUT_KEYS


def project(**changes):
    p = api.default_project()
    p["inputs"].update(
        sys_type="MAU+FFU+DCC (全外氣/無塵室)",
        en_L_A="100", en_W_A="83", en_H_A="3", en_ach_A="80",
        ppl_A="100", en_manual_oa="0", oa_capacity_cmh="58000",
        ffu_flow_basis="回風循環（外氣另加）", ffu_oa_route="外氣經 FFU",
        pre_mode="停用／旁通", en_wall="0", en_floor="0",
        gex_q="0", exhaust_margin_pct="0",
    )
    p["inputs"].update({k: str(v) for k, v in changes.items()})
    return p


def finding(result, name):
    return next(x for x in result["quality"]["items"] if x["name"] == name)


class AirflowBalance(unittest.TestCase):
    def near(self, actual, expected):
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-7),
                        (actual, expected))

    def test_user_case_uses_maximum_for_ffu_without_forcing_oa(self):
        r = api.calculate(project())
        self.assertEqual(r["counts"]["FFU"], 2050)
        self.near(r["ffu_airflow"]["supply_cmh"], 2050000)
        self.near(r["ffu_airflow"]["return_cmh"], 1992000)
        self.assertLess(r["oa_room_cmh"], 58000)
        self.assertGreaterEqual(r["oa_room_cmh"], 2400)
        self.near(r["dcc_airside"]["flow_cmh"], 1992000)
        self.assertEqual(finding(r, "MAU 最大外氣能力")["status"], "通過")
        text = str(api.report(r))
        self.assertIn("MAU 最大可用 OA 58000.00", text)
        self.assertIn("FFU 設計總送風 2050000.00", text)

    def test_total_supply_ach_does_not_add_oa_twice(self):
        r = api.calculate(project(ffu_flow_basis="總送風（含外氣）"))
        self.assertEqual(r["counts"]["FFU"], 1992)
        self.near(r["ffu_airflow"]["supply_cmh"], 1992000)
        self.near(r["ffu_airflow"]["return_cmh"], 1934000)
        self.near(r["dcc_airside"]["flow_cmh"], 1934000)

    def test_coils_and_water_are_sized_at_peak_oa_not_small_operating_flow(self):
        automatic = api.calculate(project())
        full_flow = api.calculate(project(en_manual_oa=58000))
        self.near(automatic["mau_design"]["oa_cmh"], 58000)
        self.assertLess(automatic["summer"]["mass"], automatic["mau_design"]["mass_da"])
        for loop in ("MCHW", "CHW", "HW", "DCCW"):
            self.near(automatic["water"][loop]["load_kw"], full_flow["water"][loop]["load_kw"])
        self.assertIn("MAU 另核最大／未來設計風量 58000.00", str(api.report(automatic)))

    def test_specified_operating_oa_is_separate_from_maximum(self):
        r = api.calculate(project(en_manual_oa=40000))
        self.near(r["oa_room_cmh"], 40000)
        self.near(r["ffu_airflow"]["sizing_oa_cmh"], 58000)
        self.assertEqual(r["counts"]["FFU"], 2050)
        self.near(r["ffu_airflow"]["operating_return_cmh"], 2010000)

    def test_ahu_link_uses_peak_design_flow_when_available(self):
        r = api.calculate(project())
        updates = ahu_requirement_updates(r)
        for season in ("summer", "winter"):
            state = r["mau_design"][season]["supply"]
            linked_mass = float(updates[season + "_flow"]) / state["v_da"] / 3600
            self.near(linked_mass, r["mau_design"]["mass_da"])
            self.assertGreater(linked_mass, r[season]["mass"])
        no_peak = api.calculate(project(en_manual_oa=58000))
        self.assertIsNone(no_peak["mau_design"])
        updates = ahu_requirement_updates(no_peak)
        self.near(float(updates["summer_flow"]) /
                  no_peak["summer"]["supply"]["v_da"] / 3600, no_peak["summer"]["mass"])

    def test_more_exhaust_does_not_reduce_ffu_count(self):
        low = api.calculate(project(gex_q=10000))
        high = api.calculate(project(gex_q=20000))
        self.assertEqual(low["counts"]["FFU"], high["counts"]["FFU"])
        self.near(low["oa_room_cmh"], 10000)
        self.near(high["oa_room_cmh"], 20000)
        self.near(low["ffu_airflow"]["operating_return_cmh"]
                  - high["ffu_airflow"]["operating_return_cmh"], 10000)

    def test_maximum_below_operating_demand_fails_capability(self):
        r = api.calculate(project(en_manual_oa=58000, oa_capacity_cmh=40000))
        self.assertEqual(finding(r, "MAU 最大外氣能力")["status"], "未達")
        self.assertEqual(r["quality"]["status"], "未達條件")
        self.near(r["oa_room_cmh"], 58000)  # Still a demand point, not false capability.

    def test_future_and_safety_allowance_do_not_force_current_operation(self):
        r = api.calculate(project(gex_q=20000, oa_future_cmh=30000, oa_reserve_pct=25))
        self.near(r["oa_room_cmh"], 20000)
        self.near(r["oa_balance"]["design_required_cmh"], 62500)
        self.assertEqual(finding(r, "MAU 最大外氣能力")["status"], "未達")
        enough = api.calculate(project(gex_q=20000, oa_future_cmh=30000,
                                       oa_reserve_pct=25, oa_capacity_cmh=70000))
        self.assertEqual(finding(enough, "MAU 最大外氣能力")["status"], "通過")
        self.near(enough["oa_room_cmh"], 20000)

    def test_room_and_ffu_continuity_including_people_oa(self):
        r = api.calculate(project(gex_q=20000, en_manual_oa=40000,
                                  en_gap_L=100, en_gap_W=.005, en_p_A=20, prd_q=1000))
        b, f = r["oa_balance"], r["ffu_airflow"]
        self.near(b["operating_cmh"], b["exhaust_cmh"] + b["target_leakage_cmh"]
                  + b["target_relief_cmh"] + b["extra_outflow_cmh"])
        self.near(f["supply_cmh"], f["operating_return_cmh"] + b["operating_cmh"])
        self.near(f["supply_cmh"], f["operating_return_cmh"] + b["exhaust_cmh"]
                  + b["target_outflow_cmh"] + b["extra_outflow_cmh"])
        personnel_only = api.calculate(project())
        self.near(personnel_only["extra_relief_cmh"], personnel_only["oa_room_cmh"])

    def test_independent_oa_is_not_added_to_ffu(self):
        r = api.calculate(project(ffu_oa_route="外氣獨立送入室內"))
        self.assertEqual(r["counts"]["FFU"], 1992)
        f = r["ffu_airflow"]
        self.near(f["supply_cmh"], f["return_cmh"])
        self.near(f["oa_through_design_cmh"], 0)
        self.near(f["room_supply_cmh"], f["supply_cmh"] + r["oa_room_cmh"])

    def test_inactive_mau_fields_do_not_poison_other_systems(self):
        p = project(sys_type="AHU (OA+RA 混合)", oa_capacity_cmh="bad",
                    ffu_flow_basis="bad", ffu_oa_route="bad")
        self.assertTrue({"oa_capacity_cmh", "ffu_flow_basis", "ffu_oa_route"}
                        <= set(main_inactive(p["inputs"])))
        r = api.calculate(p)
        self.assertIsNone(r["ffu_airflow"])
        self.near(r["oa_balance"]["capacity_cmh"], 0)
        p["inputs"]["sys_type"] = "MAU+FFU+DCC (全外氣/無塵室)"
        with self.assertRaises(api.ValidationError):
            api.calculate(p)

    def test_manual_oa_below_current_exhaust_is_rejected(self):
        with self.assertRaises(api.ValidationError) as error:
            api.calculate(project(gex_q=20000, en_manual_oa=19000))
        self.assertEqual(error.exception.field_name, "en_manual_oa")

    def test_face_velocity_is_a_total_supply_requirement(self):
        with self.assertRaises(api.ValidationError) as error:
            api.calculate(project(mode_A="截面風速"))
        self.assertEqual(error.exception.field_name, "ffu_flow_basis")
        r = api.calculate(project(mode_A="截面風速", ffu_flow_basis="總送風（含外氣）"))
        self.near(r["ffu_airflow"]["supply_cmh"], 8300 * .35 * 3600)

    def test_all_incoming_oa_must_fit_through_ffu(self):
        r = api.calculate(project(en_L_A=10, en_W_A=10, en_H_A=3, en_ach_A=10,
                                  ffu_flow_basis="總送風（含外氣）"))
        self.assertEqual(r["counts"]["FFU"], 58)
        self.near(r["ffu_airflow"]["supply_cmh"], 58000)
        self.near(r["ffu_airflow"]["return_cmh"], 0)

    def test_ffu_heat_is_updated_after_oa_based_count(self):
        return_based = api.calculate(project(ffu_w=50))
        supply_based = api.calculate(project(ffu_w=50, ffu_flow_basis="總送風（含外氣）"))
        self.near(return_based["qs"] - supply_based["qs"], 58 * 50 / 1000)
        self.near(return_based["parts"]["fan"] - supply_based["parts"]["fan"], 2.9)

    def test_old_project_migration_preserves_manual_oa_without_guessing_capacity(self):
        for version, keys in ((10, V556_INPUT_KEYS), (11, V560_INPUT_KEYS)):
            with self.subTest(version=version):
                p = project(en_manual_oa=58000)
                p["schema_version"] = version
                p["inputs"] = {k: v for k, v in p["inputs"].items() if k in keys}
                p["provenance"] = {k: v for k, v in p["provenance"].items() if k in keys}
                original = copy.deepcopy(p)
                migrated = migrate_project(p)
                self.assertEqual(migrated["schema_version"], 12)
                self.assertEqual(migrated["inputs"]["en_manual_oa"], "58000")
                self.assertEqual(migrated["inputs"]["oa_capacity_cmh"], "0")
                self.assertEqual(migrated["inputs"]["ffu_flow_basis"], "總送風（含外氣）")
                self.assertEqual(migrate_project(p), migrated)
                self.assertEqual(p, original)
                r = api.calculate(p)
                self.assertEqual(r["counts"]["FFU"], 1992)
                self.assertEqual(finding(r, "MAU 最大外氣能力")["status"], "待資料")
                self.assertEqual(r["hash"], api.calculate(p)["hash"])
                incomplete = copy.deepcopy(p)
                incomplete["inputs"].pop("en_manual_oa")
                with self.assertRaises(api.ValidationError):
                    migrate_project(incomplete)

    def test_capacity_and_oa_fields_are_distinct_and_visible_in_basic_forms(self):
        for key in ("en_manual_oa", "oa_capacity_cmh", "oa_future_cmh",
                    "oa_reserve_pct", "ffu_flow_basis", "ffu_oa_route"):
            self.assertIn(key, BASIC_KEYS)
            self.assertEqual(FIELDS[key]["page"], 1)
            self.assertEqual(sum(key in row[2] for row in GROUPS), 1)
            self.assertTrue(any("外氣 OA" in row[1] and key in row[2] for row in GROUPS))

    def test_positive_pressure_target_without_leakage_data_remains_pending(self):
        r = api.calculate(project(en_p_A=20))
        self.assertEqual(finding(r, "OA 補償與正壓必要條件")["status"], "待資料")

    def test_100_physical_cases_preserve_balances_and_saved_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            for index in range(100):
                with self.subTest(case=index + 1):
                    length, width, height = 12 + index * .21, 8 + index * .04, 3 + index % 4 * .25
                    ach, exhaust = 12 + index % 7 * 2, 100 + index * 30
                    future, margin = 50 + index % 5 * 100, 5 + index % 5 * 5
                    capacity = (exhaust + future) * (1 + margin / 100) + 500
                    unit = 700 + index * 3
                    return_basis, through_ffu = bool(index % 2), bool(index % 3)
                    p = project(en_L_A=length, en_W_A=width, en_H_A=height,
                                en_ach_A=ach, ppl_A=0, gex_q=exhaust,
                                oa_future_cmh=future, oa_reserve_pct=margin,
                                oa_capacity_cmh=capacity, ffu_cmh=unit,
                                ffu_flow_basis="回風循環（外氣另加）" if return_basis else "總送風（含外氣）",
                                ffu_oa_route="外氣經 FFU" if through_ffu else "外氣獨立送入室內")
                    original = copy.deepcopy(p)
                    r = api.calculate(p)
                    desired = length * width * height * ach
                    oa_through = capacity if through_ffu else 0
                    expected = desired + oa_through if return_basis else max(desired, oa_through)
                    self.assertEqual(r["counts"]["FFU"], math.ceil(expected / unit - 1e-12))
                    self.near(r["ffu_airflow"]["supply_cmh"], expected)
                    self.near(r["oa_room_cmh"], exhaust)
                    self.near(r["oa_balance"]["design_required_cmh"],
                              (exhaust + future) * (1 + margin / 100))
                    f = r["ffu_airflow"]
                    self.near(f["supply_cmh"], f["return_cmh"] + oa_through)
                    self.near(f["supply_cmh"], f["operating_return_cmh"] +
                              (exhaust if through_ffu else 0))
                    self.assertEqual(finding(r, "MAU 最大外氣能力")["status"], "通過")
                    path = Path(directory) / ("airflow-%03d.json" % index)
                    save_project_file(path, p)
                    restored = api.read_project(path)
                    self.assertEqual(api.calculate(restored)["hash"], r["hash"])
                    self.assertEqual(api.calculate(p)["counts"], r["counts"])
                    self.assertEqual(p, original)



def run_checks():
    """Run the same physical regressions inside the delivered runtime."""
    from . import i18n
    previous = i18n.language()
    stream = io.StringIO()
    try:
        i18n.set_language("zh-Hant", persist=False)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(AirflowBalance)
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
        return dict(passed=result.wasSuccessful(), tests_run=result.testsRun,
                    physical_cases=100,
                    failures=[dict(test=str(test), detail=detail)
                              for test, detail in result.failures + result.errors],
                    output=stream.getvalue())
    finally:
        i18n.set_language(previous, persist=False)


def run_ui(main, check, pump):
    """Exercise the actual delivered widgets, retaining the original document."""
    from . import i18n
    from tkinter import ttk as native_ttk
    original = main.snapshot()
    previous_view = main.view_mode.get()
    previous_page = main.current
    previous_language = i18n.language()
    try:
        for lang in ("zh-Hant", "en"):
            i18n.set_language(lang, persist=False)
            main.apply_project(project())
            main.view_mode.set("基本模式")
            main.show_page(1)
            main.recalculate()
            pump()
            check("OA FFU native 2050 units " + lang,
                  lambda: main.result is not None and main.result["counts"]["FFU"] == 2050)
            for key in ("en_manual_oa", "oa_capacity_cmh", "oa_future_cmh",
                        "oa_reserve_pct", "ffu_flow_basis", "ffu_oa_route"):
                check("OA native visible active field " + key + "/" + lang,
                      lambda field=key: main.form_rows[field].winfo_manager() == "grid"
                      and str(main.widgets[field].cget("state")) != "disabled")
            main.variables["en_manual_oa"].set("40000")
            main.recalculate()
            pump()
            check("OA native operation separated from capacity " + lang,
                  lambda: main.result is not None
                  and abs(main.result["oa_room_cmh"] - 40000) < 1e-6
                  and main.variables["oa_capacity_cmh"].get() == "58000"
                  and main.result["counts"]["FFU"] == 2050)
            main.variables["sys_type"].set("AHU (OA+RA 混合)")
            main.recalculate()
            pump()
            check("OA native other-system interlocks " + lang,
                  lambda: main.result is not None
                  and all(str(main.widgets[key].cget("state")) == "disabled"
                          for key in ("oa_capacity_cmh", "ffu_flow_basis", "ffu_oa_route"))
                  and str(main.widgets["en_manual_oa"].cget("state")) == "normal")
            main.variables["sys_type"].set("MAU+FFU+DCC (全外氣/無塵室)")
            main.recalculate()
            pump()
            check("OA native capacity draft restored " + lang,
                  lambda: main.result is not None and main.result["counts"]["FFU"] == 2050
                  and main.variables["oa_capacity_cmh"].get() == "58000")
            if lang == "en":
                check("OA native English FFU choice",
                      lambda: "Total supply" in str(native_ttk.Combobox.cget(
                          main.widgets["ffu_flow_basis"], "values")))
    finally:
        main.apply_project(original)
        main.view_mode.set(previous_view)
        main.show_page(previous_page)
        main.recalculate()
        i18n.set_language(previous_language, persist=False)
        pump()
