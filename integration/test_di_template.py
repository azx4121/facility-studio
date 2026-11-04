"""Read-only DI preview regressions; run each platform in a separate process.

The deliberately small interpreter checks actual template formulas, not Excel
compatibility. Artifact Tool recalculation/render evidence is recorded separately.
"""
import operator
import os
from pathlib import Path
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = os.environ.get("FACILITY_TEST_PLATFORM", "windows")
assert PLATFORM in ("windows", "macos")
sys.path.insert(0, str(ROOT / PLATFORM))
from facility_studio import equipment_analysis
from facility_studio.equipment_io import Cell
from facility_studio.equipment_schema import SCHEMA_ID

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
TOKEN = re.compile(r'\s*("(?:[^"]|"")*"|\d+(?:\.\d*)?|[A-Z]+\d*|<>|<=|>=|[=<>+*/(),-])')
OPERATORS = {"+": operator.add, "-": operator.sub, "*": operator.mul,
             "/": operator.truediv, "=": operator.eq, "<>": operator.ne,
             "<": operator.lt, ">": operator.gt, "<=": operator.le, ">=": operator.ge}


class Formula:
    """Whitelist parser with lazy IF; no eval, Python AST, or external libraries."""

    def __init__(self, formula):
        self.tokens, end = [], 0
        for match in TOKEN.finditer(formula.removeprefix("=")):
            if match.start() != end:
                raise ValueError("Unsupported formula token")
            self.tokens.append(match[1])
            end = match.end()
        if end != len(formula.removeprefix("=")):
            raise ValueError("Unsupported formula suffix")
        self.at = 0
        self.tree = self.expression()
        if self.at != len(self.tokens):
            raise ValueError("Trailing formula tokens")

    def peek(self):
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if token is None or expected is not None and token != expected:
            raise ValueError(f"Expected {expected}, got {token}")
        self.at += 1
        return token

    def expression(self, level=0):
        if level == 3:
            return self.atom()
        allowed = (("=", "<>", "<", ">", "<=", ">="), ("+", "-"), ("*", "/"))[level]
        node = self.expression(level + 1)
        while self.peek() in allowed:
            op = self.take()
            node = (op, node, self.expression(level + 1))
        return node

    def atom(self):
        token = self.take()
        if token == "(":
            node = self.expression()
            self.take(")")
            return node
        if token in ("+", "-"):
            return (token, ("value", 0), self.atom())
        if token.startswith('"'):
            return ("value", token[1:-1].replace('""', '"'))
        if token[0].isdigit():
            return ("value", float(token))
        if re.fullmatch(r"[A-Z]+\d+", token):
            return ("cell", token)
        if token not in ("IF", "ISNUMBER"):
            raise ValueError(f"Unsupported formula function: {token}")
        self.take("(")
        args = [self.expression()]
        while self.peek() == ",":
            self.take(",")
            args.append(self.expression())
        self.take(")")
        if len(args) != (3 if token == "IF" else 1):
            raise ValueError("Invalid function arity")
        return (token, *args)

    def calculate(self, cells):
        def visit(node):
            op, *args = node
            if op == "value":
                return args[0]
            if op == "cell":
                return cells.get(args[0], "")
            if op == "IF":
                return visit(args[1] if visit(args[0]) else args[2])
            if op == "ISNUMBER":
                return type(visit(args[0])) in (int, float)
            left, right = visit(args[0]), visit(args[1])
            if op in ("+", "-", "*", "/"):
                left, right = (0 if v in (None, "") else v for v in (left, right))
            else:
                left, right = ("" if v is None else v for v in (left, right))
            return OPERATORS[op](left, right)
        return visit(self.tree)


def read_formulas(platform):
    path = ROOT / platform / "facility_studio/resources/Equipment_Template.xlsx"
    with zipfile.ZipFile(path) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        sheet = next(s for s in workbook.findall("m:sheets/m:sheet", NS) if s.attrib["name"] == "DI")
        relation = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        links = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = next(r.attrib["Target"] for r in links if r.attrib["Id"] == relation)
        member = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        xml = ET.fromstring(book.read(member))
        return {cell.attrib["r"]: cell.find("m:f", NS).text
                for cell in xml.findall(".//m:c", NS) if cell.find("m:f", NS) is not None}


@pytest.fixture(scope="module")
def formulas():
    return {address: Formula(text) for address, text in read_formulas(PLATFORM).items()}


def preview(formulas, row, values):
    cells = {f"{column}{row}": value for column, value in values.items()}
    output = []
    for column in ("L", "M"):
        address = f"{column}{row}"
        cells[address] = formulas[address].calculate(cells)
        output.append(cells[address])
    return output


def engine(flow, unit, usage, circulation=2):
    inputs = dict(enabled=1, id="TEST", name="Test", group="DI-01", quantity=2,
                  usage=usage, flow=flow, unit=unit, circulation=circulation)
    imported = dict(schema_id=SCHEMA_ID, source_name="DI regression",
                    records=[dict(system="DI", row=6, cells={k: Cell(value=v) for k, v in inputs.items()})])
    group = equipment_analysis.analyze_equipment(imported)["groups"][0]
    return [group["connected_lpm"], group["demand_lpm"]]


def test_platform_and_template_parity():
    assert Path(equipment_analysis.__file__).resolve().is_relative_to(ROOT / PLATFORM)
    windows, macos = read_formulas("windows"), read_formulas("macos")
    assert windows == macos
    for row in range(6, 106):
        for col in ("L", "M"):
            assert f"{col}{row}" in windows
            # All rows must use the same logic, with correctly shifted references.
            normalized = re.sub(r"([A-Z]+)\d+", r"\1ROW", windows[f"{col}{row}"])
            assert normalized == re.sub(r"([A-Z]+)\d+", r"\1ROW", windows[f"{col}6"])


@pytest.mark.parametrize("row", [6, 55, 105])
@pytest.mark.parametrize("unit,factor", [("LPM", 1), ("US GPM", 3.785411784), ("m³/h", 1000/60), ("L/s", 60)])
@pytest.mark.parametrize("usage", [0, 50, 100])
def test_preview_matches_equipment_engine(formulas, row, unit, factor, usage):
    values = dict(A=1, B="TEST", E=2, F=usage, G=10/factor, H=unit, I=2)
    actual_lpm = [value * factor for value in preview(formulas, row, values)]
    assert actual_lpm == pytest.approx([24, 20*usage/100+4], rel=1e-12, abs=1e-9)
    assert actual_lpm == pytest.approx(engine(10/factor, unit, usage), rel=1e-12, abs=1e-9)


@pytest.mark.parametrize("row", [6, 55, 105])
@pytest.mark.parametrize("change,expected", [
    ({"A": 0}, [0, 0]),
    ({"A": 0, "G": None}, [0, 0]),
    ({"B": None}, ["", ""]),
    ({"I": None}, [20, 10]),
    ({"G": None}, ["待填需求", "待填需求"]),
    ({"G": 0}, [4, 4]),
    ({"E": None, "F": None}, [12, 12]),
])
def test_preview_boundaries(formulas, row, change, expected):
    values = dict(A=1, B="TEST", E=2, F=50, G=10, H="LPM", I=2)
    values.update(change)
    assert preview(formulas, row, values) == expected


def test_interpreter_rejects_unsupported_syntax_and_short_circuits():
    assert Formula('IF(1=1,"safe",1/0)').calculate({}) == "safe"
    for formula in ('SUM(A1)', '__import__("os")', 'A1!B2', 'IF(1,2)', '1**2'):
        with pytest.raises(ValueError):
            Formula(formula)
