"""Versioned reference tables. Legacy values are not a compliance certification."""

from pathlib import Path
import json
import math
from .errors import ValidationError


def load_tables(path=None):
    path = (
        Path(path)
        if path
        else Path(__file__).with_name("resources") / "engineering_tables.json"
    )
    doc = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "WIRE_DB",
        "PIPE_DB",
        "HVAC_PIPES",
        "NFB_SIZES",
        "VOLTAGE_MAP",
        "GAS_DESIGN_VELOCITY_MPS",
        "CLEANROOM_DB",
    }
    if (
        doc.get("schema_version") != 1
        or set(doc.get("tables", {})) != expected
        or not doc.get("source")
        or not doc.get("version")
    ):
        raise ValidationError(
            "工程資料表版本、來源或欄位不完整", code="invalid_database"
        )

    def positive(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value > 0
        )

    for name, size, required in [
        ("WIRE_DB", "size_mm2", {"size_mm2", "PVC_A", "XLPE_A"}),
        ("PIPE_DB", "id", {"id", "name"}),
        ("HVAC_PIPES", "id_mm", {"id_mm", "size", "max_flow_lpm"}),
    ]:
        rows = doc["tables"][name]
        if not isinstance(rows, list) or not rows:
            raise ValidationError(name + " 資料表不可空白", code="invalid_database")
        last = 0
        for row in rows:
            if (
                not isinstance(row, dict)
                or set(row) != required
                or not positive(row[size])
                or row[size] <= last
            ):
                raise ValidationError(
                    name + " 欄位或尺寸排序不合法", code="invalid_database"
                )
            last = row[size]
            for key, value in row.items():
                if key not in {"name", "size"} and not positive(value):
                    raise ValidationError(
                        name + " 數值必須有限且大於零", code="invalid_database"
                    )
    sizes = doc["tables"]["NFB_SIZES"]
    if not sizes or any(not positive(v) for v in sizes) or sorted(set(sizes)) != sizes:
        raise ValidationError("NFB 額定排序不合法", code="invalid_database")
    for name in ["VOLTAGE_MAP", "GAS_DESIGN_VELOCITY_MPS"]:
        if not doc["tables"][name] or any(
            not positive(v) for v in doc["tables"][name].values()
        ):
            raise ValidationError(name + " 資料不合法", code="invalid_database")
    for row in doc["tables"]["CLEANROOM_DB"].values():
        if set(row) != {"ach", "pressure"} or any(
            not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
            for v in row.values()
        ):
            raise ValidationError("潔淨參考表不合法", code="invalid_database")
    return doc
