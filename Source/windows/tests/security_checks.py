"""Read-only, bounded security tests of one Facility Studio source tree.

Uses benign markers only. All modified input documents are temporary.
No production files or licensing terms are changed.
"""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import warnings
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/Security_Input_Checks.json"
sys.path.insert(0, str(ROOT))
from facility_studio.equipment_io import Cell, EquipmentImportError, _xml, load_equipment
from facility_studio.equipment_analysis import analyze_equipment
from facility_studio.equipment_schema import SCHEMAS, SCHEMA_ID, example
from facility_studio.errors import ValidationError
from facility_studio.workspace_store import new_workspace, read_workspace
from facility_studio.schema import default_project
from facility_studio.html_report import summary_html
from facility_studio.engine import calculate, read_project
from facility_studio.ahu_engine import nm_read_project
from facility_studio.json_io import read_json_file
from facility_studio.project_store import read_recovery

checks = []


def rejects(name, callback, expected=ValidationError):
    try:
        callback()
    except Exception as error:
        checks.append(dict(name=name, passed=isinstance(error, expected),
                           observed=type(error).__name__, detail=str(error)[:240]))
    else:
        checks.append(dict(name=name, passed=False, observed="accepted"))


def accepts(name, callback):
    try:
        ok = callback()
        checks.append(dict(name=name, passed=bool(ok), observed="accepted"))
    except Exception as error:
        checks.append(dict(name=name, passed=False, observed=type(error).__name__,
                           detail=str(error)[:240]))


