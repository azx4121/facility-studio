"""Language switching must not change engineering data or calculations."""

import ast
import csv
import copy
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from facility_studio import i18n
from facility_studio.simple_schema import defaults, TOOLS
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_reports import tool_report
from facility_studio.schema import default_project, FIELDS
from facility_studio.engine import calculate
from facility_studio.ahu_schema import NM_DEFAULTS, NM_FIELDS
from facility_studio.ahu_engine import nm_calculate
from facility_studio.reports import report, nm_report
from facility_studio.html_report import summary_html
from facility_studio.equipment_io import (
    export_template,
    export_csv_templates,
    load_equipment,
    Cell,
)
from facility_studio.equipment_schema import SCHEMAS, SYSTEMS, example
from facility_studio.equipment_analysis import analyze_equipment, equipment_report

checks = 0


def check(value, message):
    global checks
    if not value:
        raise AssertionError(message)
    checks += 1


def english(text):
    check(
        not re.search(r"[\u3400-\u9fff]", text),
        "Untranslated authored text: " + text[:400],
    )


for path in (Path(__file__).resolve().parents[1] / "facility_studio").glob("*.py"):
    if path.stem in ("english_catalog", "i18n", "localized_tk", "language_acceptance"):
        continue
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and re.search(r"[\u3400-\u9fff]", node.value)
        ):
            english(i18n.translate(node.value, "en"))

# Inspect the resulting field definitions, including captions changed at runtime.
for fields in (NM_FIELDS, FIELDS):
    for spec in fields.values():
        for key in ("label", "unit", "help", "note"):
            if isinstance(spec.get(key), str):
                english(i18n.translate(spec[key], "en"))

cases = [
    ("electrical", {}),
    (
        "electrical",
        {"supply": "單相 220V", "power": "5", "kind": "連續運轉", "pf": "1"},
    ),
    ("electrical", {"kind": "馬達", "power": "30", "ambient": "45"}),
    ("duct", {}),
    (
        "duct",
        {"flow": "2000", "flow_unit": "CFM", "check_path": "1", "pressure": "300"},
    ),
    ("duct", {"flow": "0"}),
    ("gas", {}),
    (
        "gas",
        {
            "gas": "N2",
            "flow": "100",
            "flow_unit": "Sm³/h",
            "pressure": "600",
            "pressure_unit": "kPa(g)",
        },
    ),
    ("lighting", {}),
    ("lighting", {"area_mode": "體積 m³", "area": "90", "height": "3"}),
    (
        "lighting",
        {
            "mode": "反算燈數",
            "target": "500",
            "area": "30",
            "lumen_mode": "燈具型錄流明",
        },
    ),
    ("water", {}),
    ("water", {"mode": "已知熱量", "power": "100", "delta": "5"}),
    ("air", {}),
    ("air", {"temperature": "35", "rh": "70"}),
    ("air", {"atmosphere": "80"}),
    ("air", {"rh": "0"}),
    ("units", {}),
    ("units", {"category": "溫度差（升溫／降溫）", "value": "5", "unit": "°C差"}),
    ("units", {"category": "閥門流量係數（Kv／Cv）", "value": "10", "unit": "Kv"}),
]
for tool, updates in cases:
    inputs = defaults(tool)
    inputs.update(updates)
    original = copy.deepcopy(inputs)
    i18n.set_language("zh-Hant", persist=False)
    zh_result = calculate_tool(tool, inputs)
    zh = tool_report(zh_result, inputs)
    i18n.set_language("en", persist=False)
    en_result = calculate_tool(tool, inputs)
    en = tool_report(en_result, inputs)
    check(
        zh_result == en_result and inputs == original,
        "Numerical / input language drift",
    )
    english(en)
    check(zh != en, "No report translation: " + tool)
    check(
        Counter(re.findall(r"\d+(?:[.,]\d+)*", zh))
        == Counter(re.findall(r"\d+(?:[.,]\d+)*", en)),
        "Report numeric text changed: " + tool,
    )

