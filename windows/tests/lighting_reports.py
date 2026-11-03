"""Snapshot, missing-data, numerical and HTML safety checks for FEED lighting."""

import copy
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from facility_studio.errors import ValidationError
from facility_studio.html_report import html_report
from facility_studio.lighting_report import CONTEXT_FIELDS, report_data
from facility_studio.simple_engines import calculate_tool, lighting
from facility_studio.simple_reports import tool_report
from facility_studio.simple_schema import defaults


def result(**changes):
    return calculate_tool("lighting", dict(defaults("lighting"), **changes))


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class LightingReports(unittest.TestCase):
    def test_preserves_lumen_method_and_reports_real_totals(self):
        r = result()
        data = report_data(r)
        self.assertEqual((r["quantity"], data["average_lux"]), (10, 640))
        self.assertEqual(data["total_luminaire_flux_lm"], 40000)
        self.assertAlmostEqual(data["power_density_w_m2"], 400 / 30)
        self.assertAlmostEqual(data["power_density_per_100_lux"], (400 / 30) / 6.4)

    def test_normalized_density_uses_rounded_actual_not_target(self):
        r = result(mode="反算燈數", target="500")
        self.assertEqual(r["illuminance_lux"], 512)
        self.assertAlmostEqual(report_data(r)["power_density_per_100_lux"], 320 / 30 * 100 / 512)

    def test_unknown_metrics_remain_none_in_all_modes(self):
        for changes in ({}, {"quantity": "0"}, {"mode": "反算燈數", "target": "0"},
                        {"watts": "0"}, {"watts": "0", "lumen_mode": "燈具型錄流明"}):
            with self.subTest(changes=changes):
                r = result(**changes)
                data = report_data(r)
                for key in ("minimum_lux", "maximum_lux", "uniformity_min_avg", "uniformity_min_max",
                            "direct_lux", "reflected_lux", "grid", "isolux", "ugr", "lamp_flux_lm"):
                    self.assertIsNone(data[key], key)
                self.assertEqual(data["power_density_per_100_lux"] is None, r["illuminance_lux"] == 0)
                for language in ("zh-Hant", "en"):
                    self.assertIsNone(re.search(r"\b(?:nan|inf)\b", str(html_report(r, language=language)), re.I))

    def test_geometry_never_uses_hidden_drafts(self):
        r = result(length="bad", width="999", height="bad", mount_h="bad", work_h="bad")
        self.assertIsNone(r["length_m"])
        self.assertIsNone(r["width_m"])
        self.assertIsNone(r["room_height_m"])
        self.assertIsNone(r["mount_h_m"])
        actual = result(area_mode="長×寬", length="8.8", width="6.55",
                        u_mode="型錄 U＋室指數 K 檢核", mount_h="3", work_h="1")
        self.assertAlmostEqual(actual["area_m2"], 57.64)
        self.assertEqual((actual["length_m"], actual["width_m"], actual["work_h_m"]), (8.8, 6.55, 1))

    def test_snapshot_not_supplied_drafts_and_no_mutation(self):
        r = result(report_project="Adopted Project", report_room="Adopted Room")
        before = copy.deepcopy(r)
        for language in ("zh-Hant", "en"):
            txt = tool_report(r, dict(defaults("lighting"), area="99999", report_project="DRAFT PROJECT"), language=language)
            self.assertIn("Adopted Project", txt)
            self.assertNotIn("DRAFT PROJECT", txt)
            self.assertNotIn("99999", txt)
            html_report(r, language=language)
        self.assertEqual(r, before)

    def test_all_metadata_escaped_and_verbatim_in_both_languages(self):
        payload = '</title><script>alert(1)</script><img src=x onerror="boom"> 照明 & <demo>'
        for key, _ in CONTEXT_FIELDS:
            r = result(**{key: payload})
            for language in ("zh-Hant", "en"):
                text = str(html_report(r, language=language))
                parser = Tags()
                parser.feed(text)
                self.assertFalse(any(tag in ("script", "img") for tag, _ in parser.tags))
                self.assertNotIn('<script>', text)
                self.assertIn(payload, unescape(text))
                self.assertIn(payload, tool_report(r, {}, language=language))

    def test_empty_legacy_direct_and_pipeline_results(self):
        r = result()
        del r["report_context"]
        del r["length_m"]
        del r["width_m"]
        self.assertIn("未提供", html_report(r))
        direct = lighting(defaults("lighting"))
        self.assertIn("採用輸入條件未附", html_report(direct))
        legacy = dict(r)
        legacy.pop("adopted_inputs")
        for snapshot in (direct, legacy):
            draft = dict(defaults("lighting"), area="99999", report_project="DRAFT PROJECT")
            txt = tool_report(snapshot, draft)
            self.assertNotIn("99999", txt)
            self.assertNotIn("DRAFT PROJECT", txt)
            self.assertIn("採用輸入條件未附", txt)
        for language in ("zh-Hant", "en"):
            pipeline = html_report({"pipeline": {"lighting": r}}, language=language)
            self.assertIn("Emin/Eavg", pipeline)
            self.assertIn("Not calculated" if language == "en" else "未計算", pipeline)

    def test_combined_report_uses_lighting_snapshot_not_pipeline_draft(self):
        r = result(report_project="Adopted Project", area="30")
        draft = dict(defaults("lighting"), area="99999", report_project="DRAFT PROJECT")
        for language in ("zh-Hant", "en"):
            report = html_report({"pipeline": {"lighting": r, "adopted_inputs": {"lighting": draft}}}, language=language)
            self.assertIn("Adopted Project", report)
            self.assertNotIn("DRAFT PROJECT", report)
            self.assertNotIn("99999", report)
            old = dict(r)
            old.pop("adopted_inputs")
            report = html_report({"pipeline": {"lighting": old, "adopted_inputs": {"lighting": draft}}}, language=language)
            self.assertNotIn("DRAFT PROJECT", report)
            self.assertNotIn("99999", report)
            self.assertIn("Adopted input conditions" if language == "en" else "採用輸入條件未附", report)

    def test_authored_english_and_a4_portrait(self):
        r = result()
        for output in (html_report(r, language="en"), tool_report(r, {}, language="en")):
            self.assertIsNone(re.search(r"[\u3400-\u9fff]", output))
        self.assertIn("size:A4 portrait", html_report(r))

    def test_metadata_validation_and_unchanged_engineering(self):
        base = result()
        for text in ("", "x" * 500, "設備 甲\n" * 70):
            r = result(report_project=text)
            self.assertEqual(r["illuminance_lux"], base["illuminance_lux"])
        for bad in ("x" * 501, {}, None):
            with self.assertRaises(ValidationError):
                result(report_project=bad)
        for key in ("illuminance_lux", "area_m2"):
            for bad in (float("nan"), float("inf"), -1):
                with self.assertRaises(ValueError):
                    report_data(dict(base, **{key: bad}))

    def test_export_default_cancel_repeat_and_changed_dialog(self):
        # Production export method with display-only stubs, not native GUI QA.
        from facility_studio.simple_desktop import SimpleToolsApp

        data = dict(defaults("lighting"), report_project="Stable")
        page = SimpleNamespace(result=calculate_tool("lighting", data), data=lambda: dict(data),
                               calculate=lambda: None, upstream_stale=False,
                               banner=SimpleNamespace(show=lambda *args: None))
        app = SimpleToolsApp.__new__(SimpleToolsApp)
        app.current = "lighting"
        app.root = None
        app.active_page = lambda: page
        app.footer_text = SimpleNamespace(configure=lambda **kwargs: None)
        with patch("facility_studio.simple_desktop.filedialog.asksaveasfilename", return_value="") as dialog:
            self.assertFalse(app.export_result())
            self.assertEqual(dialog.call_args.kwargs["defaultextension"], ".html")
            self.assertEqual(dialog.call_args.kwargs["filetypes"][0][1], "*.html")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lighting.html"
            for _ in range(2):
                self.assertTrue(app.export_result(str(path)))
                self.assertIn("Stable", path.read_text())
            before = path.read_bytes()

            def change_during_dialog(**kwargs):
                data["report_project"] = "New draft"
                return str(path)

            with patch("facility_studio.simple_desktop.filedialog.asksaveasfilename", side_effect=change_during_dialog):
                self.assertFalse(app.export_result())
            self.assertEqual(path.read_bytes(), before)
            page.result = None
            self.assertFalse(app.export_result(str(path)))


if __name__ == "__main__":
    unittest.main()
