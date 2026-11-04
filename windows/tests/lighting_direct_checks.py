"""Independent analytic fixtures for direct-only lighting and export guards."""
import copy
import csv
from html import unescape
from html.parser import HTMLParser
import io
import json
import math
import os
from pathlib import Path
import re
import random
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from photometry_formats import ies, ldt
from facility_studio.photometry import parse_photometry
from facility_studio.lighting_direct import calculate_direct, point_illuminance, contour_segments
from facility_studio.lighting_direct_report import direct_html, grid_csv, plan_svg
from facility_studio.lighting_layout_ui import DirectLightingWindow, parse_scene, regular_schedule


def constant(value=100):
    return parse_photometry(ies(rows=[[value, value]]), "ies", "synthetic.ies")


def fixture(**kwargs):
    return dict(dict(photometry="P1", x_m=2, y_m=2, z_m=3, yaw_deg=0, multiplier=1), **kwargs)


def scene(**kwargs):
    return dict(dict(length_m=4, width_m=4, workplane_m=1, edge_m=0,
                     nx=10, ny=10, maintenance=.8, fixtures=[fixture()]), **kwargs)


class ParsedTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class DirectLightingChecks(unittest.TestCase):
    def test_nadir_inverse_square_and_oblique_cosine(self):
        p = constant()
        self.assertEqual(point_illuminance(p, fixture(), 2, 2, 1), 25)
        self.assertEqual(point_illuminance(p, fixture(z_m=5), 2, 2, 1), 6.25)
        # x offset 1, y offset 2, height 2 gives distance=3; cos=2/3.
        self.assertAlmostEqual(point_illuminance(p, fixture(), 3, 4, 1), 100 * (2 / 3) / 9)

    def test_random_rays_and_uniform_geometry_scaling(self):
        rng = random.Random(20261103)
        p = constant()
        for _ in range(100):
            x, y, height = rng.uniform(-10, 10), rng.uniform(-10, 10), rng.uniform(.1, 20)
            f = fixture(x_m=0, y_m=0, z_m=height)
            distance = math.sqrt(x*x + y*y + height*height)
            expected = 100 / (distance*distance) * (height/distance)
            self.assertAlmostEqual(point_illuminance(p, f, x, y, 0), expected, places=10)
        base = calculate_direct({"P1": p}, scene(maintenance=1))
        scaled = scene(length_m=8, width_m=8, workplane_m=2, fixtures=[fixture(x_m=4,y_m=4,z_m=6)], maintenance=1)
        bigger = calculate_direct({"P1": p}, scaled)
        for a, b in zip(sum(base["grid"]["lux"], []), sum(bigger["grid"]["lux"], [])):
            self.assertAlmostEqual(a, 4*b)
        self.assertAlmostEqual(base["summary"]["uniformity_min_avg"], bigger["summary"]["uniformity_min_avg"])

    def test_asymmetric_file_c0_yaw_and_cardinal_axes(self):
        p = parse_photometry(ies(c=(0, 90, 180, 270, 360), g=(0, 45, 90),
                                 rows=[[100, x, x] for x in (100, 200, 300, 400, 100)]), "ies")
        factor = (2 / math.sqrt(8)) / 8
        for x, y, intensity in ((4, 2, 100), (2, 4, 200), (0, 2, 300), (2, 0, 400)):
            self.assertAlmostEqual(point_illuminance(p, fixture(), x, y, 1), intensity * factor)
        self.assertAlmostEqual(point_illuminance(p, fixture(yaw_deg=90), 4, 2, 1), 400 * factor)
        self.assertAlmostEqual(point_illuminance(p, fixture(yaw_deg=90), 2, 4, 1), 100 * factor)

    def test_1995_c90_c270_direct_axes_yaw_and_export_provenance(self):
        p = parse_photometry(ies(c=(90, 180, 270), g=(0, 45, 90),
                                 rows=[[100, x, x] for x in (200, 300, 400)],
                                 version='1995'), 'ies', 'synthetic-1995.ies')
        factor = (2 / math.sqrt(8)) / 8
        for x, y, intensity in ((4, 2, 300), (2, 4, 200), (0, 2, 300), (2, 0, 400)):
            self.assertAlmostEqual(point_illuminance(p, fixture(), x, y, 1), intensity * factor)
        self.assertAlmostEqual(point_illuminance(p, fixture(yaw_deg=90), 4, 2, 1), 400 * factor)
        self.assertAlmostEqual(point_illuminance(p, fixture(yaw_deg=90), 2, 4, 1), 300 * factor)
        result = calculate_direct({'P1': p}, scene())
        exported = json.loads(json.dumps(result, allow_nan=False))
        self.assertEqual(exported['sources']['P1']['source_sha256'], p.source_sha256)
        self.assertEqual(exported['sources']['P1']['metadata']['source_c_angles_deg'], [90, 180, 270])
        self.assertEqual(exported['sources']['P1']['metadata']['symmetry_plane'], 'C90-C270')
        self.assertIn(p.source_sha256, direct_html(result))
        self.assertGreater(len(grid_csv(result)), 100)

    def test_1995_c90_c270_import_controller_repeats_cancel_and_invalid_file(self):
        # Exercise the real import controller without requiring a display.
        obj = DirectLightingWindow.__new__(DirectLightingWindow)
        obj.win = None
        obj.sources, obj.next_source_id = {}, 1
        obj.source_tree, obj.source_choice, obj.invalidate = Mock(), Mock(), Mock()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'synthetic-1995.ies'
            text = ies(c=(90, 180, 270), rows=[[100, x] for x in (10, 30, 70)], version='1995')
            path.write_text(text, encoding='utf-8')
            with patch('facility_studio.lighting_layout_ui.filedialog.askopenfilename', return_value=str(path)):
                obj.import_source()
                source = obj.sources['P1']
                obj.import_source()
                self.assertEqual(obj.sources, {'P1': source})
                self.assertEqual(obj.next_source_id, 2)
                obj.source_tree.insert.assert_called_once()
                path.write_text(text.replace('1995', '2002'), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'LM-63-1995'):
                    obj.import_source()
                self.assertEqual(obj.sources, {'P1': source})
                self.assertEqual(obj.next_source_id, 2)
            obj.invalidate.reset_mock()
            with patch('facility_studio.lighting_layout_ui.filedialog.askopenfilename', return_value=''):
                obj.import_source()
            obj.invalidate.assert_not_called()
            self.assertEqual(obj.sources, {'P1': source})

    def test_additivity_multiplier_and_maintenance_once(self):
        single = calculate_direct({"P1": constant()}, scene(maintenance=1))
        double = calculate_direct({"P1": constant()}, scene(fixtures=[fixture(), fixture()], maintenance=.8))
        dimmed = calculate_direct({"P1": constant()}, scene(fixtures=[fixture(multiplier=.25)], maintenance=.4))
        for a, b, c in zip(sum(single["grid"]["lux"], []), sum(double["grid"]["lux"], []), sum(dimmed["grid"]["lux"], [])):
            self.assertAlmostEqual(b, 1.6 * a)
            self.assertAlmostEqual(c, .1 * a)

    def test_grid_coordinates_summary_and_independent_equation(self):
        r = calculate_direct({"P1": constant()}, scene(nx=4, ny=2, edge_m=.2))
        self.assertEqual(r["grid"]["sampling"], "uniform_cell_centres")
        self.assertAlmostEqual(r["grid"]["x_m"][0], .65)
        self.assertAlmostEqual(r["grid"]["y_m"][0], 1.1)
        expected = [100 * 2 / ((x - 2) ** 2 + (y - 2) ** 2 + 4) ** 1.5 * .8
                    for y in r["grid"]["y_m"] for x in r["grid"]["x_m"]]
        self.assertEqual(r["summary"]["average_lux"], math.fsum(expected) / len(expected))
        self.assertEqual(r["summary"]["minimum_lux"], min(expected))
        self.assertEqual(r["summary"]["maximum_lux"], max(expected))
        self.assertAlmostEqual(r["summary"]["uniformity_min_avg"], min(expected) / (sum(expected) / len(expected)))

    def test_grid_converges_to_independent_rectangle_solid_angle(self):
        # Exact integral of I*h/r^3 over a centred rectangle is I*solid-angle.
        a, b, h, intensity = 2, 2, 2, 100
        exact = intensity * 4 * math.atan(a * b / (h * math.sqrt(h*h + a*a + b*b))) / (4*a*b)
        coarse = calculate_direct({"P1": constant()}, scene(nx=4, ny=4, maintenance=1))["summary"]["average_lux"]
        fine = calculate_direct({"P1": constant()}, scene(nx=80, ny=80, maintenance=1))["summary"]["average_lux"]
        self.assertLess(abs(fine - exact), abs(coarse - exact))
        self.assertAlmostEqual(fine / exact, 1, delta=.0001)

    def test_ldt_relative_and_absolute_have_correct_direct_scale(self):
        for lamps in (-1, 4):
            p = parse_photometry(ldt(lamps=lamps, flux=2000, factor=.5, lor=50), "ldt")
            self.assertEqual(point_illuminance(p, fixture(), 2, 2, 1), 125)

    def test_ldt_asymmetric_c90_lobe_rotates_to_negative_x(self):
        p = parse_photometry(ldt(sym=0, rows=[[100, x, x] for x in (10, 20, 30, 40)]), "ldt")
        expected = 20 * (2 / math.sqrt(8)) / 8
        self.assertAlmostEqual(point_illuminance(p, fixture(), 2, 4, 1), expected)
        self.assertAlmostEqual(point_illuminance(p, fixture(yaw_deg=90), 0, 2, 1), expected)

    def test_missing_lower_hemisphere_no_reflected_fake_light(self):
        p = parse_photometry(ies(g=(90, 180)), "ies")
        r = calculate_direct({"P1": p}, scene())
        self.assertEqual(r["summary"]["maximum_lux"], 0)
        self.assertIsNone(r["reflected_lux"])
        self.assertIsNone(r["ugr"])
        self.assertIsNone(r["summary"]["uniformity_min_avg"])

    def test_zero_maintenance_or_multiplier_preserves_initial_distinction(self):
        r = calculate_direct({"P1": constant()}, scene(maintenance=0))
        self.assertGreater(r["summary"]["initial_average_lux"], 0)
        self.assertEqual(r["summary"]["average_lux"], 0)
        self.assertIsNone(r["summary"]["uniformity_min_max"])
        r = calculate_direct({"P1": constant()}, scene(fixtures=[fixture(multiplier=0)]))
        self.assertEqual(r["summary"]["initial_average_lux"], 0)
        self.assertIn("zero illuminance", direct_html(r, language="en"))

    def test_snapshots_are_independent_and_trace_sources(self):
        original = scene()
        p = constant()
        r = calculate_direct({"P1": p}, original)
        saved = copy.deepcopy(r)
        original["fixtures"][0]["x_m"] = 999
        original["maintenance"] = .1
        self.assertEqual(r, saved)
        self.assertEqual(r["sources"]["P1"]["source_sha256"], p.source_sha256)
        self.assertIn("file C0", r["sources"]["P1"]["metadata"].values())
        json.dumps(r, allow_nan=False)

    def test_invalid_scenes_and_unsupported_orientation_rejected(self):
        with patch("facility_studio.lighting_direct.MAX_TOTAL_PHOTOMETRIC_SAMPLES", 3), self.assertRaises(ValueError):
            calculate_direct({"P1": constant()}, scene())
        for changes in ({"length_m": 0}, {"width_m": float("nan")}, {"workplane_m": -1},
                        {"nx": True}, {"nx": 2.2}, {"nx": 81}, {"ny": 1}, {"edge_m": 2},
                        {"maintenance": 1.1}, {"fixtures": []}, {"fixtures": [fixture()] * 201},
                        {"utilization": .6}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                calculate_direct({"P1": constant()}, scene(**changes))
        for changes in ({"x_m": -1}, {"y_m": 5}, {"z_m": 1}, {"z_m": 1.009},
                        {"multiplier": 1.1}, {"yaw_deg": float("inf")},
                        {"photometry": "absent"}, {"tilt_deg": 10}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                calculate_direct({"P1": constant()}, scene(fixtures=[fixture(**changes)]))

    def test_near_field_warns_without_claiming_far_field_certification(self):
        p = parse_photometry(ies(width=2, length=3), "ies")
        r = calculate_direct({"P1": p}, scene())
        self.assertTrue(any("Far-field" in message for message in r["warnings"]))
        self.assertTrue(any("point-source" in message for message in r["limitations"]))

    def test_zero_size_photometry_does_not_certify_near_field_accuracy(self):
        p = parse_photometry(ies(width=0, length=0, height=0), "ies")
        r = calculate_direct({"P1": p}, scene())
        self.assertGreater(r["summary"]["average_lux"], 0)
        self.assertTrue(any("zero luminaire dimensions" in message for message in r["warnings"]))
        self.assertTrue(any("numerical clearance is not an accuracy guarantee" in message for message in r["limitations"]))
        for language in ("zh-Hant", "en"):
            self.assertIn("far-field distance validity", direct_html(r, language=language))

    def test_contour_interpolation_stays_inside_sample_hull(self):
        r = {"grid": {"x_m": [1, 2], "y_m": [3, 4], "lux": [[0, 10], [0, 10]]}}
        segments = contour_segments(r, [5])[5]
        self.assertEqual(len(segments), 2)
        for line in segments:
            for x, y in line:
                self.assertEqual(x, 1.5)
                self.assertTrue(3 <= y <= 4)
        self.assertEqual(contour_segments(r, [20])[20], [])
        r["grid"]["lux"] = [[5, 5], [5, 5]]
        self.assertEqual(contour_segments(r, [5])[5], [])

    def test_csv_preserves_full_grid_and_initial_maintained_values(self):
        r = calculate_direct({"P1": constant()}, scene(nx=3, ny=4))
        rows = list(csv.DictReader(io.StringIO(grid_csv(r))))
        self.assertEqual(len(rows), 12)
        for row in rows:
            self.assertAlmostEqual(float(row["direct_maintained_lux"]), float(row["direct_initial_lux"]) * .8, places=9)

    def test_report_source_injection_and_authored_english(self):
        p = parse_photometry(ies().replace("Test lamp", '</title><script>boom</script>照明&'), "ies", '<img src=x onerror="boom">.ies')
        r = calculate_direct({"P1": p}, scene(nx=3, ny=3))
        for language in ("zh-Hant", "en"):
            text = str(direct_html(r, language=language))
            tags = ParsedTags(); tags.feed(text)
            self.assertFalse(any(tag in ("script", "img") for tag, _ in tags.tags))
            self.assertIn(p.source_name, unescape(text))
            self.assertIn(p.luminaire, unescape(text))
            self.assertIn(p.source_sha256, text)
        plain = direct_html(calculate_direct({"P1": constant()}, scene(nx=2, ny=2)), language="en")
        self.assertIsNone(re.search(r"[\u3400-\u9fff]", plain))
        self.assertIn("size:A4 portrait", plain)
        self.assertIn("<svg", plain)

    def test_svg_numeric_layout_and_no_fake_uniformity_at_zero(self):
        r = calculate_direct({"P1": constant()}, scene(maintenance=0))
        svg = plan_svg(r)
        self.assertIsNone(re.search(r"\b(?:nan|inf)\b", svg, re.I))
        self.assertIn("0.00 lx", svg)

    def test_ui_helpers_and_export_guards(self):
        fields = {key: str(value) for key, value in scene().items() if key != "fixtures"}
        schedule = regular_schedule(fields, "P1", "2", "3", "3", ["P1"])
        adopted = parse_scene(fields, schedule, ["P1"])
        self.assertEqual(len(adopted["fixtures"]), 6)
        r = calculate_direct({"P1": constant()}, adopted)
        class Variable:
            def __init__(self, value): self.value = value
            def get(self): return self.value
            def set(self, value): self.value = value
        obj = DirectLightingWindow.__new__(DirectLightingWindow)
        obj.win = None
        obj.variables = {key: Variable(value) for key, value in fields.items()}
        obj.generator_vars = {}
        obj.schedule = SimpleNamespace(get=lambda *args: schedule)
        obj.sources = {"P1": constant()}
        obj.status = Variable("")
        obj.result = r
        obj.result_fingerprint = obj.fingerprint()
        with patch("facility_studio.lighting_layout_ui.filedialog.asksaveasfilename", return_value=""):
            obj.export("html")
            self.assertIs(obj.result, r)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.html"
            for _ in range(2):
                with patch("facility_studio.lighting_layout_ui.filedialog.asksaveasfilename", return_value=str(path)):
                    obj.export("html")
                self.assertIn("<svg", path.read_text(encoding="utf-8"))
            before = path.read_bytes()
            def change(**kwargs):
                obj.variables["length_m"].set("99")
                return str(path)
            with patch("facility_studio.lighting_layout_ui.filedialog.asksaveasfilename", side_effect=change), self.assertRaises(ValueError):
                obj.export("html")
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(ValueError): obj.export("csv")

    def test_export_rechecks_source_and_result_identity_after_dialog(self):
        fields = {key: str(value) for key, value in scene().items() if key != "fixtures"}
        schedule = regular_schedule(fields, "P1", "1", "1", "3", ["P1"])
        obj = DirectLightingWindow.__new__(DirectLightingWindow)
        obj.win = None
        obj.variables = {key: SimpleNamespace(get=lambda value=value: value) for key, value in fields.items()}
        obj.generator_vars = {}
        obj.schedule = SimpleNamespace(get=lambda *args: schedule)
        obj.status = SimpleNamespace(set=lambda value: None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "existing.html"
            path.write_text("preserve existing report", encoding="utf-8")
            for change in ("replace_source", "add_unused_source", "replace_result", "remove_source"):
                obj.sources = {"P1": constant()}
                obj.result = calculate_direct(obj.sources, parse_scene(fields, schedule, obj.sources))
                obj.result_fingerprint = obj.fingerprint()
                def mutate(**kwargs):
                    if change == "replace_source": obj.sources["P1"] = constant(200)
                    elif change == "add_unused_source": obj.sources["P2"] = constant(200)
                    elif change == "replace_result": obj.result = copy.deepcopy(obj.result)
                    else: obj.sources.pop("P1")
                    return str(path)
                with self.subTest(change=change), patch("facility_studio.lighting_layout_ui.filedialog.asksaveasfilename", side_effect=mutate), self.assertRaises(ValueError):
                    obj.export("html")
                self.assertEqual(path.read_text(encoding="utf-8"), "preserve existing report")

    def test_failed_atomic_export_preserves_existing_report(self):
        fields = {key: str(value) for key, value in scene().items() if key != "fixtures"}
        schedule = regular_schedule(fields, "P1", "1", "1", "3", ["P1"])
        obj = DirectLightingWindow.__new__(DirectLightingWindow)
        obj.win = None
        obj.variables = {key: SimpleNamespace(get=lambda value=value: value) for key, value in fields.items()}
        obj.generator_vars = {}
        obj.schedule = SimpleNamespace(get=lambda *args: schedule)
        obj.status = SimpleNamespace(set=lambda value: None)
        obj.sources = {"P1": constant()}
        obj.result = calculate_direct(obj.sources, parse_scene(fields, schedule, obj.sources))
        obj.result_fingerprint = obj.fingerprint()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "existing.json"
            path.write_text("preserve existing report", encoding="utf-8")
            with patch("facility_studio.lighting_layout_ui.filedialog.asksaveasfilename", return_value=str(path)), patch("facility_studio.utils.os.replace", side_effect=OSError("simulated interrupted export")), self.assertRaises(OSError):
                obj.export("json")
            self.assertEqual(path.read_text(encoding="utf-8"), "preserve existing report")
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    @unittest.skipUnless(os.environ.get("FACILITY_DIRECT_GUI") == "1", "Native Tk check requires an explicit display-enabled run")
    def test_native_1995_c90_c270_import_calculate_and_export(self):
        from facility_studio.localized_tk import tk
        root = tk.Tk()
        root.withdraw()
        try:
            window = DirectLightingWindow(root)
            with tempfile.TemporaryDirectory() as folder:
                source = Path(folder)/'synthetic-1995.ies'
                source.write_text(ies(c=(90, 180, 270), rows=[[100, x] for x in (10, 30, 70)], version='1995'), encoding='utf-8')
                with patch('facility_studio.lighting_layout_ui.filedialog.askopenfilename', return_value=str(source)):
                    window.import_source()
                    window.import_source()
                self.assertEqual(len(window.sources), 1)
                self.assertEqual(window.sources['P1'].metadata['symmetry_plane'], 'C90-C270')
                for key, value in scene().items():
                    if key != 'fixtures':
                        window.variables[key].set(str(value))
                window.schedule.insert('1.0', 'ID,x,y,z,yaw,scale\nP1,2,2,3,0,1\n')
                root.update()
                window.calculate()
                root.update()
                self.assertGreater(window.result['summary']['average_lux'], 0)
                for extension in ('json', 'csv', 'html'):
                    target = Path(folder)/('result.'+extension)
                    with patch('facility_studio.lighting_layout_ui.filedialog.asksaveasfilename', return_value=str(target)):
                        window.export(extension)
                    self.assertGreater(target.stat().st_size, 0)
                data = json.loads((Path(folder)/'result.json').read_text(encoding='utf-8'))
                self.assertEqual(data['sources']['P1']['metadata']['symmetry_plane'], 'C90-C270')
            window.win.destroy()
        finally:
            root.destroy()

    @unittest.skipUnless(os.environ.get("FACILITY_DIRECT_GUI") == "1", "Native Tk check requires an explicit display-enabled run")
    def test_native_window_import_edit_calculate_repeat_and_export(self):
        from facility_studio.localized_tk import tk
        from facility_studio.simple_desktop import SimplePage
        root = tk.Tk()
        root.withdraw()
        host = SimpleNamespace(winfo_toplevel=lambda: root)
        try:
            window = SimplePage.open_direct_lighting(host)
            self.assertIs(SimplePage.open_direct_lighting(host), window)
            with tempfile.TemporaryDirectory() as tmp:
                file = Path(tmp) / "source.ies"; file.write_text(ies(), encoding="utf-8")
                with patch("facility_studio.lighting_layout_ui.filedialog.askopenfilename", return_value=str(file)):
                    window.import_source(); window.import_source()
                self.assertEqual(len(window.sources), 1)
                for key, value in scene().items():
                    if key != "fixtures": window.variables[key].set(str(value))
                for key, value in {"source": "P1", "rows": "2", "cols": "2", "height": "3"}.items():
                    window.generator_vars[key].set(value)
                window.generate(); root.update()
                for _ in range(2):
                    window.calculate(); root.update()
                    self.assertIsNotNone(window.result)
                path = Path(tmp) / "report.html"
                with patch("facility_studio.lighting_layout_ui.filedialog.asksaveasfilename", return_value=str(path)):
                    window.export("html")
                self.assertIn("<svg", path.read_text(encoding="utf-8"))
                adopted = window.result
                with patch("facility_studio.lighting_layout_ui.filedialog.askopenfilename", return_value=""):
                    window.import_source()
                self.assertIs(window.result, adopted)
                window.variables["length_m"].set("9"); root.update()
                self.assertIsNone(window.result)
                window.calculate(); root.update()
                window.schedule.insert("end", "bad"); root.update()
                self.assertIsNone(window.result)
                with self.assertRaises(ValueError): window.calculate()
                window.generate(); root.update(); window.calculate(); root.update()
                window.source_tree.selection_set("P1"); window.remove_source(); root.update()
                self.assertIsNone(window.result)
                self.assertEqual(window.sources, {})
            window.win.destroy(); root.update()
            replacement = SimplePage.open_direct_lighting(host)
            self.assertIsNot(replacement, window)
            self.assertEqual(replacement.sources, {})
            replacement.win.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
