"""Translate a trusted bundled schedule, preserving types, formulas and styles."""

import csv
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from .i18n import translate


def export_english_excel(source, destination):
    """Only the application-owned template is read, never an imported workbook."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(
        destination, "w", zipfile.ZIP_DEFLATED
    ) as target:
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename.endswith(".xml"):
                tree = ET.fromstring(data)
                # Only the two application-owned electrical instruction cells.
                # Stored-string <v> values are not shared/inline <t> nodes.
                # Never reinterpret numeric cells or formula results as text.
                if item.filename == "xl/worksheets/sheet1.xml":
                    for cell in tree.iter():
                        if (cell.tag.rsplit("}", 1)[-1] == "c"
                            and cell.get("r") in {"B13", "B25"}
                            and cell.get("t") == "str"
                            and not any(child.tag.rsplit("}", 1)[-1] == "f" for child in cell)):
                            for child in cell:
                                if child.tag.rsplit("}", 1)[-1] == "v" and child.text:
                                    child.text = translate(child.text, "en")
                for element in tree.iter():
                    tag = element.tag.rsplit("}", 1)[-1]
                    if tag == "t" and element.text:
                        element.text = translate(element.text, "en")
                    elif tag == "sheet" and "name" in element.attrib:
                        name = element.get("name")
                        # This template tab needs a whole-label translation;
                        # the generic catalog uses 說明 for Description elsewhere.
                        element.set("name", "Instructions" if name == "填寫說明"
                                    else translate(name, "en"))
                    elif tag in ("formula1", "f") and element.text:
                        # Only quoted display strings change, not cell references,
                        # operators, numeric constants or formula functions.
                        import re

                        element.text = re.sub(
                            r'"([^"]*)"',
                            lambda match: '"' + translate(match.group(1), "en") + '"',
                            element.text,
                        )
                    elif tag == "row" and element.get("r") == "5":
                        element.set("ht", "54")
                        element.set("customHeight", "1")
                data = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
            target.writestr(item, data)
    return destination


def export_english_csv(source, destination, systems):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for system in systems:
        with (Path(source) / (system + ".csv")).open(
            encoding="utf-8-sig", newline=""
        ) as file:
            rows = list(csv.reader(file))
        output = destination / (translate(system, "en") + ".csv")
        with output.open("w", encoding="utf-8-sig", newline="") as file:
            csv.writer(file).writerows(
                [[translate(value, "en") for value in row] for row in rows]
            )
    return destination
