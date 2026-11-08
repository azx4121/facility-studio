"""Real Windows template export/reimport; source checks, not native EXE evidence."""
import os
from pathlib import Path
import posixpath
import sys
import xml.etree.ElementTree as ET
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = os.environ.get("FACILITY_TEST_PLATFORM", "windows")
sys.path.insert(0, str(ROOT / PLATFORM))
from facility_studio import equipment_io, i18n
from facility_studio.equipment_analysis import analyze_equipment, validate_rows
from facility_studio.equipment_io import EquipmentImportError, export_template, load_equipment
from facility_studio.template_language import export_english_excel

pytestmark = pytest.mark.skipif(PLATFORM != "windows", reason="Windows-only candidate label fix")
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
SYSTEMS = ["電力", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV"]


@pytest.fixture(autouse=True)
def restore_language():
    assert Path(equipment_io.__file__).resolve() == ROOT / "windows/facility_studio/equipment_io.py"
    before = i18n.language()
    yield
    i18n.set_language(before, persist=False)


def sheet_names(path):
    with zipfile.ZipFile(path) as archive:
        tree = ET.fromstring(archive.read("xl/workbook.xml"))
    return [sheet.get("name") for sheet in tree.findall("s:sheets/s:sheet", NS)]


def enable_sample(source, destination, sheet_name):
    """Change only the selected example's A6, preserving every other ZIP member."""
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as target:
        workbook = ET.fromstring(original.read("xl/workbook.xml"))
        sheet = next(node for node in workbook.findall("s:sheets/s:sheet", NS)
                     if node.get("name") == sheet_name)
        rels = ET.fromstring(original.read("xl/_rels/workbook.xml.rels"))
        relative = next(node.get("Target") for node in rels if node.get("Id") == sheet.get(RID))
        member = relative.lstrip("/") if relative.startswith("/") else posixpath.normpath("xl/" + relative)
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename == member:
                tree = ET.fromstring(data)
                cell = tree.find(".//s:c[@r='A6']", NS)
                assert cell is not None and cell.find("s:f", NS) is None
                value = cell.find("s:v", NS)
                assert value is not None and value.text == "0"
                value.text = "1"
                data = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
            target.writestr(item, data)
    return destination


@pytest.mark.parametrize("lang,title,electrical", [
    ("en", "Instructions", "Electrical"), ("zh-Hant", "填寫說明", "電力"),
])
def test_real_export_titles_and_disabled_sample_guard(tmp_path, lang, title, electrical):
    source = ROOT / "windows/facility_studio/resources/Equipment_Template.xlsx"
    before = source.read_bytes()
    i18n.set_language(lang, persist=False)
    path = export_template(tmp_path / (lang + ".xlsx"))
    assert sheet_names(path) == [title, electrical, *SYSTEMS[1:]]
    imported = load_equipment(path)
    assert imported["systems"] == SYSTEMS
    assert [row["system"] for row in imported["records"]] == SYSTEMS
    assert all(row["cells"]["enabled"].value == "0" for row in imported["records"])
    with pytest.raises(EquipmentImportError, match="沒有啟用的設備"):
        analyze_equipment(imported)
    assert source.read_bytes() == before
    if lang == "zh-Hant":
        assert path.read_bytes() == before


@pytest.mark.parametrize("lang", ["en", "zh-Hant"])
@pytest.mark.parametrize("system", SYSTEMS)
def test_each_system_can_reimport_one_explicitly_enabled_sample(tmp_path, lang, system):
    i18n.set_language(lang, persist=False)
    template = export_template(tmp_path / "template.xlsx")
    before = template.read_bytes()
    sheet = "Electrical" if lang == "en" and system == "電力" else system
    active = enable_sample(template, tmp_path / "active.xlsx", sheet)
    imported = load_equipment(active)
    assert imported["systems"] == SYSTEMS
    rows, skipped = validate_rows(imported)
    assert [row["system"] for row in rows] == [system]
    assert skipped == 6
    assert sheet_names(active) == sheet_names(template)
    assert template.read_bytes() == before
    if system == "電力":
        result = analyze_equipment(imported)
        assert result["active_records"] == 1 and result["skipped_records"] == 6
        assert [group["system"] for group in result["groups"]] == [system]
        assert result["totals"]["connected_kw"] == pytest.approx(10)
        candidate = result["groups"][0]["candidate"]
        assert candidate["selection_status"] == "blocked_unverified_ampacity_basis"
        assert candidate["selected"] is None


def test_exact_title_catalog_translation_preserves_generic_and_longer_labels():
    assert i18n.translate("填寫說明", "en") == "Instructions"
    assert i18n.translate("填寫說明", "zh-Hant") == "填寫說明"
    assert i18n.translate("說明", "en") == "Description"
    assert i18n.translate("設備需求表填寫說明", "en") == "Equipment schedule instructions"


def test_title_translation_does_not_change_generic_description(tmp_path):
    source, destination = tmp_path / "source.xlsx", tmp_path / "english.xlsx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("xl/workbook.xml", '<workbook xmlns="' + NS["s"] + '"><sheets>'
                         '<sheet name="填寫說明"/><sheet name="說明"/>'
                         '</sheets></workbook>')
        archive.writestr("preserved.bin", b"unchanged\x00\xff")
    before = source.read_bytes()
    export_english_excel(source, destination)
    assert sheet_names(destination) == ["Instructions", "Description"]
    assert i18n.translate("說明", "en") == "Description"
    with zipfile.ZipFile(destination) as archive:
        assert archive.read("preserved.bin") == b"unchanged\x00\xff"
    assert source.read_bytes() == before
