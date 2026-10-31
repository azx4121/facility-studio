"""Electrical power-unit regression checks; --gui also exercises real Tk widgets.

These tests use temporary CLI outputs and never rewrite checked-in evidence.
Run on either source mirror: python tests/electrical_units.py [--gui].
"""

import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WITH_GUI = "--gui" in sys.argv
if WITH_GUI:
    sys.argv.remove("--gui")

from facility_studio import i18n
from facility_studio.errors import ValidationError
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_reports import tool_report
from facility_studio.simple_schema import active_field, defaults


def inputs(**changes):
    return dict(defaults("electrical"), **{key: str(value) for key, value in changes.items()})


def calculate(**changes):
    return calculate_tool("electrical", inputs(**changes))


class PowerUnits(unittest.TestCase):
    def close(self, actual, expected):
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (actual, expected))

    def test_equivalent_inputs_preserve_current_breaker_wire_and_drop(self):
        # Factors here are an independent specification, not imported from the model.
        factors = {"kW": 1, "W": .001, "HP": .745699871582 / .82, "PS": .73549875 / .82}
        for supply, phases, voltage in (("三相 380V", 3, 380), ("單相 220V", 1, 220)):
            baseline = calculate(power=9.5, kind="馬達", supply=supply)
            for unit, factor in factors.items():
                with self.subTest(supply=supply, unit=unit):
                    result = calculate(power=9.5/factor, power_unit=unit, motor_efficiency=.82, kind="馬達", supply=supply)
                    self.close(result["power_kw"], 9.5)
                    self.close(result["current_a"], 9500/((math.sqrt(3) if phases == 3 else 1)*voltage*.85))
                    self.close(result["design_a"], baseline["design_a"])
                    for key, value in baseline["selected"].items():
                        if isinstance(value, (int, float)) and value is not None:
                            self.close(result["selected"][key], value)
                        else:
                            self.assertEqual(result["selected"][key], value)

    def test_horsepower_uses_shaft_efficiency_and_motor_allowance(self):
        for unit, shaft_kw in (("HP", 10*.745699871582), ("PS", 10*.73549875)):
            with self.subTest(unit=unit):
                result = calculate(power=10, power_unit=unit, motor_efficiency=.9)
                self.close(result["shaft_kw"], shaft_kw)
                self.close(result["power_kw"], shaft_kw/.9)
                self.close(result["design_a"], result["current_a"]*1.25)
                self.close(result["motor_efficiency"], .9)

    def test_legacy_kw_inputs_and_report_remain_usable(self):
        legacy = inputs()
        del legacy["power_unit"], legacy["motor_efficiency"]
        self.assertEqual(calculate_tool("electrical", legacy), calculate())
        self.assertIn("10 kW", tool_report(calculate_tool("electrical", legacy), legacy, language="en"))
        for power in (10, 10.5):
            with self.subTest(numeric_power=power):
                legacy["power"] = power
                original = copy.deepcopy(legacy)
                result = calculate_tool("electrical", legacy)
                self.close(result["power_kw"], power)
                for language in ("en", "zh-Hant"):
                    self.assertIn(f"{power} kW", tool_report(result, legacy, language=language))
                self.assertEqual(legacy, original)

    def test_efficiency_draft_is_only_active_for_motor_units(self):
        for unit in ("kW", "W"):
            data = inputs(power_unit=unit, motor_efficiency="unfinished")
            self.assertFalse(active_field("electrical", "motor_efficiency", data))
            self.assertIsNone(calculate_tool("electrical", data)["motor_efficiency"])
            self.assertNotIn("unfinished", tool_report(calculate_tool("electrical", data), data))
        for unit in ("HP", "PS"):
            self.assertTrue(active_field("electrical", "motor_efficiency", inputs(power_unit=unit)))
            for bad in ("", "unfinished", "NaN", "0", ".099", "1.01"):
                with self.subTest(unit=unit, efficiency=bad), self.assertRaises(ValidationError) as error:
                    calculate(power_unit=unit, motor_efficiency=bad)
                self.assertEqual(error.exception.field_name, "motor_efficiency")

    def test_invalid_power_and_units_are_rejected(self):
        for unit in ("", "US RT", "kcal/h", "BTU/h", "MW", "hp", "arbitrary"):
            with self.subTest(unit=unit), self.assertRaises(ValidationError) as error:
                calculate(power_unit=unit)
            self.assertEqual(error.exception.field_name, "power_unit")
        for unit in ("kW", "W", "HP", "PS"):
            for bad in ("", "NaN", "Infinity", "-1"):
                with self.subTest(unit=unit, power=bad), self.assertRaises(ValidationError) as error:
                    calculate(power_unit=unit, power=bad)
                self.assertEqual(error.exception.field_name, "power")

    def test_power_limit_is_applied_after_unit_conversion(self):
        result = calculate(power=1_000_001, power_unit="W", length=0, terminal=90)
        self.close(result["power_kw"], 1000.001)
        for unit, power in (("kW", 1_000_001), ("W", 1_000_000_001), ("HP", 2_000_000), ("PS", 2_000_000)):
            with self.subTest(unit=unit), self.assertRaises(ValidationError) as error:
                calculate(power=power, power_unit=unit)
            self.assertEqual(error.exception.field_name, "power")

    def test_zero_demand_in_each_unit(self):
        for unit in ("kW", "W", "HP", "PS"):
            result = calculate(power=0, power_unit=unit)
            self.assertEqual(result["power_kw"], 0)
            self.assertEqual(result["current_a"], 0)
            self.assertIsNone(result["selected"])

    def test_bilingual_reports_retain_units_and_adopted_efficiency(self):
        for unit in ("kW", "W", "HP", "PS"):
            data = inputs(power=10, power_unit=unit, motor_efficiency=.82)
            result = calculate_tool("electrical", data)
            original = copy.deepcopy((data, result))
            english = tool_report(result, data, language="en")
            chinese = tool_report(result, data, language="zh-Hant")
            self.assertNotRegex(english, r"[\u3400-\u9fff]")
            self.assertRegex(english, r"Equipment power\s*[:：]\s*10 " + unit)
            self.assertIn("電氣輸入", chinese)
            if unit in ("HP", "PS"):
                self.assertRegex(english, r"Motor efficiency η\s*[:：]\s*0\.82")
                self.assertIn("Shaft output", english)
            self.assertEqual((data, result), original)

    def test_cli_json_input_and_result_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="facility-power-units-") as temporary:
            path = Path(temporary)
            source, output, report = path/"input.json", path/"result.json", path/"report.txt"
            for unit, value in (("kW", 10), ("W", 10000), ("HP", 10*.9/.745699871582), ("PS", 10*.9/.73549875)):
                source.write_text(json.dumps(dict(power=value, power_unit=unit, motor_efficiency=.9)), encoding="utf-8")
                command = [sys.executable, str(ROOT/"Facility_Studio_V5_5.py"), "--tool", "electrical", "--tool-input", str(source), "--result", str(output), "--report", str(report)]
                run = subprocess.run(command, text=True, capture_output=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                result = json.loads(output.read_text())
                self.close(result["power_kw"], 10)
                self.assertEqual(result["power_unit"], unit)
                self.assertIn(unit, report.read_text())
            source.write_text('{"power_unit":"VA"}', encoding="utf-8")
            output.unlink()
            run = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(output.exists())


@unittest.skipUnless(WITH_GUI, "Pass --gui under a display to exercise Tk")
class PowerUnitWidgets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        from facility_studio.simple_desktop import SimpleToolsApp
        cls.old_language = i18n.language()
        i18n.set_language("zh-Hant", persist=False)
        cls.root = tk.Tk()
        cls.callbacks = []
        cls.root.report_callback_exception = lambda *args: cls.callbacks.append(str(args))
        cls.app = SimpleToolsApp(cls.root)

    def setUp(self):
        i18n.set_language("zh-Hant", persist=False)
        self.app.show_tool("electrical")
        self.page = self.app.active_page()
        self.page.reset()
        self.root.update()

    def tearDown(self):
        self.assertEqual(self.callbacks, [])

    @classmethod
    def tearDownClass(cls):
        i18n.set_language(cls.old_language, persist=False)
        self.root.destroy()

    def choose(self, unit):
        widget = self.page.widgets["power_unit"]
        widget.current(tuple(widget.cget("values")).index(unit))
        widget.event_generate("<<ComboboxSelected>>")
        self.page.calculate()
        self.root.update()

    def test_readonly_unit_switches_preserve_load_and_motor_settings(self):
        widget = self.page.widgets["power_unit"]
        self.assertEqual(str(widget.cget("state")), "readonly")
        self.assertEqual(tuple(widget.cget("values")), ("kW", "W", "HP", "PS", "A", "kVA"))
        original = self.page.result["current_a"]
        self.assertFalse(self.page.rows["motor_efficiency"].winfo_manager())
        for _ in range(3):
            for unit in ("W", "HP", "PS", "kW"):
                self.choose(unit)
                self.assertTrue(math.isclose(self.page.result["current_a"], original, rel_tol=1e-12))
                self.assertEqual(bool(self.page.rows["motor_efficiency"].winfo_manager()), unit in ("HP", "PS"))
        self.assertEqual(self.page.variables["kind"].get(), "馬達")
        self.assertTrue(math.isclose(self.page.result["design_a"], original*1.25))

    def test_bilingual_navigation_preserves_power_unit_and_efficiency_draft(self):
        self.choose("HP")
        self.page.variables["motor_efficiency"].set(".82")
        self.page.variables["power"].set("10")
        self.page.calculate()
        original = copy.deepcopy((self.page.data(), self.page.result))
        for language in ("en", "zh-Hant", "en"):
            i18n.set_language(language, persist=False)
            self.app.show_tool("water")
            self.app.show_tool("electrical")
            self.page.calculate()
            self.root.update()
            self.assertEqual((self.page.data(), self.page.result), original)
            if language == "en":
                self.assertEqual(self.page.labels["motor_efficiency"].cget("text"), "Motor efficiency η")
                self.assertNotRegex(self.page.note.cget("text") + self.page.formula.cget("text"), r"[\u3400-\u9fff]")
        self.choose("W")
        self.assertEqual(self.page.variables["motor_efficiency"].get(), ".82")
        self.choose("HP")
        self.assertEqual(self.page.variables["motor_efficiency"].get(), ".82")

    def test_invalid_unit_switch_rolls_back_without_destroying_draft(self):
        self.page.variables["power"].set("unfinished")
        self.choose("HP")
        self.assertEqual(self.page.variables["power_unit"].get(), "kW")
        self.assertEqual(self.page.variables["power"].get(), "unfinished")
        self.assertEqual(self.page.variables["kind"].get(), "一般設備")
        self.assertIsNone(self.page.result)
        self.assertTrue(self.app.export_button.instate(["disabled"]))
        self.page.reset()
        self.choose("HP")
        self.page.variables["motor_efficiency"].set("bad")
        self.page.calculate()
        self.assertIsNone(self.page.result)
        self.assertIn("馬達效率", self.page.status.cget("text"))
        # Invalid active efficiency prevents leaving HP, retaining a visible,
        # editable field and the original shaft-output draft until corrected.
        draft = self.page.variables["power"].get()
        self.choose("W")
        self.assertEqual(self.page.variables["power_unit"].get(), "HP")
        self.assertEqual(self.page.variables["power"].get(), draft)
        self.assertTrue(self.page.rows["motor_efficiency"].winfo_manager())
        self.page.variables["motor_efficiency"].set(".8")
        self.page.calculate()
        expected = self.page.result["power_kw"]
        self.choose("W")
        self.assertTrue(math.isclose(self.page.result["power_kw"], expected))
        self.page.reset()
        self.assertEqual(self.page.variables["power_unit"].get(), "kW")
        self.assertEqual(self.page.variables["motor_efficiency"].get(), "0.90")
        self.assertIsNotNone(self.page.result)


if __name__ == "__main__":
    unittest.main()
