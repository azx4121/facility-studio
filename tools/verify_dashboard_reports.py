#!/usr/bin/env python3
"""Check executive reports against either source tree without opening a GUI.

Includes numerical presentation, missing-data boundaries, HTML escaping,
localization, and nonmutation. Optional HTML samples are source-test artifacts,
not screenshots or native Windows / macOS acceptance evidence.
"""

import argparse
from collections import Counter
import copy
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import platform as host_platform
import re
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u3400-\u9fff]")


class DocumentShape(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.cards = 0
        self.images = 0
        self.scripts = 0
        self.language = None
        self.viewport = False
        self.utf8 = False
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.language = attrs.get("lang")
        if tag == "article" and "kpi-card" in attrs.get("class", "").split():
            self.cards += 1
        if tag == "img":
            self.images += 1
        if tag == "script":
            self.scripts += 1
        if tag == "meta":
            self.viewport |= attrs.get("name") == "viewport"
            self.utf8 |= attrs.get("charset", "").lower() == "utf-8"


def run_checks(source_platform, artifacts_dir=None):
    source_root = ROOT / source_platform
    package_root = source_root / "facility_studio"
    if not package_root.is_dir():
        raise ValueError("Selected source tree is missing: " + str(source_root))
    loaded = sys.modules.get("facility_studio")
    if loaded and Path(loaded.__file__).resolve().parent != package_root.resolve():
        raise RuntimeError("Run each source platform in a fresh Python process")
    sys.path.insert(0, str(source_root))
    from facility_studio.services import calculate_pipeline
    from facility_studio.html_report import html_report, summary_html, export_html_report
    from facility_studio.reports import executive_summary, executive_summary_html, report, nm_report
    from facility_studio.simple_reports import presentation, tool_report, pipeline_report
    from facility_studio.simple_engines import calculate_tool
    from facility_studio.simple_schema import defaults
    from facility_studio.schema import default_project, SCHEMA_VERSION
    from facility_studio.engine import calculate
    from facility_studio.ahu_engine import nm_calculate
    from facility_studio.ahu_schema import NM_DEFAULTS
    from facility_studio.errors import InputError

    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(dict(name=name, passed=True))

    def rejects(name, action):
        try:
            action()
        except InputError as error:
            check(name, error.code == "incomplete_result")
        else:
            raise AssertionError(name + ": incomplete result was exported")

    def numerals(text):
        return Counter(re.findall(r"\d+(?:[.,]\d+)*", text))

    inputs = {
        "cleanroom": {"area": "100", "height": "3", "ach": "60", "delta_p": "15", "persons": "10",
                      "ffu_topology": "MAU入靜壓箱經FFU送風", "ffu_airflow_basis": "室內基本循環（另加OA）"},
        "electrical": {"chiller_cop": "5", "mau_input_kw": "2", "process_input_kw": "20"},
        "water": {"length": "50"},
    }
    pipeline = calculate_pipeline(inputs)
    check("requested 50 m water path is actually adopted", pipeline["water"]["pressure"]["length_m"] == 50)
    check("adopted water pressure reaches pump input", pipeline["pumps"]["path_head_m"] == pipeline["water"]["pressure"]["head_m"])
    before = copy.deepcopy(pipeline)
    rows = executive_summary(pipeline)
    check("exactly seven equipment / system overview rows", len(rows) == 7)
    check("FFU overview includes rounded quantity", "19 台" in rows[0]["selection"])
    check("FFU overview includes OA and thousands formatting", "18,300 CMH" in rows[0]["demand"])
    check("DCC design return excludes OA", "18,000 CMH" in rows[2]["demand"])
    check("motor nameplate covers shaft output plus margin", pipeline["pumps"]["recommended_motor_kw"] >= pipeline["pumps"]["shaft_power_kw"] * 1.15)
    expected_kw = f"{pipeline['heat_loads']['q_total_kw']:,.2f}".rstrip("0").rstrip(".")
    check("reported chiller cooling matches calculated thermal load", rows[3]["demand"].startswith(expected_kw))
    documents = {}
    for lang in ("zh-Hant", "en"):
        document = str(html_report(pipeline, language=lang))
        shape = DocumentShape(document)
        check("HTML5 document " + lang, document.startswith("<!doctype html>"))
        check("seven top KPI cards " + lang, shape.cards == 7)
        check("HTML language " + lang, shape.language == lang)
        check("UTF-8 and responsive viewport " + lang, shape.utf8 and shape.viewport)
        check("industrial theme, numeric font and structural table " + lang,
              "#F8FAFC" in document and "Consolas" in document and "<thead>" in document and 'scope="col"' in document)
        check("no external media / script elements " + lang, shape.images == 0 and shape.scripts == 0)
        if lang == "en":
            check("pipeline report authored text is translated", CJK.search(document) is None)
        documents["pipeline-" + lang + ".html"] = document
    check("language switching preserves report numerals", numerals(documents["pipeline-zh-Hant.html"]) == numerals(documents["pipeline-en.html"]))
    for key in ("cleanroom", "heat_loads", "water", "pumps", "electrical"):
        check("dashboard presentation " + key, bool(presentation(pipeline[key])))
        zh = tool_report(pipeline[key], pipeline["adopted_inputs"][key], language="zh-Hant")
        en = tool_report(pipeline[key], pipeline["adopted_inputs"][key], language="en")
        check("tool report translates " + key, CJK.search(en) is None)
        check("tool report preserves numerals " + key, numerals(zh) == numerals(en))
    check("text pipeline report translates", CJK.search(pipeline_report(pipeline, language="en")) is None)
    check("report generation does not mutate source results", pipeline == before)
    check("missing quick-pipeline values remain visibly missing", all("尚未計算" in row["demand"] or "尚未計算" in row["selection"] for row in executive_summary({})))

    large_input = defaults("electrical")
    large_input.update(power="200", kind="一般設備", eta="1")
    large_load = calculate_tool("electrical", large_input)
    independent_current = 200000 / (math.sqrt(3) * 380 * .85)
    check("200 kW general-load current uses the declared supply", math.isclose(large_load["current_a"], independent_current))
    check("ordinary-load cable candidate may still be 400 AT", large_load["selected"]["nfb_a"] == 400)
    large_row = executive_summary(large_load)[6]
    if source_platform == "windows":
        check("general-load design current follows the declared circuit duty", math.isclose(large_load["design_breaker_a"], independent_current))
        check("summary adopts the same coordinated 400 AT circuit candidate", large_load["recommended_breaker_at"] == 400
              and "400 AT" in large_row["selection"] and large_row["status"] == "同迴路配線候選")
        check("circuit candidate does not claim an upstream main feeder", "主進線未計算" in large_row["selection"])
        check("ordinary-load circuit retains a valid protection bound", 400 <= large_load["selected"]["ampacity_a"])
    else:
        check("legacy Mac continuous reference exceeds the 400 AT short table", large_load["design_breaker_a"] > 400 and large_load["recommended_breaker_at"] is None)
        check("legacy Mac reference is not replaced with an ordinary candidate", large_row["status"] == "超出級距" and large_row["tone"] == "danger" and "400 AT" not in large_row["selection"])
        check("legacy Mac above-catalogue reference retains a warning", bool(large_load.get("warnings")))

    attack = copy.deepcopy(pipeline)
    attack["cleanroom"]["ffu_size"] = '<img src=x onerror="alert(1)">'
    attack["warnings"] = ["<script>benign_report_marker()</script>"]
    for lang in ("zh-Hant", "en"):
        escaped = str(html_report(attack, language=lang))
        shape = DocumentShape(escaped)
        check("dynamic HTML is escaped " + lang, shape.images == 0 and shape.scripts == 0 and "&lt;img src=x" in escaped and "&lt;script&gt;benign_report_marker()" in escaped)

    full = calculate(default_project())
    full_before = copy.deepcopy(full)
    text = str(report(full, language="zh-Hant"))
    check("overview precedes first engineering chapter", text.index("Executive Design Summary") < text.index("一、設計條件"))
    check("legacy sensible-load report pattern is retained", f"室內顯熱 {full['qs']:.3f} kW" in text)
    check("separate panels do not imply a main-incomer calculation", "主進線未計算" in text)
    full_rows = executive_summary(full)
    check("panel selection contains AT and conductor area", "AT" in full_rows[6]["selection"] and "mm²" in full_rows[6]["selection"])
    for missing in ("summer", "electric", "water", "ffu_count", "project"):
        incomplete = copy.deepcopy(full)
        del incomplete[missing]
        for function in (report, summary_html, executive_summary_html):
            rejects("incomplete main rejected: " + function.__name__ + "/" + missing,
                    lambda f=function, value=incomplete: f(value))
    for lang in ("zh-Hant", "en"):
        documents["main-" + lang + ".html"] = str(summary_html(full, language=lang))
    check("full-project reporting is nonmutating", full == full_before)
    named = default_project()
    named["inputs"]["project_name"] = '<script>benign_title_marker()</script>'
    named_html = str(summary_html(calculate(named), language="en"))
    check("custom project titles are escaped and preserved", DocumentShape(named_html).scripts == 0 and "&lt;script&gt;benign_title_marker()" in named_html)

    unit = nm_calculate(dict(NM_DEFAULTS))
    check("single MAU report identifies its unit scope", "MAU 單機核心設計量" in nm_report(unit, language="zh-Hant"))
    for lang in ("zh-Hant", "en"):
        document = str(html_report(unit, language=lang))
        check("single MAU has six unit KPIs " + lang, DocumentShape(document).cards == 6)
        if lang == "en":
            check("single MAU report translates", CJK.search(document) is None)
        documents["mau-" + lang + ".html"] = document
    with tempfile.TemporaryDirectory(prefix="facility_report_checks_") as directory:
        destination = Path(directory) / "design.html"
        exported = export_html_report(pipeline, destination, language="zh-Hant")
        check("atomic HTML export returns the real output path", exported == destination.resolve())
        check("atomic HTML export matches the current calculation", destination.read_text(encoding="utf-8") == documents["pipeline-zh-Hant.html"])
    if artifacts_dir:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        for name, document in documents.items():
            (artifacts_dir / name).write_text(document, encoding="utf-8")
    return {"kind": "source-dashboard-reports", "source_platform": source_platform,
            "host_os": host_platform.system(), "python": host_platform.python_version(),
            "schema_version": SCHEMA_VERSION, "passed": True, "check_count": len(checks), "checks": checks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("windows", "macos"), required=True,
                        help="Source tree to import; this does not change the host OS")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence path")
    parser.add_argument("--artifacts-dir", type=Path, help="Optional directory for generated HTML examples")
    args = parser.parse_args(argv)
    try:
        result = run_checks(args.platform, args.artifacts_dir)
    except Exception as error:
        result = {"kind": "source-dashboard-reports", "source_platform": args.platform,
                  "host_os": host_platform.system(), "python": host_platform.python_version(),
                  "passed": False, "error": type(error).__name__ + ": " + str(error)}
        traceback.print_exc()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
