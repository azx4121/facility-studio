"""Black-box checks of unchanged, one-file FACS Windows executable bytes.

Only process containment / launch-environment helpers are imported from the
candidate. Expected values and result validation do not call application code.
This gate does not establish engineering suitability or OS network isolation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import ntpath
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
import zipfile

BLOCKED = "blocked_unverified_ampacity_basis"
TOOLS = {
    "electrical": ("電力配線", "Electrical sizing"),
    "duct": ("風管尺寸", "Duct sizing"),
    "gas": ("CDA／特氣管徑", "CDA / gas piping"),
    "lighting": ("照明照度", "Lighting"),
    "water": ("冷熱水快算", "Water / heat load"),
    "air": ("空氣狀態／線圖", "Psychrometrics"),
    "units": ("單位換算", "Unit converter"),
    "cleanroom": ("潔淨室風量", "Cleanroom airflow"),
    "heat_loads": ("熱負荷初估", "Heat load estimate"),
    "pumps": ("冰水泵浦", "Water pump sizing"),
    "liquid": ("液體／純水管路", "Liquid / pure water"),
    "vacuum": ("PV 真空快算", "PV vacuum calculator"),
}
RESTRICTED = {"nfb_a", "nfb_candidate_a", "wire_mm2", "ampacity_a", "iz_a",
              "pe_mm2", "pe_spec", "recommended_breaker_at"}
CSV_HEADER = ["啟用(1/0)", "設備編號", "設備名稱", "供應群組", "設備台數",
              "同時使用率(%)", "每台輸入功率(kW)", "供電電壓(V)",
              "供電相數(1/3)", "功率因數(PF)", "負載類型",
              "每台所需插座數", "單程配線長度(m)", "備註"]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def close(actual, expected, label, rel=1e-8, abs_tol=1e-8):
    require(isinstance(actual, (int, float)) and not isinstance(actual, bool)
            and math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_tol),
            f"{label}: expected {expected!r}, got {actual!r}")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def strict_json(path):
    def reject(value):
        raise AssertionError("Non-finite JSON constant: " + value)
    result = json.loads(Path(path).read_text(encoding="utf-8"),
                        object_pairs_hook=unique_object, parse_constant=reject)
    def visit(value):
        if isinstance(value, float):
            require(math.isfinite(value), "Non-finite JSON number")
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(result)
    require(isinstance(result, dict), "Expected JSON object")
    return result


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False), encoding="utf-8")


def text_report(path):
    value = Path(path).read_text(encoding="utf-8", errors="strict")
    require(len(value.strip()) > 30, "Empty / truncated report")
    require("\ufffd" not in value and "\x00" not in value, "Invalid report text")
    return value


def electrical_safe(value):
    """New calculation exports must not have adoptable sizing at any depth."""
    records = []
    def visit(node, path="$", electrical=False):
        if isinstance(node, dict):
            is_record = node.get("tool") == "electrical" or node.get("system") == "電力"
            is_record |= "selected" in node and "current_a" in node
            active = electrical or is_record
            if active:
                for key in RESTRICTED & set(node):
                    require(node[key] is None, f"Restricted sizing populated at {path}.{key}")
            if is_record:
                records.append(node)
                require(node.get("selection_status") in (BLOCKED, "no_electrical_load"),
                        "Missing blocked/no-load electrical status at " + path)
                if "selected" in node:
                    require(node["selected"] is None, "Unexpected electrical selection at " + path)
            for key, child in node.items():
                if key == "_electrical_export_policy":
                    require(child.get("selection_status") == BLOCKED, "Missing export restriction")
                    require(child.get("content_kind") == "load_only_result", "Unexpected retained sizing history")
                    require(child.get("historical_selection_paths") == [], "Unexpected sizing history")
                    require("not adoptable" in child.get("warning", ""), "Missing export limitation")
                else:
                    visit(child, path + "." + key, active or key == "electric")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{path}[{index}]", electrical)
    visit(value)
    require(records, "No electrical result records were checked")
    require(value.get("_electrical_export_policy", {}).get("selection_status") == BLOCKED,
            "Root electrical export restriction missing")
    return len(records)


def check_default_tool(tool, result):
    require(result.get("tool") == tool, "Wrong exported tool")
    require(isinstance(result.get("adopted_inputs"), dict) and result["adopted_inputs"],
            "Missing adopted input record")
    require(isinstance(result.get("failures"), list), "Missing explicit known-failure list")
    # Basic independent physical/arithmetic identities, not app golden copies.
    if tool == "electrical":
        close(result["power_kw"], 10, "Electrical input kW")
        close(result["current_a"], 10000 / (math.sqrt(3) * 380 * .85), "Three-phase current")
        close(result["design_a"], result["current_a"], "Noncontinuous current")
        electrical_safe(result)
    elif tool == "duct":
        close(result["flow_cmh"], 3000, "Duct flow")
        require(result["path_checked"] is False, "Unrequested duct pressure conclusion")
        for key in ("rectangle", "round"):
            value = result[key]
            close(value["area_m2"] * value["velocity_mps"] * 3600, 3000, "Duct continuity")
            require(0 < value["velocity_mps"] <= 8, "Duct exceeds velocity limit")
    elif tool == "gas":
        close(result["standard_lpm"], 800, "Standard gas flow")
        close(result["absolute_kpa"], 701.325, "Gas absolute pressure")
        close(result["actual_lpm"], 800 * 101.325 / 701.325, "Gas ideal volume correction")
    elif tool == "lighting":
        close(result["illuminance_lux"], 10 * 4000 * .6 * .8 / 30, "Lumen method")
        close(result["total_kw"], 10 * 40 / 1000, "Lighting power")
    elif tool == "water":
        close(result["flow_lpm"], 100, "Water flow")
        close(result["load_kw"], 100 * 1000 * 4.1868 * 5 / 60000, "Water heat balance")
        require(0 < result["pipe"]["velocity_mps"] <= 1.5, "Water velocity")
    elif tool == "air":
        close(result["state"]["t"], 35, "Air A temperature")
        close(result["comparison_state"]["t"], 26, "Air B temperature")
        close(result["delta_t_k"], 9, "Air temperature difference")
        close(result["delta_h_kj_kg"], result["state"]["h"] - result["comparison_state"]["h"], "Air enthalpy difference")
    elif tool == "units":
        close(result["values"]["CMH"], 1000, "Original flow unit")
        close(result["values"]["L/s"], 1000 / 3.6, "CMH to L/s")
    elif tool == "cleanroom":
        close(result["volume_m3"], 100 * 3, "Room volume")
        close(result["ffu_total_cmh"], 100 * 3 * 60, "FFU flow")
        close(result["ffu_count"], 18, "FFU count")
    elif tool == "heat_loads":
        close(result["q_room_sensible_kw"], 1.2 + 2 + .75 + 20, "Sensible heat sum")
        close(result["q_total_kw"], 1.2 + 2 + .75 + 20 + .55, "Total heat sum")
    elif tool == "pumps":
        close(result["hydraulic_power_kw"], 6 * 20 * 9.81 / 3600, "Pump water power")
        close(result["shaft_power_kw"], 6 * 20 * 9.81 / 3600 / .7, "Pump shaft power")
        close(result["motor_input_kw"], 6 * 20 * 9.81 / 3600 / .7 / .9, "Pump input power")
    elif tool == "liquid":
        close(result["flow_lpm"], 100, "Liquid flow")
        close(result["inner_mm"], result["outer_mm"] - 2 * result["wall_mm"], "Liquid actual diameter")
        close(result["velocity_mps"] * math.pi * (result["inner_mm"] / 1000) ** 2 / 4 * 60000,
              100, "Liquid continuity")
    elif tool == "vacuum":
        pressure = 150 * 101325 / 760
        close(result["pressure_pa"], pressure, "Vacuum Torr to Pa")
        close(result["actual_lpm"], 100 * 101325 / pressure * 293.15 / 273.15, "Vacuum volume correction")
        require(result["conductance_l_s"] is None and result["effective_speed_l_s"] is None,
                "Inapplicable molecular-flow result should stay unknown")


def workbook_sheets(path, language):
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, "Excel archive CRC failed")
        names = archive.namelist()
        require(len(names) == len(set(names)), "Duplicate XLSX members")
        require("[Content_Types].xml" in names, "Missing XLSX content types")
        require(not any("vbaProject" in name for name in names), "Unexpected Excel macros")
        tree = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = [node.get("name") for node in tree.findall("{*}sheets/{*}sheet")]
    expected = {"Electrical" if language == "en" else "電力", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV",
                "Instructions" if language == "en" else "填寫說明"}
    require(set(sheets) == expected and len(sheets) == 8, "Wrong Excel template sheets: " + repr(sheets))
    return sheets


def enable_template_example(source, destination, language):
    """Create a new XLSX fixture by enabling only the known electrical sample.

    Read OOXML relationships directly, do not import application or Excel code.
    Keep the exported template unchanged. No formulas are evaluated or changed.
    """
    source, destination = Path(source), Path(destination)
    require(source.resolve() != destination.resolve() and not destination.exists(), "Fixture must be a new file")
    before = digest(source)
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with zipfile.ZipFile(source) as original:
        book = ET.fromstring(original.read("xl/workbook.xml"))
        rels = ET.fromstring(original.read("xl/_rels/workbook.xml.rels"))
        title = "Electrical" if language == "en" else "電力"
        sheet = [node for node in book.findall("{*}sheets/{*}sheet") if node.get("name") == title]
        require(len(sheet) == 1, "Missing electrical template sheet")
        relation_id = sheet[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        relation = [node for node in rels if node.get("Id") == relation_id and node.get("TargetMode") != "External"]
        require(len(relation) == 1, "Missing internal template sheet relationship")
        target = relation[0].get("Target", "")
        require(target and ".." not in target and "\\" not in target, "Unexpected template relationship")
        member = target.lstrip("/") if target.startswith("/") else "xl/" + target
        tree = ET.fromstring(original.read(member))
        cells = {node.get("r"): node for node in tree.findall("{*}sheetData/{*}row/{*}c")}
        # Guard against a moved or materially different sample row.
        for reference, expected in {"A6": 0, "E6": 1, "F6": 100, "G6": 10,
                                    "H6": 380, "I6": 3, "J6": .85}.items():
            cell = cells[reference]
            require(cell.find("{*}f") is None, "Sample input must not contain a formula")
            close(float(cell.findtext("{*}v")), expected, "Template " + reference)
        cells["A6"].set("t", "n")
        cells["A6"].find("{" + namespace + "}v").text = "1"
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for info in original.infolist():
                output.writestr(info, ET.tostring(tree, encoding="utf-8", xml_declaration=True)
                                if info.filename == member else original.read(info.filename))
    require(digest(source) == before, "Exported original template changed")
    workbook_sheets(destination, language)


class Suite:
    """Injectable launcher is for unit/source probes, never native attestation."""
    def __init__(self, command, output, run_bounded, offline_environment, report,
                 persist=lambda: None, timeout=180):
        self.command = [str(p) for p in command]
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.run_bounded = run_bounded
        self.environment = offline_environment
        self.report = report
        self.persist = persist
        self.timeout = timeout

    def invoke(self, label, arguments, expected=0):
        case = self.output / label
        case.mkdir(exist_ok=False)
        data = case / "app-data"
        data.mkdir()
        log = case / "process.log"
        command = self.command + [str(a) for a in arguments]
        record = {"label": self.output.name + "/" + label, "command": command,
                  "expected_exit": expected, "passed": False}
        self.report["commands"].append(record)
        self.persist()
        start = time.monotonic()
        try:
            result = self.run_bounded(command, log, self.environment(data), timeout=self.timeout)
        except RuntimeError as error:
            # The existing helper deliberately treats any nonzero as an error.
            # Accept only its exact expected exit form, never a timeout/setup failure.
            require(expected != 0 and str(error) == f"Single EXE acceptance exited {expected}; inspect {log}",
                    "Unexpected process failure: " + str(error))
            result = getattr(error, "process_record", {"exit_code": expected, "elapsed_seconds": round(time.monotonic() - start, 3)})
        require(result["exit_code"] == expected, "Unexpected process exit code")
        record.update(result, passed=True)
        self.persist()
        return case

    def exports(self, label, arguments):
        output = self.output / (label + ".json")
        report = self.output / (label + ".txt")
        require(not output.exists() and not report.exists(), "Output destination already exists")
        self.invoke(label, arguments + ["--result", output, "--report", report])
        return strict_json(output), text_report(report)

    def refusal(self, label, arguments, stale_result, stale_report):
        for state in ("fresh", "stale"):
            stem = self.output / (label + "-" + state)
            result = stem.with_suffix(".json")
            report = stem.with_suffix(".txt")
            if state == "stale":
                shutil.copyfile(stale_result, result)
                shutil.copyfile(stale_report, report)
                before = digest(result), digest(report)
            self.invoke(label + "-" + state, arguments + ["--result", result, "--report", report], expected=2)
            if state == "stale":
                require((digest(result), digest(report)) == before, "Invalid input changed a previous export")
            else:
                require(not result.exists() and not report.exists(), "Invalid input exported fresh results")

    def run(self, gui_smoke=True):
        language_results = {}
        for language in ("zh-Hant", "en"):
            for tool in TOOLS:
                label = language + "-tool-" + tool
                value, report = self.exports(label, ["--language", language, "--tool", tool])
                check_default_tool(tool, value)
                require(TOOLS[tool][language == "en"] in report, "Localized tool title missing")
                if language == "zh-Hant":
                    language_results[tool] = value
                else:
                    require(value == language_results[tool], "UI language changed canonical tool data: " + tool)
            template = self.output / (language + "-設備 Template.xlsx")
            self.invoke(language + "-template-export", ["--language", language, "--export-equipment-template", template])
            workbook_sheets(template, language)
            self.refusal(language + "-disabled-template", ["--language", language, "--equipment", template],
                         self.output / (language + "-tool-electrical.json"),
                         self.output / (language + "-tool-electrical.txt"))
            active = self.output / (language + "-啟用範例 Template.xlsx")
            enable_template_example(template, active, language)
            value, _ = self.exports(language + "-template-import", ["--language", language, "--equipment", active])
            require(value["active_records"] == 1 and len(value["groups"]) == 1 and len(value["rows"]) == 1,
                    "Enabled Excel example equipment count mismatch")
            close(value["totals"]["connected_kw"], 10, "Excel connected power")
            close(value["totals"]["demand_kw"], 10, "Excel demand power")
            close(value["groups"][0]["current_a"], 10000 / (math.sqrt(3) * 380 * .85), "Excel current")
            electrical_safe(value)

        # Explicit inputs exercise override parsing and motor/zero-load distinctions.
        for label, inputs in (("electrical-hp", {"power": 10, "power_unit": "HP", "motor_efficiency": .8}),
                              ("electrical-zero", {"power": 0})):
            path = self.output / (label + "-input.json")
            write_json(path, inputs)
            result, _ = self.exports(label, ["--tool", "electrical", "--tool-input", path, "--language", "en"])
            electrical_safe(result)
            power = 10 * .745699871582 / .8 if label.endswith("hp") else 0
            close(result["electrical_input_kw"], power, "Explicit electrical input")
            close(result["current_a"], power * 1000 / (math.sqrt(3) * 380 * .85), "Explicit current")
            close(result["design_a"], result["current_a"] * (1.25 if power else 1), "Explicit design current")
            require(result["selection_status"] == (BLOCKED if power else "no_electrical_load"), "Wrong load status")

        # Real CSV import with a finite, independently calculable equipment load.
        schedule = self.output / "設備輸入 schedule.csv"
        with schedule.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(CSV_HEADER)
            writer.writerow([1, "EQ-獨立-001", "測試設備", "UP-01", 2, 50, 10, 380, 3, .85, "一般設備", 1, 30, "驗收"])
        csv_results = []
        for language in ("zh-Hant", "en"):
            value, _ = self.exports(language + "-equipment-csv", ["--language", language, "--equipment", schedule,
                                    "--equipment-system", "Electrical" if language == "en" else "電力"])
            require(value["active_records"] == 1 and len(value["groups"]) == 1 and len(value["rows"]) == 1,
                    "CSV equipment row count mismatch")
            close(value["totals"]["connected_kw"], 20, "CSV connected load")
            close(value["totals"]["demand_kw"], 10, "CSV diversity load")
            close(value["groups"][0]["current_a"], 10000 / (math.sqrt(3) * 380 * .85), "CSV demand current")
            electrical_safe(value)
            csv_results.append(value)
        require(csv_results[0] == csv_results[1], "Language changed canonical equipment data")

        project = self.output / "專案 repeated save.json"
        canonical = previous_result = None
        for cycle in range(3):
            language = "en" if cycle == 1 else "zh-Hant"
            # Actual EXE save (including overwrite), not a claim about GUI Save.
            self.invoke("project-default-save-" + str(cycle), ["--language", language, "--write-default", project])
            saved = strict_json(project)
            require(set(saved) == {"schema_version", "inputs", "pressure_drop", "provenance"}, "Wrong project schema")
            require(saved["schema_version"] == 12, "Unexpected project schema version")
            if canonical is None:
                canonical = saved
            require(saved == canonical, "Repeated default save is nondeterministic")
            value, _ = self.exports("project-read-" + str(cycle), ["--language", language, "--project", project])
            electrical_safe(value)
            require(value["project"] == canonical, "CLI changed stored project data")
            if previous_result is not None:
                require(value == previous_result, "Repeated project result changed")
            previous_result = value
        # Re-read the returned canonical project after external JSON serialization.
        roundtrip = self.output / "專案 roundtrip.json"
        write_json(roundtrip, previous_result["project"])
        value, _ = self.exports("project-json-roundtrip", ["--project", roundtrip, "--language", "en"])
        require(value == previous_result, "Canonical project roundtrip changed calculation")

        stale_result = self.output / "en-tool-electrical.json"
        stale_report = self.output / "en-tool-electrical.txt"
        for label, raw in (("unknown-key", '{"unknown_field": 1}'),
                           ("bad-number", '{"power": "not a number"}'),
                           ("negative-load", '{"power": -1}'),
                           ("invalid-json", '{"power":'),
                           ("nonfinite-json", '{"power": NaN}')):
            source = self.output / (label + "-input.json")
            source.write_text(raw, encoding="utf-8")
            self.refusal("reject-" + label, ["--tool", "electrical", "--tool-input", source], stale_result, stale_report)
        invalid_project = self.output / "invalid-project-input.json"
        write_json(invalid_project, {"schema_version": 12, "inputs": {}})
        self.refusal("reject-project", ["--project", invalid_project], stale_result, stale_report)
        invalid_equipment = self.output / "invalid-equipment-input.csv"
        invalid_equipment.write_text("unknown,column\n1,2\n", encoding="utf-8")
        self.refusal("reject-equipment", ["--equipment", invalid_equipment], stale_result, stale_report)
        if gui_smoke:
            for language in ("zh-Hant", "en"):
                self.invoke(language + "-gui-smoke", ["--language", language, "--gui-smoke"])


def load_helpers(candidate):
    # Enforce read-only helper imports even if the caller omits Python's -B.
    sys.dont_write_bytecode = True
    integration = Path(candidate).resolve() / "integration"
    path = integration / "onefile_validation.py"
    require(path.is_file(), "Missing existing process-containment helper")
    sys.path.insert(0, str(integration))
    spec = importlib.util.spec_from_file_location("frozen_check_launch_helpers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def valid_process_image_audit(audit, expected_image=None):
    if not isinstance(audit, dict):
        return False
    images = audit.get('images')
    if not isinstance(images, list) or not all(isinstance(row, dict) for row in images):
        return False
    return (audit.get('required') is True and audit.get('passed') is True
            and audit.get('errors') == []
            and type(audit.get('total_job_processes')) is int
            and type(audit.get('retained_process_handles')) is int
            and audit['total_job_processes'] > 0
            and audit['total_job_processes'] == audit['retained_process_handles'] == len(images)
            and all(isinstance(row.get('image'), str) and row['image']
                    and type(row.get('pid')) is int and row['pid'] > 0 for row in images)
            and len({row['pid'] for row in images}) == len(images)
            and (expected_image is None or all(
                ntpath.normcase(ntpath.normpath(row['image'])) ==
                ntpath.normcase(ntpath.normpath(str(expected_image))) for row in images)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--sha256", required=True, help="Trusted digest of previously built/tested EXE")
    parser.add_argument("--candidate", type=Path, required=True, help="Read-only source tree containing integration helpers")
    parser.add_argument("--evidence", type=Path, required=True, help="New evidence directory (must not exist)")
    parser.add_argument("--screenshots", action="store_true", help="Require startup captures for both GUIs and languages")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    require(sys.platform == "win32", "Native Windows is mandatory; no portable route can pass this gate")
    require(30 <= args.timeout <= 600, "Timeout must be 30..600 seconds")
    require(len(args.sha256) == 64 and all(c in "0123456789abcdefABCDEF" for c in args.sha256), "Invalid expected SHA-256")
    helpers, helper_path = load_helpers(args.candidate)
    exe = helpers._regular_executable(args.exe).resolve()
    helpers._validate_amd64_pe(exe)
    expected = args.sha256.lower()
    require(digest(exe) == expected, "EXE does not match the required tested SHA-256")
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    summary_path = evidence / "Frozen_External_Checks.json"
    summary = {"schema_version": 1, "passed": False, "native_windows": True,
               "host": platform.platform(), "executable_sha256": expected,
               "helper_sha256": digest(helper_path), "runner_sha256": digest(__file__),
               "commands": [], "screenshots": [], "observations": [], "installation_performed": False,
               "launch_path_policy": "windows-system-directories-only",
               "external_python_absence_claimed": False,
               "standalone_process_image_audit_required": True,
               "standalone_process_image_audit_passed": False,
               "application_network_audit_hook": True, "os_network_isolation_claimed": False,
               "engineering_or_formal_feed_approval_claimed": False,
               "gui_interactions_claimed": False, "screenshots_requested": args.screenshots,
               "scope": "Black-box CLI exports, refusal, project serialization, headless GUI smoke, optional visible startup only"}
    def persist():
        write_json(summary_path, summary)
    persist()
    try:
        with tempfile.TemporaryDirectory(prefix="facs-frozen-external-") as temp:
            for label, folder in (("plain", "portable"), ("unicode-space", "繁體中文 空白路徑")):
                launch = Path(temp) / folder
                launch.mkdir()
                copied = launch / exe.name
                shutil.copy2(exe, copied)
                require(list(launch.iterdir()) == [copied], "Portable directory must start with only the EXE")
                require(digest(copied) == expected, "Launch copy hash mismatch")
                suite = Suite([copied], evidence / label, helpers.run_bounded, helpers.offline_environment,
                              summary, persist, args.timeout)
                suite.run()
                if args.screenshots:
                    from capture_windows import capture_startup
                    for language in ("zh-Hant", "en"):
                        for full in (False, True):
                            record = capture_startup(copied, suite.output, language, full,
                                                     helpers.run_bounded, helpers.offline_environment,
                                                     timeout=args.timeout)
                            summary["screenshots"].append(record)
                            persist()
                require(digest(copied) == expected, "Launch EXE changed during checks")
                require(digest(exe) == expected, "Original EXE changed during checks")
        process_records = list(summary["commands"]) + [item["process"] for item in summary["screenshots"]]
        for record in process_records:
            require(valid_process_image_audit(record.get("process_image_audit"), record["command"][0]),
                    "Missing or incomplete standalone process-image audit")
        summary["standalone_process_image_audit_passed"] = True
        summary["passed"] = True
    except Exception as error:
        summary["error"] = str(error)
        summary["traceback"] = traceback.format_exc()
        raise
    finally:
        summary["original_exe_unchanged"] = digest(exe) == expected
        if not summary["original_exe_unchanged"]:
            summary["passed"] = False
        summary["artifacts"] = [{"path": str(path.relative_to(evidence)), "bytes": path.stat().st_size,
                                  "sha256": digest(path)} for path in sorted(evidence.rglob("*"))
                                 if path.is_file() and path != summary_path]
        persist()
    require(summary["passed"], "Frozen checks failed")
    print(json.dumps({"passed": True, "commands": len(summary["commands"]),
                      "screenshots": len(summary["screenshots"]), "sha256": expected}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