with tempfile.TemporaryDirectory(prefix="facility_security_inputs_") as directory:
    directory = Path(directory)
    source = ROOT / "facility_studio/resources/Equipment_Template.xlsx"
    normal = directory / "normal.xlsx"
    with zipfile.ZipFile(source) as archive:
        base = {i.filename: archive.read(i) for i in archive.infolist()}
    fixture_ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    fixture_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    fixture_book = ET.fromstring(base["xl/workbook.xml"])
    fixture_sheet = next(s for s in fixture_book.findall("s:sheets/s:sheet", fixture_ns)
                         if s.get("name") == "電力")
    fixture_links = ET.fromstring(base["xl/_rels/workbook.xml.rels"])
    fixture_target = next(r.get("Target") for r in fixture_links
                          if r.get("Id") == fixture_sheet.get(fixture_rel))
    fixture_path = fixture_target.lstrip("/") if fixture_target.startswith("/") else "xl/" + fixture_target
    fixture_tree = ET.fromstring(base[fixture_path])
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    for reference, value, kind in (("A6", "1", "n"), ("C6", "SAFE_AUDIT_MARKER", "inlineStr")):
        cell = fixture_tree.find('.//s:c[@r="' + reference + '"]', fixture_ns)
        assert cell is not None, "Expected trusted template cell missing"
        cell.clear()
        cell.set("r", reference)
        cell.set("t", kind)
        if kind == "n":
            ET.SubElement(cell, namespace + "v").text = value
        else:
            ET.SubElement(ET.SubElement(cell, namespace + "is"), namespace + "t").text = value
    base[fixture_path] = ET.tostring(fixture_tree, encoding="utf-8")
    with zipfile.ZipFile(normal, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in base.items():
            archive.writestr(name, body)

    def workbook(name, changed=None, extra=None):
        path = directory / (name + ".xlsx")
        content = dict(base)
        if changed:
            content.update(changed)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for member, data in content.items():
                archive.writestr(member, data)
            if extra:
                for member, data in extra:
                    archive.writestr(member, data)
        return path

    def analyze(path):
        return analyze_equipment(load_equipment(path))

    accepts("valid_xlsx", lambda: analyze(normal)["active_records"] == 1)
    xml_ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    relationship_id = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    workbook_xml = ET.fromstring(base["xl/workbook.xml"])
    power_sheet = next(s for s in workbook_xml.findall("s:sheets/s:sheet", xml_ns)
                       if s.get("name") == "電力")
    relationship_xml = ET.fromstring(base["xl/_rels/workbook.xml.rels"])
    power_relationship = next(r for r in relationship_xml
                              if r.get("Id") == power_sheet.get(relationship_id))
    sheet_target = power_relationship.get("Target")
    sheet_name = sheet_target.lstrip("/") if sheet_target.startswith("/") else "xl/" + sheet_target
    sheet = base[sheet_name].decode("utf-8")
    assert "SAFE_AUDIT_MARKER" in sheet, "Fixture must address active equipment sheet"
    safe_utf16 = '<?xml version="1.0" encoding="utf-16"?>' + sheet
    utf16 = workbook("valid_utf16", {sheet_name: safe_utf16.encode("utf-16")})
    accepts("valid_utf16_xlsx", lambda: analyze(utf16)["active_records"] == 1)

    for encoding in ("utf-8", "utf-16"):
        declaration = ('<?xml version="1.0" encoding="' + encoding + '"?>'
                       '<!DOCTYPE worksheet [<!ENTITY audit "SAFE_AUDIT_MARKER">]>')
        content = (declaration + sheet.replace("SAFE_AUDIT_MARKER", "&audit;")).encode(encoding)
        path = workbook("internal_entity_" + encoding, {sheet_name: content})
        rejects("reject_internal_entity_" + encoding, lambda p=path: analyze(p))
        outside = directory / "unshared.txt"
        outside.write_text("PRIVATE_BENIGN_MARKER", encoding="utf-8")
        external = ('<?xml version="1.0" encoding="' + encoding + '"?>'
                    '<!DOCTYPE worksheet [<!ENTITY audit SYSTEM "' + outside.as_uri() + '">]>')
        content = (external + sheet.replace("SAFE_AUDIT_MARKER", "&audit;")).encode(encoding)
        path = workbook("external_entity_" + encoding, {sheet_name: content})
        rejects("reject_external_entity_" + encoding, lambda p=path: analyze(p))

    invalid = directory / "broken.xlsx"
    invalid.write_bytes(b"not a zip")
    rejects("reject_non_zip_xlsx", lambda: analyze(invalid))
    missing = dict(base)
    missing.pop("xl/workbook.xml")
    invalid = directory / "missing.xlsx"
    with zipfile.ZipFile(invalid, "w") as archive:
        for member, data in missing.items():
            archive.writestr(member, data)
    rejects("reject_missing_workbook", lambda: analyze(invalid))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        path = workbook("duplicate", extra=[("xl/workbook.xml", base["xl/workbook.xml"])])
    rejects("reject_duplicate_zip_members", lambda: analyze(path))
    path = workbook("macro", extra=[("xl/vbaProject.bin", b"NON_EXECUTABLE_MARKER")])
    rejects("reject_macro_payload", lambda: analyze(path))
    path = workbook("many", extra=[(f"padding/{n}", b"") for n in range(3001)])
    rejects("reject_excessive_zip_members", lambda: analyze(path))
    large = directory / "large.xlsx"
    with large.open("wb") as file:
        file.truncate(20 * 1024 * 1024 + 1)
    rejects("reject_oversized_input", lambda: analyze(large))
    path = workbook("inflation", extra=[("padding", b"0" * (40 * 1024 * 1024 + 1))])
    rejects("reject_oversized_decompression", lambda: analyze(path))

    relationships = base["xl/_rels/workbook.xml.rels"].decode("utf-8")
    for tag, target in (("parent", "../outside.xml"), ("backslash", "..\\outside.xml")):
        changed = relationships.replace(sheet_target, target)
        assert changed != relationships, "Fixture sheet relationship missing"
        path = workbook(tag, {"xl/_rels/workbook.xml.rels": changed.encode()})
        rejects("reject_worksheet_path_" + tag, lambda p=path: analyze(p))
    external_relationship = relationships.replace(
        'Target="' + sheet_target + '"',
        'Target="https://example.invalid/not_requested.xml" TargetMode="External"')
    assert external_relationship != relationships
    path = workbook("external_sheet", {"xl/_rels/workbook.xml.rels": external_relationship.encode()})
    rejects("reject_external_sheet_reference", lambda: analyze(path))
    invalid = directory / "macro.xlsm"
    invalid.write_bytes(normal.read_bytes())
    rejects("reject_xlsm_extension", lambda: analyze(invalid))

    def schedule(**changes):
        values = example("電力")
        values.update(enabled=1, **changes)
        record = dict(system="電力", row=6, cells={k: Cell(v) for k, v in values.items()})
        return dict(schema_id=SCHEMA_ID, source_name="benign", systems=["電力"], records=[record])

    for name, value in (("nan", "NaN"), ("infinity", "Infinity"),
                        ("negative", -1), ("bool", True)):
        rejects("reject_power_" + name, lambda v=value: analyze_equipment(schedule(power=v)))
    formula = schedule()
    formula["records"][0]["cells"]["power"] = Cell("10", formula=True)
    rejects("reject_cached_xlsx_formula", lambda: analyze_equipment(formula))
    rejects("reject_text_controls", lambda: analyze_equipment(schedule(name="line1\nline2")))
    rejects("reject_long_text", lambda: analyze_equipment(schedule(name="x" * 501)))
    rejects("reject_invalid_voltage", lambda: analyze_equipment(schedule(voltage=0)))
    accepts("code_like_text_is_plain_data", lambda: analyze_equipment(
        schedule(name="__import__('os').system('SAFE_MARKER')"))["active_records"] == 1)

    def csv_path(name, **changes):
        path = directory / (name + ".csv")
        values = example("電力")
        values.update(enabled=1, **changes)
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([c["label"] for c in SCHEMAS["電力"]])
            writer.writerow([values[c["key"]] for c in SCHEMAS["電力"]])
        return path
    path = csv_path("valid_csv")
    accepts("valid_csv", lambda: analyze(path)["active_records"] == 1)
    path = csv_path("formula_csv", power="=1+1")
    rejects("reject_csv_formula", lambda: analyze(path))
    path = directory / "columns.csv"
    path.write_text(",".join(["column"] * 129), encoding="utf-8")
    rejects("reject_excess_csv_columns", lambda: analyze(path))
    path = directory / "headers.csv"
    path.write_text("unknown,headers\n1,2\n", encoding="utf-8")
    rejects("reject_unknown_csv_columns", lambda: analyze(path))

    project = default_project()
    workspace = new_workspace(project)
    path = directory / "workspace.json"
    path.write_text(json.dumps(workspace, ensure_ascii=False), encoding="utf-8")
    accepts("valid_workspace", lambda: read_workspace(path)["kind"] == "facility_workspace")
    path = directory / "bad.json"
    path.write_text("{broken", encoding="utf-8")
    rejects("reject_invalid_json", lambda: read_workspace(path), ValueError)
    path = directory / "nan.json"
    path.write_text('{"value":NaN}', encoding="utf-8")
    rejects("reject_nonfinite_json", lambda: read_workspace(path))
    path = directory / "large.json"
    with path.open("wb") as file:
        file.truncate(15_000_001)
    rejects("reject_oversized_json", lambda: read_workspace(path))
    path = directory / "nested.json"
    path.write_text('{"unknown":' + "[" * 10000 + "0" + "]" * 10000 + "}", encoding="utf-8")
    rejects("deep_json_has_controlled_validation_error", lambda: read_workspace(path))

    project["inputs"]["project_name"] = '<script>SAFE_MARKER</script>'
    result = calculate(project)
    accepts("html_report_escapes_project_name", lambda: (
        "&lt;script&gt;SAFE_MARKER&lt;/script&gt;" in summary_html(result)
        and "<script>SAFE_MARKER</script>" not in summary_html(result)))

    def parsed_xml(body):
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w") as archive:
            archive.writestr("audit.xml", body)
        with zipfile.ZipFile(io.BytesIO(memory.getvalue())) as archive:
            return _xml(archive, "audit.xml")

    for encoding in ("utf-8", "utf-16"):
        text = '<?xml version="1.0" encoding="' + encoding + '"?><r><!-- harmless <!DOCTYPE text -->SAFE</r>'
        accepts("xml_comment_is_not_dtd_" + encoding,
                lambda body=text.encode(encoding): parsed_xml(body).text == "SAFE")
    for codec, bom in (("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
        text = '<?xml version="1.0" encoding="utf-16"?><!DOCTYPE r [<!ENTITY a "SAFE">]><r>&a;</r>'
        rejects("reject_entity_bom_" + codec, lambda body=bom + text.encode(codec): parsed_xml(body))
    accepts("xml_depth_64", lambda: parsed_xml(("<r>" * 64 + "</r>" * 64).encode()).tag == "r")
    rejects("reject_xml_depth_65", lambda: parsed_xml(("<r>" * 65 + "</r>" * 65).encode()))
    path = directory / "json_depth.json"
    path.write_text("[" * 64 + "0" + "]" * 64)
    accepts("json_depth_64", lambda: isinstance(read_json_file(path), list))
    path.write_text("[" * 65 + "0" + "]" * 65)
    rejects("reject_json_depth_65", lambda: read_json_file(path))
    for name, content in (("duplicate", b'{"a":1,"a":2}'),
                          ("overflow", b'{"a":1e309}'),
                          ("encoding", b"\xffnot_utf8")):
        path = directory / (name + ".json")
        path.write_bytes(content)
        rejects("reject_json_" + name, lambda p=path: read_json_file(p))
    path = directory / "quoted.json"
    value = {"text": "[" * 100 + "a\\\"b" + "]" * 100}
    path.write_text(json.dumps(value))
    accepts("json_quoted_brackets_and_escapes", lambda: read_json_file(path) == value)
    path = directory / "nested_import.json"
    path.write_text("[" * 10000 + "0" + "]" * 10000)
    for name, reader in (("main", read_project), ("ahu", nm_read_project), ("recovery", read_recovery)):
        rejects("controlled_deep_json_" + name, lambda f=reader: f(path))
    path.write_text("[]")
    rejects("controlled_main_json_list", lambda: read_project(path))

    locations = (ROOT.parent, ROOT.parent / "windows", ROOT.parent / "macos",
                 ROOT.parent / "windows/installer/payload")
    if all((location / "LICENSE").is_file() for location in locations):
        copies = [(location / "LICENSE").read_bytes() for location in locations]
        accepts("all_current_license_copies_match", lambda: len(set(copies)) == 1)
        accepts("current_license_has_internal_permission", lambda: all(
            phrase in copies[0].decode() for phrase in ("Internal Business Use", "You may charge for engineering", "PART B")))
        old_copies = [(location / "LICENSE_LEGACY_MIT").read_bytes() for location in locations]
        accepts("all_historical_mit_copies_match", lambda: len(set(old_copies)) == 1
                and old_copies[0].startswith(b"MIT License"))


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(dict(source=ROOT.name, checks=checks,
                                 passed=sum(c["passed"] for c in checks),
                                 failed=[c for c in checks if not c["passed"]]),
                             ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(source=ROOT.name, cases=len(checks),
                     passed=sum(c["passed"] for c in checks),
                     failed=[c for c in checks if not c["passed"]]), ensure_ascii=False))