full = calculate(default_project())
ahu = nm_calculate(dict(NM_DEFAULTS))
for result, function in ((full, report), (ahu, nm_report), (full, summary_html)):
    before = copy.deepcopy(result)
    english(function(result))
    check(result == before, "Report mutated model result")
check('lang="en"' in summary_html(full), "HTML language attribute")
for system in SYSTEMS:
    row = example(system)
    row["enabled"] = 1
    # English choice values are accepted and normalized; user identifiers survive.
    cells = {
        c["key"]: Cell(
            i18n.translate(row[c["key"]], "en")
            if c["kind"] == "choice"
            else row[c["key"]]
        )
        for c in SCHEMAS[system]
    }
    result = analyze_equipment(
        {
            "schema_id": "FacilityStudioEquipment/1",
            "source_name": "test.csv",
            "records": [{"system": system, "row": 6, "cells": cells}],
        }
    )
    english(equipment_report(result))

# A language switch must retain source text and user-defined project names.
custom = default_project()
custom["inputs"]["project_name"] = "電力 <script>alert(1)</script> 案件"
custom_result = calculate(custom)
rendered = report(custom_result, language="en")
check(
    custom["inputs"]["project_name"] in rendered, "Custom project name was translated"
)
check(
    i18n.translate(rendered, "zh-Hant") == report(custom_result, language="zh-Hant"),
    "Rendered report lost its Chinese source",
)
i18n.set_language("zh-Hant", persist=False)
html = summary_html(custom_result, language="en")
check(
    'lang="en"' in html and "&lt;script&gt;" in html and "<script>" not in html,
    "Explicit HTML locale / escaped user name",
)
check(
    custom_result["project"]["inputs"]["project_name"]
    == custom["inputs"]["project_name"],
    "Report changed stored name",
)
from facility_studio.ahu_schema import NM_CONTROL_NOTES

for count in (1, 6, 12):
    english(
        i18n.translate(NM_CONTROL_NOTES.replace("8 台 EC", str(count) + " 台 EC"), "en")
    )
i18n.set_language("en", persist=False)

with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    os.environ["FACILITY_STUDIO_PREFERENCES"] = str(folder / "prefs/preferences.json")
    i18n.set_language("en")
    check(
        json.loads(i18n.preference_path().read_text())["language"] == "en",
        "Preference persistence",
    )
    script = (
        "from facility_studio import i18n; i18n.initialize(); print(i18n.language())"
    )
    loaded = subprocess.check_output(
        [sys.executable, "-c", script],
        env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1])),
        text=True,
    ).strip()
    check(loaded == "en", "Cold-start preference reload")
    target = folder / "Equipment English.xlsx"
    export_template(target)
    check(len(load_equipment(target)["systems"]) == 7, "English Excel import")
    with zipfile.ZipFile(target) as archive:
        for name in archive.namelist():
            if name.endswith(".xml"):
                for element in ET.fromstring(archive.read(name)).iter():
                    if element.tag.rsplit("}", 1)[-1] in ("t", "formula1"):
                        english(element.text or "")
    csv_folder = folder / "csv"
    export_csv_templates(csv_folder)
    for system in SYSTEMS:
        path = csv_folder / (i18n.translate(system) + ".csv")
        check(
            len(load_equipment(path, i18n.translate(system))["records"]) == 1,
            "English CSV import",
        )
    # Import of historical Chinese workbooks remains available in English mode.
    source = (
        Path(__file__).resolve().parents[1]
        / "facility_studio/resources/Equipment_Template.xlsx"
    )
    check(
        len(load_equipment(source)["systems"]) == 7,
        "Historical Chinese template compatibility",
    )
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target) as new:
        for name in old.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                formula = lambda data: [
                    re.sub(r'"[^"]*"', '"text"', el.text or "")
                    for el in ET.fromstring(data).iter()
                    if el.tag.endswith("}f")
                ]
                check(
                    formula(old.read(name)) == formula(new.read(name)),
                    "Workbook arithmetic changed",
                )
    os.environ.pop("FACILITY_STUDIO_PREFERENCES")
i18n.set_language("zh-Hant", persist=False)
print(
    f"20 language-parity scenarios, {checks} localization / import / persistence checks passed"
)
