"""Read typed Excel/CSV inputs without Excel, macros or formula execution."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import csv
import io
import json
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

from .equipment_schema import HEADER_ROW, SCHEMAS, SCHEMA_ID, SYSTEMS, DERIVED_HEADERS
from .errors import ValidationError
from .utils import atomic_text

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_XML_BYTES = 40 * 1024 * 1024
MAX_ROWS = 10000
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


@dataclass(frozen=True)
class Cell:
    value: object = None
    formula: bool = False
    excel_error: bool = False


class EquipmentImportError(ValidationError):
    def __init__(self, message, system=None, row=None, column=None):
        location = f"{system or '檔案'}"
        if row is not None:
            location += f"第{row}列"
        if column:
            location += f"／{column}"
        super().__init__(f"{location}：{message}", column, "equipment_import")
        self.system, self.row, self.column = system, row, column


def _xml(archive, path):
    try:
        data = archive.read(path)
    except KeyError:
        raise EquipmentImportError(f"Excel缺少必要內容：{path}") from None
    if len(data) > MAX_XML_BYTES or b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise EquipmentImportError("XML內容過大或含外部實體宣告")
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        raise EquipmentImportError("Excel XML內容損壞") from None


def _column_index(reference):
    if not re.fullmatch(r"[A-Za-z]+[1-9][0-9]*", reference):
        raise EquipmentImportError("Excel儲存格位置損壞")
    letters = "".join(c for c in reference if "A" <= c.upper() <= "Z")
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - 64
    if not letters or index < 1 or index > 128:
        raise EquipmentImportError("輸入欄位超過支援範圍（128欄）")
    return index - 1


def _xlsx_sheets(path):
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise EquipmentImportError("不是有效.xlsx檔；請另存為Excel活頁簿") from None
    with archive:
        records = archive.infolist()
        if len(records) > 3000 or sum(r.file_size for r in records) > MAX_XML_BYTES:
            raise EquipmentImportError("Excel解壓內容過大")
        if len({r.filename for r in records}) != len(records):
            raise EquipmentImportError("Excel含重複封存項目")
        if any("vbaProject" in r.filename for r in records):
            raise EquipmentImportError("不接受含巨集的活頁簿，請另存無巨集.xlsx")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for entry in _xml(archive, "xl/sharedStrings.xml").findall("s:si", NS):
                strings.append(
                    "".join(t.text or "" for t in entry.iterfind(".//s:t", NS))
                )
        book = _xml(archive, "xl/workbook.xml")
        rels = _xml(archive, "xl/_rels/workbook.xml.rels")
        destinations = {}
        for rel in rels:
            target = rel.get("Target", "")
            if rel.get("TargetMode") == "External":
                continue
            relative = PurePosixPath(target.lstrip("/"))
            if ".." in relative.parts or "\\" in target:
                raise EquipmentImportError("Excel含不安全的工作表路徑")
            destinations[rel.get("Id")] = (
                target.lstrip("/") if target.startswith("/") else "xl/" + target
            )
        result = {}
        for sheet in book.findall("s:sheets/s:sheet", NS):
            name = sheet.get("name")
            if name not in SYSTEMS:
                continue
            if name in result:
                raise EquipmentImportError("系統工作表重複", name)
            destination = destinations.get(sheet.get(REL))
            if destination is None:
                raise EquipmentImportError("工作表連結缺少或為外部連結", name)
            rows = {}
            tree = _xml(archive, destination)
            for row in tree.findall("s:sheetData/s:row", NS):
                try:
                    row_number = int(row.get("r", "0"))
                except ValueError:
                    raise EquipmentImportError("工作表列號損壞", name) from None
                # Allow the field-help section below the 10,000 equipment rows.
                if not 1 <= row_number <= MAX_ROWS + HEADER_ROW + 100:
                    raise EquipmentImportError(f"每張系統表最多{MAX_ROWS}筆資料", name)
                if row_number in rows:
                    raise EquipmentImportError("工作表列號重複", name, row_number)
                cells = {}
                for cell in row.findall("s:c", NS):
                    index = _column_index(cell.get("r", ""))
                    if int(re.search(r"[0-9]+$", cell.get("r")).group()) != row_number:
                        raise EquipmentImportError(
                            "儲存格與所在列號不一致", name, row_number
                        )
                    if index in cells:
                        raise EquipmentImportError(
                            "同一列的儲存格位置重複", name, row_number
                        )
                    kind = cell.get("t")
                    value = cell.findtext("s:v", default=None, namespaces=NS)
                    if kind == "s":
                        try:
                            string_index = int(value)
                            if string_index < 0:
                                raise IndexError
                            value = strings[string_index]
                        except (IndexError, TypeError, ValueError):
                            raise EquipmentImportError(
                                "共用文字索引損壞", name, row_number
                            ) from None
                    elif kind == "inlineStr":
                        value = "".join(
                            t.text or "" for t in cell.iterfind(".//s:is//s:t", NS)
                        )
                    elif kind == "b":
                        value = value == "1"
                    cells[index] = Cell(
                        value, cell.find("s:f", NS) is not None, kind == "e"
                    )
                rows[row_number] = cells
            result[name] = rows
        if not result:
            raise EquipmentImportError(
                "找不到電力／PCW／CDA／N2／EXHAUST／DI／PV工作表；請使用公版範本"
            )
        return result


def _mapped_rows(system, rows, header_row):
    schema = SCHEMAS[system]
    labels = {c["label"]: c["key"] for c in schema}
    headers = rows.get(header_row, {})
    mapping = {}
    derived_indices = set()
    seen = set()
    for index, cell in headers.items():
        label = str(cell.value or "").strip()
        if not label:
            continue
        if label in DERIVED_HEADERS and not cell.formula:
            derived_indices.add(index)
            continue
        if cell.formula or label not in labels:
            raise EquipmentImportError(
                "未知或公式欄名；請保留範本欄名", system, header_row, label
            )
        key = labels[label]
        if key in seen:
            raise EquipmentImportError("欄名重複", system, header_row, label)
        seen.add(key)
        mapping[index] = key
    missing = [c["label"] for c in schema if c["required"] and c["key"] not in seen]
    if missing or "enabled" not in seen:
        raise EquipmentImportError(
            "缺少欄位：" + "、".join(missing or ["啟用(1/0)"]), system, header_row
        )
    result = []
    for row_number, values in sorted(rows.items()):
        if row_number <= header_row:
            continue
        if (values.get(0, Cell()).value, values.get(1, Cell()).value) == (
            "欄位",
            "填寫提示",
        ):
            break
        mapped = {key: values.get(index, Cell()) for index, key in mapping.items()}
        if not any(
            cell.value not in (None, "") or cell.formula for cell in mapped.values()
        ):
            continue
        if any(
            cell.value not in (None, "")
            for index, cell in values.items()
            if index not in mapping and index not in derived_indices
        ):
            raise EquipmentImportError("無欄名的欄位含資料", system, row_number)
        result.append({"system": system, "row": row_number, "cells": mapped})
        if len(result) > MAX_ROWS:
            raise EquipmentImportError(
                f"每張系統表最多{MAX_ROWS}筆資料", system, row_number
            )
    return result


def load_equipment(path, csv_system="電力"):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise EquipmentImportError("檔案不存在或超過20MB")
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        data = _xlsx_sheets(path)
        records = [
            record
            for system, rows in data.items()
            for record in _mapped_rows(system, rows, HEADER_ROW)
        ]
        present = list(data)
    elif suffix == ".csv":
        if csv_system not in SYSTEMS:
            raise EquipmentImportError("CSV必須指定系統")
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp950")
            except UnicodeDecodeError:
                raise EquipmentImportError("CSV請使用UTF-8或繁體中文編碼") from None
        parsed = list(csv.reader(io.StringIO(text)))
        if len(parsed) > MAX_ROWS + 1:
            raise EquipmentImportError(f"CSV最多{MAX_ROWS}筆資料")
        if any(len(row) > 128 for row in parsed):
            raise EquipmentImportError("CSV輸入欄位超過支援範圍（128欄）")
        rows = {
            i: {
                j: Cell(value, value.lstrip().startswith("="))
                for j, value in enumerate(row)
            }
            for i, row in enumerate(parsed, 1)
        }
        records = _mapped_rows(csv_system, rows, 1)
        present = [csv_system]
    else:
        raise EquipmentImportError("僅接受.xlsx或.csv；.xls／巨集檔請另存.xlsx")
    return dict(
        schema_id=SCHEMA_ID, source_name=path.name, systems=present, records=records
    )


def export_template(destination):
    source = Path(__file__).with_name("resources") / "Equipment_Template.xlsx"
    destination = Path(destination)
    if not source.is_file():
        raise EquipmentImportError("安裝缺少設備Excel範本")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copyfile(source, destination)
    return destination


def export_csv_templates(destination):
    source = Path(__file__).with_name("resources") / "equipment_csv"
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for system in SYSTEMS:
        shutil.copyfile(source / (system + ".csv"), destination / (system + ".csv"))
    return destination


def save_equipment_result(path, result):
    atomic_text(path, json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
