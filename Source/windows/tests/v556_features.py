"""V5.5.6 regressions using independent balances and real XLSX XML inputs."""

import copy
import json
import math
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.schema import default_project, V55_INPUT_KEYS
from facility_studio.engine import calculate, migrate_project, water_properties
from facility_studio.utils import project_hash
from facility_studio.workspace_store import new_workspace, validate_workspace
from facility_studio.contributions import empty_ledger, updated_ledger, removed_ledger, aggregate_ledger, ahu_contribution, equipment_contribution
from facility_studio.ahu_engine import nm_calculate
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.equipment_io import Cell, percentage_value, load_equipment, EquipmentImportError
from facility_studio.equipment_schema import example, SCHEMAS, SCHEMA_ID, SYSTEMS
from facility_studio.equipment_analysis import analyze_equipment, equipment_report
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_schema import defaults
from facility_studio.reports import report

CASES = []


def record(system, **changes):
    values = dict(example(system), enabled=1, **changes)
    return dict(system=system, row=6, cells={k: v if isinstance(v, Cell) else Cell(v) for k, v in values.items()})


def analyze(*rows):
    return analyze_equipment(dict(schema_id=SCHEMA_ID, source_name="test.xlsx", systems=SYSTEMS, records=list(rows)))


def water_entry(ident, summer=100., winter=10., supply=7., ret=12., rho=1000., circuit="CHW"):
    return dict(id=ident, name=ident, kind="AHU", source_hash=ident, updates={}, power={}, water=[dict(loop="CHW", circuit=circuit, supply=supply, **{"return": ret}, rho=rho, cp=4.1868, mu=.001, summer_lpm=summer, winter_lpm=winter)], notes=[], pending=[])


