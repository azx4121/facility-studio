"""Portable unit tests, using synthetic outputs and mocked process launches.

These tests are NOT Windows, frozen EXE, visual, or engineering acceptance.
"""
import copy
import ctypes
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

    def workbook(self, names, filename="sheets.xlsx"):
        path = self.path / filename
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets>'
                + "".join('<sheet name="' + name + '"/>' for name in names) + "</sheets></workbook>")
        return path

    def test_xlsx_sheet_names(self):
        for language, electrical in (("en", "Electrical"), ("zh-Hant", "電力")):
            names = ["Instructions" if language == "en" else "填寫說明", electrical,
                     "PCW", "CDA", "N2", "EXHAUST", "DI", "PV"]
            path = self.workbook(names, language + ".xlsx")
            self.assertEqual(checks.workbook_sheets(path, language), names)
            with self.assertRaises(AssertionError):
                checks.workbook_sheets(path, "en" if language == "zh-Hant" else "zh-Hant")

    def test_xlsx_english_rejects_old_or_untranslated_instruction_title(self):
        for title in ("填寫 Description", "填寫說明", "Description"):
            with self.subTest(title=title), self.assertRaisesRegex(AssertionError, "Wrong Excel template sheets"):
                checks.workbook_sheets(self.workbook([
                    title, "Electrical", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV"]), "en")

    def test_xlsx_all_seven_system_sheets_remain_required(self):
        names = ["Instructions", "Electrical", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV"]
        for index in range(1, len(names)):
            with self.subTest(missing=names[index]), self.assertRaisesRegex(AssertionError, "Wrong Excel template sheets"):
                checks.workbook_sheets(self.workbook(names[:index] + names[index + 1:]), "en")

    def test_xlsx_duplicate_sheet_title_rejected(self):
        names = ["Instructions", "Electrical", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV", "Instructions"]
        with self.assertRaisesRegex(AssertionError, "Wrong Excel template sheets"):
            checks.workbook_sheets(self.workbook(names), "en")

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
    @staticmethod
    def geometry():
        # Synthetic values illustrate the native failure's plausible cause.
        # These are NOT measured DWM/client values from the failed native run.
        return {"outer_rect": [156, 156, 1612, 1045],
                "visible_frame_rect": [163, 156, 1605, 1038],
                "client_screen_rect": [164, 187, 1604, 1037],
                "dwm_hresult": 0, "client_query_succeeded": True}

    @staticmethod
    def display():
        return {"virtual_display": [0, 0, 1920, 1080],
                "nearest_monitor": [0, 0, 1920, 1080],
                "nearest_work_area": [0, 0, 1920, 1040]}

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

    def test_zero_reversed_or_invalid_rectangles_fail(self):
        for rectangle in (None, [], [0, 0, 0, 0], [5, 5, 2, 2], [0, 0, 2], [0., 0, 2, 2], [False, 0, 2, 2]):
            with self.subTest(rectangle=rectangle):
                self.assertFalse(capture_windows.rect_inside(rectangle, [0, 0, 1920, 1080]))

    def test_invisible_border_outside_work_area_is_not_visible_clipping(self):
        geometry, display = self.geometry(), self.display()
        self.assertEqual(capture_windows.capture_rectangle(geometry, display), geometry["visible_frame_rect"])
        flags = capture_windows.containment_flags(geometry, display)
        self.assertFalse(flags["outer_inside_nearest_work_area"])
        self.assertTrue(flags["visible_frame_inside_nearest_work_area"])
        self.assertTrue(flags["client_screen_inside_nearest_work_area"])

    def test_no_fixed_eight_pixel_border_assumption(self):
        geometry = self.geometry()
        geometry["outer_rect"] = [140, 150, 1630, 1060]
        self.assertEqual(capture_windows.capture_rectangle(geometry, self.display()), geometry["visible_frame_rect"])

    def test_visible_frame_one_pixel_under_taskbar_fails(self):
        geometry = self.geometry()
        geometry["visible_frame_rect"][3] = 1041
        with self.assertRaisesRegex(RuntimeError, "clipped"):
            capture_windows.capture_rectangle(geometry, self.display())

    def test_visible_frame_exact_work_area_boundary_passes(self):
        geometry = self.geometry()
        geometry["visible_frame_rect"][3] = 1040  # right/bottom coordinates are exclusive
        self.assertEqual(capture_windows.capture_rectangle(geometry, self.display()), geometry["visible_frame_rect"])

    def test_client_one_pixel_under_taskbar_fails(self):
        geometry = self.geometry()
        geometry["visible_frame_rect"][3] = 1043
        geometry["client_screen_rect"][3] = 1041
        with self.assertRaisesRegex(RuntimeError, "clipped"):
            capture_windows.capture_rectangle(geometry, self.display())

    def test_clipped_title_fails_even_when_client_fits(self):
        geometry = self.geometry()
        geometry["outer_rect"][1] = -10
        geometry["visible_frame_rect"][1] = -1
        with self.assertRaisesRegex(RuntimeError, "clipped"):
            capture_windows.capture_rectangle(geometry, self.display())

    def test_clipped_display_fails_even_with_bad_larger_work_area(self):
        display = self.display()
        display["nearest_monitor"][3] = 1037
        with self.assertRaisesRegex(RuntimeError, "clipped"):
            capture_windows.capture_rectangle(self.geometry(), display)

    def test_virtual_desktop_bounds_are_enforced(self):
        display = self.display()
        display["virtual_display"][2] = 1604
        with self.assertRaisesRegex(RuntimeError, "clipped"):
            capture_windows.capture_rectangle(self.geometry(), display)

    def test_missing_or_failed_dwm_never_falls_back(self):
        for status in (None, -2147024891, 1):
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, "DWM"):
                geometry = self.geometry()
                geometry["dwm_hresult"] = status
                capture_windows.capture_rectangle(geometry, self.display())

    def test_failed_client_query_never_passes(self):
        geometry = self.geometry()
        geometry["client_query_succeeded"] = False
        with self.assertRaisesRegex(RuntimeError, "Client"):
            capture_windows.capture_rectangle(geometry, self.display())

    def test_bad_dwm_frame_never_passes(self):
        for rectangle in (None, [0, 0, 0, 0], [163, 156, 1620, 1038]):
            with self.subTest(rectangle=rectangle), self.assertRaises(RuntimeError):
                geometry = self.geometry()
                geometry["visible_frame_rect"] = rectangle
                capture_windows.capture_rectangle(geometry, self.display())

    def test_client_outside_visible_frame_never_passes(self):
        geometry = self.geometry()
        geometry["client_screen_rect"][3] = 1039
        with self.assertRaisesRegex(RuntimeError, "Client area"):
            capture_windows.capture_rectangle(geometry, self.display())

    def test_negative_physical_coordinates_pass_on_secondary_monitor(self):
        geometry, display = self.geometry(), self.display()
        for rectangle in ("outer_rect", "visible_frame_rect", "client_screen_rect"):
            geometry[rectangle][0] -= 1920
            geometry[rectangle][2] -= 1920
        for rectangle in display:
            display[rectangle][0] -= 1920
            display[rectangle][2] -= 1920
        self.assertEqual(capture_windows.capture_rectangle(geometry, display), geometry["visible_frame_rect"])


class MockNativeGeometry(unittest.TestCase):
    """ctypes calls below are mocks, not execution of Windows API code."""

    def native(self, dwm_status=0, client_success=True, screen_success=True):
        owner = self
        class User:
            @staticmethod
            def GetWindowRect(hwnd, out):
                owner.assertEqual(hwnd, 1234)
                out._obj.left, out._obj.top, out._obj.right, out._obj.bottom = (156, 156, 1612, 1045)
                return 1

            @staticmethod
            def GetClientRect(hwnd, out):
                out._obj.left, out._obj.top, out._obj.right, out._obj.bottom = (0, 0, 1440, 850)
                return client_success

            @staticmethod
            def ClientToScreen(hwnd, point):
                point._obj.x += 164
                point._obj.y += 187
                return screen_success

        class Dwm:
            @staticmethod
            def DwmGetWindowAttribute(hwnd, attribute, out, size):
                owner.assertEqual(hwnd, 1234)
                owner.assertEqual(attribute, 9)
                owner.assertEqual(size, ctypes.sizeof(capture_windows.w.RECT))
                out._obj.left, out._obj.top, out._obj.right, out._obj.bottom = (163, 156, 1605, 1038)
                return dwm_status

        instance = object.__new__(capture_windows.NativeWindows)
        instance.user, instance.dwm, instance.dwm_load_error = User(), Dwm(), None
        return instance

    def test_separate_outer_frame_and_screen_client_queries(self):
        geometry = self.native().window_geometry({"hwnd": 1234})
        self.assertEqual(geometry["outer_rect"], [156, 156, 1612, 1045])
        self.assertEqual(geometry["visible_frame_rect"], [163, 156, 1605, 1038])
        self.assertEqual(geometry["client_screen_rect"], [164, 187, 1604, 1037])
        self.assertEqual(geometry["dwm_hresult"], 0)
        self.assertIs(geometry["client_query_succeeded"], True)
        self.assertEqual(capture_windows.capture_rectangle(geometry, NativeCaptureBoundary.display()),
                         [163, 156, 1605, 1038])

    def test_dwm_error_is_recorded_without_using_written_output(self):
        geometry = self.native(dwm_status=-2147024891).window_geometry({"hwnd": 1234})
        self.assertEqual(geometry["dwm_hresult"], -2147024891)
        self.assertIsNone(geometry["visible_frame_rect"])
        with self.assertRaisesRegex(RuntimeError, "DWM"):
            capture_windows.capture_rectangle(geometry, NativeCaptureBoundary.display())

    def test_dwm_unavailable_is_recorded_without_fallback(self):
        native = self.native()
        native.dwm = None
        native.dwm_load_error = "mock unavailable library"
        geometry = native.window_geometry({"hwnd": 1234})
        self.assertIsNone(geometry["visible_frame_rect"])
        self.assertEqual(geometry["dwm_load_error"], "mock unavailable library")
        with self.assertRaisesRegex(RuntimeError, "DWM"):
            capture_windows.capture_rectangle(geometry, NativeCaptureBoundary.display())

    def test_failed_getclientrect_is_recorded_without_fallback(self):
        geometry = self.native(client_success=False).window_geometry({"hwnd": 1234})
        self.assertFalse(geometry["client_query_succeeded"])
        self.assertIsNone(geometry["client_screen_rect"])

    def test_failed_clienttoscreen_is_recorded_without_fallback(self):
        geometry = self.native(screen_success=False).window_geometry({"hwnd": 1234})
        self.assertFalse(geometry["client_query_succeeded"])
        self.assertIsNone(geometry["client_screen_rect"])


class MockDpiContext(unittest.TestCase):
    def native(self, awareness=2):
        class User:
            calls = []

            def SetThreadDpiAwarenessContext(self, value):
                self.calls.append(value)
                return 99

            @staticmethod
            def GetThreadDpiAwarenessContext():
                return 100

            @staticmethod
            def GetAwarenessFromDpiAwarenessContext(context):
                return awareness

        native = object.__new__(capture_windows.NativeWindows)
        native.user = User()
        return native

    def test_thread_dpi_context_restored_after_success(self):
        native = self.native()
        with native.physical_coordinates():
            self.assertEqual(len(native.user.calls), 1)
        self.assertEqual(len(native.user.calls), 2)
        self.assertEqual(native.user.calls[-1], 99)

    def test_thread_dpi_context_restored_after_exception(self):
        native = self.native()
        with self.assertRaisesRegex(ValueError, "test"):
            with native.physical_coordinates():
                raise ValueError("test")
        self.assertEqual(native.user.calls[-1], 99)

    def test_wrong_dpi_context_fails_and_restores(self):
        native = self.native(awareness=1)
        with self.assertRaisesRegex(RuntimeError, "per-monitor"):
            with native.physical_coordinates():
                self.fail("Must not run a capture in virtualized coordinates")
        self.assertEqual(native.user.calls[-1], 99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
