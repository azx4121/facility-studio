"""R01–R05: independently check adopted conditions and exported explanations.

These checks run from source and inside the delivered Windows executable.
They decode report text/tables instead of merely comparing two formatters.
"""
import copy
from html.parser import HTMLParser
import math
from pathlib import Path
import re
import tempfile
from unittest.mock import patch

ISSUES = {"R01", "R02", "R03", "R04", "R05"}


class ReportTables(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in ("td", "th"):
            self.cell = []

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            if self.row is not None:
                self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(tuple(self.row))
            self.row = None


def run_checks():
    from .simple_engines import calculate_tool, electrical
    from .simple_schema import defaults, TOOLS, input_unit, active_field
    from .simple_reports import tool_report, pipeline_report
    from .html_report import html_report, summary_html
    from .services import calculate_pipeline
    from .errors import InputError
    from .engine import calculate
    from .schema import default_project
    from .reports import report, nm_report
    from .ahu_engine import nm_calculate
    from .ahu_schema import NM_DEFAULTS
    from .equipment_analysis import analyze_equipment, equipment_report
    from .equipment_io import Cell
    from .equipment_schema import SCHEMA_ID, SYSTEMS, example
    from .version import REPORT_VERSION

    checks = []

    def check(issue, name, condition):
        if not condition:
            raise AssertionError(issue + "/" + name)
        checks.append(dict(issue_id=issue, name=name, passed=True))

    for inputs, code, field in [
        ({"water": {"length_m": "50"}}, "unknown_field", "water.length_m"),
        ({"pump": {}}, "unknown_field", None),
        ({"water": {}, "pipes": {}}, "conflicting_input", "water"),
        ({"water": []}, "invalid_input", "water"),
        ([], "invalid_input", None),
    ]:
        try:
            calculate_pipeline(inputs)
        except InputError as error:
            check("R01", repr(inputs), error.code == code and (field is None or error.field_name == field))
        else:
            raise AssertionError("R01: invalid pipeline inputs were silently accepted")
    inputs = {"water": {"length": "50"}, "electrical": {"chiller_cop": "5", "mau_input_kw": "2", "process_input_kw": "20"}}
    original = copy.deepcopy(inputs)
    pipeline = calculate_pipeline(inputs)
    check("R01", "50 m is adopted and retained", pipeline["water"]["pressure"]["length_m"] == 50 and pipeline["adopted_inputs"]["water"]["length"] == "50")
    check("R01", "50 m pressure independent reference", math.isclose(pipeline["water"]["pressure"]["loss_pa"], 24197.929837789383, rel_tol=1e-10))
    check("R01", "50 m pump head independent reference", math.isclose(pipeline["pumps"]["head_m"], 2.4675021376096202, rel_tol=1e-10))
    check("R01", "pipeline input not mutated", inputs == original)
    check("R01", "documented pipes tool alias retains 50 m", calculate_pipeline({"pipes": {"length": "50"}})["water"]["pressure"]["length_m"] == 50)

    for kind in ("一般設備", "連續運轉", "馬達"):
        for unit, value in (("kW", "10"), ("W", "10000"), ("kVA", str(10/.85)), ("A", str(10000/(math.sqrt(3)*380*.85))), ("HP", "10"), ("PS", "10")):
            i = defaults("electrical")
            i.update(kind=kind, power_unit=unit, power=value)
            r = calculate_tool("electrical", i)
            factor = 1 if kind == "一般設備" and unit not in ("HP", "PS") else 1.25
            check("R02", f"{kind}/{unit} numeric duty", math.isclose(r["design_a"], r["current_a"]*factor))
            for lang in ("zh-Hant", "en"):
                txt = tool_report(r, i, language=lang)
                source_line = next(line for line in txt.source.splitlines() if "設計電流依據" in line)
                found = re.search(r"運轉電流 ([\d,.]+) A × ([\d.]+)＝([\d,.]+) A", source_line)
                a, multiple, design = (float(x.replace(",", "")) for x in found.groups())
                check("R02", f"{kind}/{unit}/{lang} printed arithmetic", multiple == factor and abs(a*multiple-design) < .0002)
                for fmt, text in (("txt", txt), ("html", html_report(r, language=lang))):
                    check("R02", f"{kind}/{unit}/{lang}/{fmt} no unconditional claim", "1.25 倍連續負載初估" not in text and "1.25-times continuous-load estimate" not in text)
                    check("R05", f"{kind}/{unit}/{lang}/{fmt} revision", REPORT_VERSION in text)
                    if lang == "en":
                        check("R02", f"{kind}/{unit}/{fmt} English", re.search(r"[\u3400-\u9fff]", text) is None)

    other = calculate_pipeline({"water": {"length": "50"}, "electrical": {"chiller_cop": "5", "mau_input_kw": "12", "process_input_kw": "10"}})
    for lang in ("zh-Hant", "en"):
        for fmt, function in (("txt", pipeline_report), ("html", html_report)):
            a, b = function(pipeline, language=lang), function(other, language=lang)
            check("R03", lang+fmt+" equal total / different source reports", pipeline["electrical"]["power_kw"] == other["electrical"]["power_kw"] and a != b)
            if fmt == "html":
                rows = ReportTables(a).rows
                check("R03", lang+" actual MAU ledger row", any(row[:2] == ("MAU", "2.000000 kW") for row in rows))
                check("R03", lang+" actual process ledger row", any(len(row) == 3 and row[1] == "20.000000 kW" for row in rows))
                check("R03", lang+" adopted water length table", any(row[1:] == ("50 m",) for row in rows))
            check("R03", lang+fmt+" COP and source total", "COP 5" in a and f"{pipeline['electrical']['power_kw']:,.6f} kW" in a)
            check("R05", lang+fmt+" pipeline revision", REPORT_VERSION in a)

    explicit = calculate_pipeline({"electrical": {"chiller_input_kw": "7", "chiller_cop": "inactive-draft"}})
    text = str(html_report(explicit, language="zh-Hant"))
    check("R03", "explicit chiller overrides inactive COP", "明填冰機輸入電功率" in text and "inactive-draft" not in text)
    legacy = electrical(defaults("electrical"))
    check("R03", "legacy result does not invent input conditions", "採用輸入條件未附" in html_report(legacy, language="zh-Hant"))

    for tool in TOOLS:
        i = defaults(tool)
        r = calculate_tool(tool, i)
        saved = copy.deepcopy(r)
        for lang in ("zh-Hant", "en"):
            txt, document = tool_report(r, i, language=lang), html_report(r, language=lang)
            check("R03", tool+lang+" HTML supplied conditions", bool(ReportTables(document).rows) and "採用輸入條件未附" not in document)
            check("R05", tool+lang+" tool revision", REPORT_VERSION in txt and REPORT_VERSION in document)
            if lang == "en":
                check("R04", tool+" English units and conditions", re.search(r"[\u3400-\u9fff]", txt+document) is None)
        check("R03", tool+" exports preserve result", r == saved)
        for row in TOOLS[tool]["fields"]:
            if row.get("display_unit") and active_field(tool,row["key"],i):
                unit = input_unit(tool, row, i)
                check("R04", tool+"/"+row["key"], f"{row['label']}：{i[row['key']]} {unit}" in tool_report(r,i,language="zh-Hant"))
    for mode,value,unit in (("面積 m²","75","m²"),("面積 坪","22.6875","坪"),("體積 m³","225","m³")):
        i=defaults("lighting");i.update(area_mode=mode,area=value,height="3")
        r=calculate_tool("lighting",i)
        check("R04", mode+" report unit", "空間面積："+value+" "+unit in tool_report(r,i,language="zh-Hant"))
    i=defaults("lighting");i.update(lumen_mode="燈具型錄流明",efficacy="unused-draft")
    r=calculate_tool("lighting",i)
    check("R03", "inactive photometric draft not adopted", "efficacy" not in r["adopted_inputs"] and "unused-draft" not in html_report(r,language="zh-Hant"))

    for system in ("AHU (OA+RA 混合)","FCU (風機盤管+外氣)","RCU (機房空調箱+外氣)","MAU+FFU+DCC (全外氣/無塵室)"):
        p=default_project();p["inputs"]["sys_type"]=system;r=calculate(p)
        for lang in ("zh-Hant","en"):
            t,h=report(r,language=lang),summary_html(r,language=lang)
            check("R05", system+lang+" workbench revision", REPORT_VERSION in t and REPORT_VERSION in h)
            if lang == "en":
                check("R03", system+" English selection basis", re.search(r"[\u3400-\u9fff]",t+h) is None)
        if system.startswith("FCU"):
            t=report(r,language="zh-Hant")
            check("R03", "FCU ratings exported", "單台風量 1200 CMH" in t and "FCU 單台額定：10 RT" in t)
            check("R03", "FCU governing count independently reproduced", r["counts"]["FCU"] == math.ceil(r["supply_room_cmh"]/1200) and "主導條件：風量" in t)
        if system.startswith("RCU"):
            p["inputs"]["en_rcu_rt"]="40";different=calculate(p)
            check("R03", "RCU same quantity / different rating remains visible", r["counts"]["RCU"]==different["counts"]["RCU"] and report(r)!=report(different))
    nm=nm_calculate(dict(NM_DEFAULTS))
    for lang in ("zh-Hant","en"):
        check("R05", lang+" MAU revision", REPORT_VERSION in nm_report(nm,language=lang) and REPORT_VERSION in html_report(nm,language=lang))
    for system in SYSTEMS:
        row=example(system);row["enabled"]=1
        result=analyze_equipment(dict(schema_id=SCHEMA_ID,source_name="synthetic-report.csv",records=[dict(system=system,row=6,cells={k:Cell(v) for k,v in row.items()})]))
        for lang in ("zh-Hant","en"):
            check("R05", system+lang+" schedule revision", REPORT_VERSION in equipment_report(result,language=lang))
    return checks


def run_ui(root, app, check, pump, output=None):
    """Export via actual buttons and verify the values users receive."""
    from . import i18n
    from .version import REPORT_VERSION, BUILD_VERSION
    original_language, original_tool = i18n.language(), app.current
    snapshots={}
    from .pv_acceptance import run_ui as check_pv
    check_pv(root, app, check, pump)
    with tempfile.TemporaryDirectory(prefix="report-export-") as temp:
        folder=Path(output).parent/"report-samples" if output else Path(temp)
        folder.mkdir(parents=True,exist_ok=True)
        try:
            for lang in ("zh-Hant","en"):
                i18n.set_language(lang,persist=False)
                app.nav["water"].invoke()
                page=app.active_page()
                snapshots.setdefault("water",page.data())
                page.suspended=True
                for key,value in dict(mode="已知水量",flow="100",flow_unit="LPM",length="50").items():
                    page.variables[key].set(value)
                page.suspended=False
                page.update_visibility();page.calculate();pump()
                check("R01 real water form adopts 50 m / "+lang,lambda:page.result["pressure"]["length_m"]==50)
                for suffix in ("txt","html"):
                    path=folder/("water-"+lang+"."+suffix)
                    with patch("facility_studio.simple_desktop.filedialog.asksaveasfilename",return_value=str(path)):
                        app.export_button.invoke();pump()
                    text=path.read_text(encoding="utf-8")
                    check("R04 actual exported 50 m / "+lang+suffix,lambda:re.search(r"\b50\s*m\b",text) is not None)
                    check("R05 actual exported revision / "+lang+suffix,lambda:REPORT_VERSION in text and BUILD_VERSION in root.title())
                summary=folder/("summary-"+lang+".html")
                with patch("facility_studio.simple_desktop.filedialog.asksaveasfilename",return_value=str(summary)):
                    app.summary_button.invoke();pump()
                check("R03 summary button retains adopted conditions / "+lang,lambda:any(row[1:]==("50 m",) for row in ReportTables(summary.read_text(encoding="utf-8")).rows))
                app.nav["lighting"].invoke();page=app.active_page()
                snapshots.setdefault("lighting",page.data())
                page.variables["area_mode"].set("體積 m³");pump()
                check("R04 dynamic volume unit / "+lang,lambda:page.unit_labels["area"].cget("text")=="m³")
        finally:
            for tool,values in snapshots.items():
                page=app.pages[tool];page.suspended=True
                for key,value in values.items():page.variables[key].set(value)
                page.suspended=False;page.previous=page.data();page.update_visibility();page.calculate()
            i18n.set_language(original_language,persist=False)
            app.show_tool(original_tool);pump()