class Regression(unittest.TestCase):
    def mark(self, name):
        CASES.append(name)

    def close(self, actual, expected):
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9), (actual, expected))

    def test_percentage_records(self):
        samples = [("numeric50", Cell(50), 50), ("general-half", Cell(.5, numeric=True), .5), ("excel-half", Cell(.5, number_format="0%", numeric=True), 50), ("excel-decimals", Cell(.375, number_format="0.00%", numeric=True), 37.5), ("text", Cell("50%"), 50), ("fullwidth", Cell("50％"), 50), ("quoted-percent", Cell(.5, number_format='0.0"%"', numeric=True), .5), ("escaped-percent", Cell(.5, number_format=r"0.0\%", numeric=True), .5), ("section", Cell(.5, number_format='[>=1]0%;0.0', numeric=True), .5), ("section-match", Cell(.5, number_format='[<1]0%;0.0', numeric=True), 50), ("zero", Cell(0, number_format='0%;0%;0.0', numeric=True), 0)]
        for name, cell, expected in samples:
            with self.subTest(name=name):
                self.mark("percentage-" + name)
                result = analyze(record("電力", power=10, quantity=2, pf=1, usage=cell))
                self.close(result["totals"]["demand_kw"], 20 * expected / 100)
                equipment_report(result)
        for name, cell in [("formula", Cell(.5, formula=True, number_format="0%", numeric=True)), ("boolean", Cell(True, number_format="0%")), ("range", Cell(1.5, number_format="0%", numeric=True))]:
            self.mark("percentage-reject-" + name)
            with self.assertRaises(EquipmentImportError):
                analyze(record("電力", usage=cell))

    def test_real_xlsx_percentage(self):
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        source = ROOT / "facility_studio/resources/Equipment_Template.xlsx"
        with tempfile.TemporaryDirectory() as directory:
            for code, raw, expected in [("0%", ".5", 50), ("0.00%", ".125", 12.5), ('0.0"%"', ".5", .5), ("General", ".5", .5)]:
                self.mark("xlsx-" + code)
                destination = Path(directory) / "actual.xlsx"
                with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as output:
                    styles = ET.fromstring(original.read("xl/styles.xml"))
                    nums = styles.find(ns + "numFmts")
                    if nums is None:
                        nums = ET.SubElement(styles, ns + "numFmts")
                    fmt_id = max([163] + [int(n.get("numFmtId")) for n in nums]) + 1
                    ET.SubElement(nums, ns + "numFmt", numFmtId=str(fmt_id), formatCode=code)
                    nums.set("count", str(len(nums)))
                    xfs = styles.find(ns + "cellXfs")
                    index = len(xfs)
                    ET.SubElement(xfs, ns + "xf", numFmtId=str(fmt_id), applyNumberFormat="1")
                    xfs.set("count", str(len(xfs)))
                    for info in original.infolist():
                        content = original.read(info.filename)
                        if info.filename == "xl/styles.xml":
                            content = ET.tostring(styles)
                        if info.filename == "xl/worksheets/sheet2.xml":
                            xml = ET.fromstring(content)
                            row = next(r for r in xml.find(ns + "sheetData") if r.get("r") == "6")
                            values = dict(example("電力"), enabled=1, power=10, quantity=2, pf=1)
                            for col, spec in enumerate(SCHEMAS["電力"], 1):
                                address = chr(64 + col) + "6"
                                cell = next((c for c in row if c.get("r") == address), None)
                                if cell is None:
                                    cell = ET.SubElement(row, ns + "c", r=address)
                                cell.attrib.clear()
                                cell.set("r", address)
                                for child in list(cell):
                                    cell.remove(child)
                                value = values[spec["key"]]
                                if spec["key"] == "usage":
                                    cell.set("s", str(index))
                                    ET.SubElement(cell, ns + "v").text = raw
                                elif isinstance(value, (int, float)):
                                    ET.SubElement(cell, ns + "v").text = str(value)
                                else:
                                    cell.set("t", "inlineStr")
                                    ET.SubElement(ET.SubElement(cell, ns + "is"), ns + "t").text = str(value or "")
                            content = ET.tostring(xml)
                        output.writestr(info.filename, content)
                result = analyze_equipment(load_equipment(destination))
                self.close(result["totals"]["demand_kw"], 20 * expected / 100)
                if expected >= 1:
                    self.assertTrue(result["rows"][0]["normalizations"])

    def test_coincident_water_and_duplicate(self):
        self.mark("seasonal-coincident-not-sum-peaks")
        p = default_project()["inputs"]
        d, _, _ = updated_ledger(empty_ledger(), water_entry("A", 100, 10), p)
        d, u, s = updated_ledger(d, water_entry("B", 10, 100), p)
        self.close(float(u["chw_q"]), 110)
        self.close(s["water"][0]["winter_lpm"], 110)
        self.mark("same-id-idempotent")
        again, u2, _ = updated_ledger(d, water_entry("B", 10, 100), p)
        self.assertEqual(u, u2)
        self.assertEqual(len(again["entries"]), 2)
        self.mark("same-id-updates-only-one-source")
        d, u, _ = updated_ledger(d, water_entry("A", 200, 10), p)
        self.close(float(u["chw_q"]), 210)
        self.mark("remove-one-contribution")
        d, u, _ = removed_ledger(d, "A", p)
        self.close(float(u["chw_q"]), 100)

    def test_water_groups_and_selection(self):
        p = default_project()["inputs"]
        for name, changes in [("temperature", dict(supply=8, ret=13)), ("fluid", dict(rho=1100)), ("circuit", dict(circuit="second-service"))]:
            self.mark("separate-water-" + name)
            d, _, _ = updated_ledger(empty_ledger(), water_entry("A"), p)
            d, u, s = updated_ledger(d, water_entry("B", **changes), p)
            self.assertEqual(len(s["water"]), 2)
            self.assertNotIn("chw_q", u)
            self.assertTrue(s["pending"])
            self.mark("explicit-water-selection-" + name)
            d["selections"]["CHW"] = s["water"][1]["id"]
            s2 = aggregate_ledger(d, p)
            self.close(float(s2["updates"]["chw_q"]), 100)
            self.assertEqual(sum(g["adopted"] for g in s2["water"]), 1)

    def test_water_scope_and_old_project(self):
        p = default_project()
        before = calculate(p)
        self.mark("independent-chw-does-not-change-pcw-dccw-hw")
        p["inputs"].update(chw_fluid_mode="本迴路獨立物性", chw_rho="1100", chw_cp="3.5", chw_mu="0.002")
        after = calculate(p)
        for loop in ("PCW", "DCCW", "HW"):
            self.close(before["water"][loop]["lpm"], after["water"][loop]["lpm"])
            self.close(before["pressure"][loop]["total_pa"], after["pressure"][loop]["total_pa"])
        self.mark("legacy-custom-water-properties-preserved")
        old = default_project()
        old["schema_version"] = 9
        old["inputs"] = {k: v for k, v in old["inputs"].items() if k in V55_INPUT_KEYS}
        old["provenance"] = {k: v for k, v in old["provenance"].items() if k in V55_INPUT_KEYS}
        old["inputs"].update(water_rho="1100", water_cp="3.5", water_mu="0.002")
        migrated = migrate_project(old)
        self.close(water_properties(migrated["inputs"], "pcw")["cp"], 3.5)
        self.assertEqual(migrated["inputs"]["chw_cp"], "3.5")
        self.mark("workspace-v1-schema9-and-ab-migrate")
        legacy_result = calculate(migrated)
        legacy_result["project"] = old
        legacy_result["hash"] = project_hash(old)
        doc = new_workspace(default_project())
        doc["workspace_version"] = 1
        del doc["demand_ledger"]
        doc["main"] = old
        doc["comparisons"]["A"] = legacy_result
        loaded = validate_workspace(doc)
        self.assertEqual(loaded["workspace_version"], 2)
        self.assertIn("migration_note", loaded["comparisons"]["A"])
        self.mark("tampered-ab-hash-rejected")
        doc["comparisons"]["A"]["hash"] = "bad"
        with self.assertRaises(ValueError):
            validate_workspace(doc)

    def test_ahu_repeat_and_persistence(self):
        self.mark("actual-ahu-known-power-and-repeat")
        p = default_project()
        result = nm_calculate(NM_DEFAULTS)
        entry = ahu_contribution(result, "A", p["inputs"])
        d, updates, summary = updated_ledger(empty_ledger(), entry, p["inputs"])
        p["inputs"].update(updates)
        d2, updates2, _ = updated_ledger(d, entry, p["inputs"])
        self.close(float(updates2["e_np_heat"]), float(NM_DEFAULTS["h1_kw"]) + float(NM_DEFAULTS["h2_kw"]))
        self.assertTrue(summary["pending"])
        self.mark("ledger-save-load-round-trip")
        doc = new_workspace(p)
        doc["demand_ledger"] = d2
        loaded = validate_workspace(json.loads(json.dumps(doc)))
        self.assertEqual(loaded["demand_ledger"], d2)
        self.mark("remove-last-restores-adopted-original")
        _, restored, _ = removed_ledger(d2, "A", p["inputs"])
        self.assertEqual(restored["e_np_heat"], default_project()["inputs"]["e_np_heat"])
        self.mark("remove-last-preserves-manual-edits")
        p["inputs"]["e_np_heat"] = "22"
        _, restored, _ = removed_ledger(d2, "A", p["inputs"])
        self.assertNotIn("e_np_heat", restored)

    def test_workspace_report_ledger(self):
        self.mark("workspace-report-seasonal-flow-round-trip")
        p = default_project()
        d, u, _ = updated_ledger(empty_ledger(), water_entry("A"), p["inputs"])
        p["inputs"].update(u)
        d, u, _ = updated_ledger(d, water_entry("B", 10, 100), p["inputs"])
        p["inputs"].update(u)
        doc = new_workspace(p)
        doc["demand_ledger"] = d
        r = calculate(doc)
        self.close(r["water"]["CHW"]["lpm"], 110)
        self.close(r["demand_summary"]["water"][0]["design_lpm"], 110)
        text = str(report(r))
        self.assertIn("設計 110.00 LPM", text)
        self.assertIn("Σ夏季LPM", text)
        self.mark("missing-ledger-source-document-keeps-engineering-pending")
        self.assertTrue(any("來源快照" in q["name"] for q in r["quality"]["items"]))

    def test_existing_amp_panel_pf(self):
        self.mark("original-amp-load-retains-independent-panel-pf")
        p = default_project()
        p["inputs"].update(e_np_fan="0", e_np_heat="0", e_np_humid="0", e_np_exh="10", u_e_np_exh="A", e_np_pump="0", e_np_pf_mode="本盤獨立 PF", e_np_pf="0.5")
        original_kw = math.sqrt(3) * 380 * 10 * .5 / 1000
        source = dict(id="p", name="p", kind="設備表", source_hash="p", updates={"e_np_heat":"2", "u_e_np_heat":"kW"}, water=[], power={"NP":dict(kw=2.,kvar=0.,design_kw=2.,design_kvar=0.,branch_floor_a=0.,length_m=0.,voltage=380.)}, notes=[], pending=[])
        d, updates, _ = updated_ledger(empty_ledger(), source, p["inputs"])
        p["inputs"].update(updates)
        self.close(float(p["inputs"]["e_np_exh"]), original_kw)
        self.assertEqual(p["inputs"]["u_e_np_exh"], "kW")
        expected_kva = math.hypot(original_kw + 2, original_kw * math.sqrt(3))
        self.close(calculate(p)["electric"]["NP"]["current_a"], expected_kva * 1000 / (math.sqrt(3) * 380))
        self.mark("original-amp-load-stable-on-repeat-import")
        d, again, _ = updated_ledger(d, source, p["inputs"])
        p["inputs"].update(again)
        self.close(calculate(p)["electric"]["NP"]["current_a"], expected_kva * 1000 / (math.sqrt(3) * 380))
        self.mark("removal-restores-original-amp-and-panel-pf")
        _, restore, _ = removed_ledger(d, "p", p["inputs"])
        self.assertEqual(restore["e_np_exh"], "10")
        self.assertEqual(restore["u_e_np_exh"], "A")
        self.assertEqual(restore["e_np_pf"], "0.5")

    def test_schedule_transfer(self):
        self.mark("mixed-pf-vector-power-and-continuous-design")
        result = analyze(record("電力", id="a", power=10, quantity=1, usage=50, pf=.8, kind="連續運轉"), record("電力", id="b", power=10, quantity=1, usage=100, pf=1))
        g = result["groups"][0]
        p = default_project()
        p["inputs"].update(e_up_eq="0", e_up_oven="0")
        entry = equipment_contribution(result, g, p["inputs"], "UP")
        d, u, _ = updated_ledger(empty_ledger(), entry, p["inputs"])
        p["inputs"].update(u)
        actual = calculate(p)["electric"]["UP"]
        self.close(actual["current_a"], math.hypot(15, 3.75) * 1000 / (math.sqrt(3) * 380))
        self.assertGreaterEqual(actual["design_current_a"], g["design_current_a"] - 1e-9)
        self.mark("schedule-reimport-does-not-double-count")
        d, u, _ = updated_ledger(d, entry, p["inputs"])
        self.close(float(u["e_up_eq"]), 15)
        self.mark("single-phase-transfer-refused")
        single = analyze(record("電力", phases=1, voltage=220))
        with self.assertRaises(ValueError):
            equipment_contribution(single, single["groups"][0], p["inputs"])
        self.mark("different-voltage-transfer-refused")
        single = analyze(record("電力", phases=3, voltage=220))
        with self.assertRaises(ValueError):
            equipment_contribution(single, single["groups"][0], p["inputs"])
        for system, target in [("CDA", "1"), ("N2", "2"), ("DI", "DI"), ("PV", "PV"), ("PCW", "PCW"), ("EXHAUST", "EXHAUST")]:
            self.mark("equipment-transfer-" + system)
            result = analyze(record(system))
            entry = equipment_contribution(result, result["groups"][0], default_project()["inputs"], target)
            _, u, _ = updated_ledger(empty_ledger(), entry, default_project()["inputs"])
            self.assertTrue(u)
            if system == "CDA":
                self.close(float(u["gas1_q"]), result["groups"][0]["demand_standard_lpm"])

    def test_simple_scope_and_gas_basis(self):
        self.mark("duct-dimensions-unknown-pressure-valid")
        d = defaults("duct")
        d.update(pressure="unknown", length="unknown", k_sum="unknown", equipment="unknown")
        result = calculate_tool("duct", d)
        self.assertFalse(result["path_checked"])
        self.mark("duct-pressure-check-needs-pressure")
        d["check_path"] = "1"
        with self.assertRaises(ValueError):
            calculate_tool("duct", d)
        self.mark("standard-and-actual-gas-equivalence")
        d = defaults("gas")
        standard = calculate_tool("gas", d)
        d.update(flow_basis="管內實際流量", flow_unit="ALPM", flow=str(standard["actual_lpm"]))
        actual = calculate_tool("gas", d)
        self.close(standard["minimum_id_mm"], actual["minimum_id_mm"])
        self.close(standard["standard_lpm"], actual["standard_lpm"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Regression)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    output = ROOT / "evidence/v556-features.json"
    output.write_text(json.dumps(dict(version="5.5.6", scenarios=len(CASES), cases=CASES, failures=len(result.failures), errors=len(result.errors), passed=result.wasSuccessful()), ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(len(CASES)) + " distinct new scenarios; " + str(output))
    sys.exit(0 if result.wasSuccessful() else 1)
