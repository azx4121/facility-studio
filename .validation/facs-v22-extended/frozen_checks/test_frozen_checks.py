"""Portable unit tests, using synthetic outputs and mocked process launches.

These tests are NOT Windows, frozen EXE, visual, or engineering acceptance.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import run_frozen_cli as checks
import capture_windows


def safe_electrical():
    return {"tool": "electrical", "current_a": 2, "design_a": 2,
            "selected": None, "recommended_breaker_at": None,
            "selection_status": checks.BLOCKED,
            "_electrical_export_policy": {"selection_status": checks.BLOCKED,
                "content_kind": "load_only_result", "historical_selection_paths": [],
                "warning": "Historical numbers are not adoptable"}}


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def file(self, value, name="result.json"):
        path = self.path / name
        path.write_text(value, encoding="utf-8")
        return path


class Files(TemporaryCase):

    def test_json_unicode(self):
        self.assertEqual(checks.strict_json(self.file('{"繁體中文": 3}')), {"繁體中文": 3})

    def test_duplicate_json(self):
        with self.assertRaisesRegex(AssertionError, "Duplicate"):
            checks.strict_json(self.file('{"a": 1, "a": 2}'))

    def test_nonfinite_json(self):
        for literal in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(literal=literal), self.assertRaisesRegex(AssertionError, "Non-finite"):
                checks.strict_json(self.file('{"a": ' + literal + '}'))

    def test_wrong_json_shape(self):
        with self.assertRaisesRegex(AssertionError, "object"):
            checks.strict_json(self.file("[]"))

    def test_invalid_utf8(self):
        path = self.path / "invalid.json"
        path.write_bytes(b'{"a": "\xff"}')
        with self.assertRaises(UnicodeDecodeError):
            checks.strict_json(path)

    def test_report_unicode(self):
        value = "可讀繁體中文報告 " * 10
        self.assertEqual(checks.text_report(self.file(value)), value)

    def test_report_empty(self):
        with self.assertRaises(AssertionError):
            checks.text_report(self.file(" "))

    def test_report_replacement_character(self):
        with self.assertRaises(AssertionError):
            checks.text_report(self.file("a" * 40 + "\ufffd"))

    def test_xlsx_sheet_names(self):
        for language, electrical in (("en", "Electrical"), ("zh-Hant", "電力")):
            path = self.path / (language + ".xlsx")
            names = ["填寫 Description" if language == "en" else "填寫說明", electrical,
                     "PCW", "CDA", "N2", "EXHAUST", "DI", "PV"]
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("[Content_Types].xml", "<Types/>")
                archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets>'
                    + "".join('<sheet name="' + name + '"/>' for name in names) + "</sheets></workbook>")
            self.assertEqual(checks.workbook_sheets(path, language), names)
            with self.assertRaises(AssertionError):
                checks.workbook_sheets(path, "en" if language == "zh-Hant" else "zh-Hant")

    def test_native_gate_rejects_portable(self):
        with patch.object(checks.sys, "platform", "linux"), self.assertRaisesRegex(AssertionError, "Native Windows"):
            checks.main(["--exe", "fake.exe", "--sha256", "a" * 64, "--candidate", ".", "--evidence", "unused"])


class Electrical(unittest.TestCase):
    def test_safe_record(self):
        self.assertEqual(checks.electrical_safe(safe_electrical()), 1)

    def test_every_restricted_field(self):
        for key in checks.RESTRICTED:
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "Restricted"):
                value = safe_electrical()
                value[key] = 10
                checks.electrical_safe(value)

    def test_selected_value(self):
        value = safe_electrical()
        value["selected"] = {"other": "numeric design"}
        with self.assertRaisesRegex(AssertionError, "selection"):
            checks.electrical_safe(value)

    def test_nested_restricted_value(self):
        value = safe_electrical()
        value["nested"] = [{"pe_mm2": 2}]
        with self.assertRaisesRegex(AssertionError, "Restricted"):
            checks.electrical_safe(value)

    def test_unblocked_status(self):
        value = safe_electrical()
        value["selection_status"] = "approved"
        with self.assertRaises(AssertionError):
            checks.electrical_safe(value)

    def test_missing_export_policy(self):
        value = safe_electrical()
        value.pop("_electrical_export_policy")
        with self.assertRaisesRegex(AssertionError, "Root"):
            checks.electrical_safe(value)

    def test_forged_policy(self):
        for key, bad in (("selection_status", "approved"), ("content_kind", "historical_unverified_archive"),
                         ("historical_selection_paths", ["$.selected"]), ("warning", "All approved")):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                value = safe_electrical()
                value["_electrical_export_policy"][key] = bad
                checks.electrical_safe(value)

    def test_no_record_is_not_a_pass(self):
        with self.assertRaisesRegex(AssertionError, "No electrical"):
            checks.electrical_safe({"other": 3})

    def test_nonfinite_numeric_assertion(self):
        for number in (True, None, float("inf"), float("nan"), "2"):
            with self.subTest(number=number), self.assertRaises(AssertionError):
                checks.close(number, 2, "test")

    def test_default_lighting_independent_arithmetic(self):
        value = {"tool": "lighting", "adopted_inputs": {"area": "30"}, "failures": [],
                 "illuminance_lux": 640, "total_kw": .4}
        checks.check_default_tool("lighting", value)
        value["illuminance_lux"] = 641
        with self.assertRaises(AssertionError):
            checks.check_default_tool("lighting", value)


class Launch(TemporaryCase):
    def suite(self, launcher):
        report = {"commands": []}
        return checks.Suite(["fake.exe"], self.path / "suite", launcher,
                            lambda data: {"TEST_DATA": str(data)}, report)

    def test_zero_exit(self):
        suite = self.suite(lambda *a, **k: {"exit_code": 0})
        suite.invoke("test", ["--tool", "lighting"])
        self.assertTrue(suite.report["commands"][0]["passed"])

    def test_expected_nonzero_exit(self):
        def launch(command, log, env, timeout):
            raise RuntimeError(f"Single EXE acceptance exited 2; inspect {log}")
        suite = self.suite(launch)
        suite.invoke("test", ["--tool", "lighting"], expected=2)
        self.assertTrue(suite.report["commands"][0]["passed"])

    def test_timeout_never_accepted_as_refusal(self):
        def launch(command, log, env, timeout):
            raise RuntimeError("Single EXE acceptance timed out; inspect " + str(log))
        suite = self.suite(launch)
        with self.assertRaisesRegex(AssertionError, "Unexpected"):
            suite.invoke("test", [], expected=2)
        self.assertFalse(suite.report["commands"][0]["passed"])

    def test_wrong_exit_never_accepted(self):
        def launch(command, log, env, timeout):
            raise RuntimeError(f"Single EXE acceptance exited 3; inspect {log}")
        with self.assertRaises(AssertionError):
            self.suite(launch).invoke("test", [], expected=2)

    def test_success_cannot_satisfy_refusal(self):
        with self.assertRaises(AssertionError):
            self.suite(lambda *a, **k: {"exit_code": 0}).invoke("test", [], expected=2)

    def test_stale_export_unchanged(self):
        def launch(command, log, env, timeout):
            raise RuntimeError(f"Single EXE acceptance exited 2; inspect {log}")
        suite = self.suite(launch)
        result = self.file('{"known": "previous successful result"}')
        report = self.file("previous successful report" * 3, "previous.txt")
        suite.refusal("invalid", ["--tool", "electrical"], result, report)
        self.assertEqual(len(suite.report["commands"]), 2)

    def test_fresh_export_on_failure_rejected(self):
        def launch(command, log, env, timeout):
            Path(command[command.index("--result") + 1]).write_text("stale", encoding="utf-8")
            raise RuntimeError(f"Single EXE acceptance exited 2; inspect {log}")
        with self.assertRaisesRegex(AssertionError, "fresh"):
            self.suite(launch).refusal("invalid", [], self.file("{}"), self.file("old", "old.txt"))

    def test_stale_export_changed_on_failure_rejected(self):
        def launch(command, log, env, timeout):
            result = Path(command[command.index("--result") + 1])
            if result.exists():
                result.write_text("overwritten", encoding="utf-8")
            raise RuntimeError(f"Single EXE acceptance exited 2; inspect {log}")
        with self.assertRaisesRegex(AssertionError, "previous export"):
            self.suite(launch).refusal("invalid", [], self.file("{}"), self.file("old", "old.txt"))


class NativeCaptureBoundary(unittest.TestCase):
    def test_no_linux_capture_fallback(self):
        with patch.object(capture_windows.sys, "platform", "linux"), self.assertRaisesRegex(RuntimeError, "native Windows"):
            capture_windows.NativeWindows()

    def test_full_display_rectangle(self):
        self.assertTrue(capture_windows.rect_inside([0, 0, 1024, 728], [0, 0, 1024, 728]))

    def test_offscreen_padding_rejected(self):
        for window in ([-1, 0, 1000, 700], [0, -1, 1000, 700], [0, 0, 1200, 700], [0, 0, 1000, 800]):
            with self.subTest(window=window):
                self.assertFalse(capture_windows.rect_inside(window, [0, 0, 1024, 728]))

    def test_negative_coordinate_secondary_display(self):
        self.assertTrue(capture_windows.rect_inside([-1900, 0, -50, 900], [-1920, 0, 0, 1080]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
