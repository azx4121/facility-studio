"""Versioned reference tables. Legacy values are not a compliance certification."""

from pathlib import Path
import json
import math
from .json_io import read_json_file
from .errors import ValidationError


def load_tables(path=None):
    path = (
        Path(path)
        if path
        else Path(__file__).with_name("resources") / "engineering_tables.json"
    )
    try:
        doc = read_json_file(path)
    except (OSError, UnicodeError, ValueError) as error:
        raise ValidationError(
            "工程資料表無法讀取；請確認檔案存在、UTF-8 編碼及 JSON 格式",
            code="invalid_database",
        ) from error
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
        not isinstance(doc, dict)
        or type(doc.get("schema_version")) is not int
        or doc.get("schema_version") != 1
        or not isinstance(doc.get("tables"), dict)
        or set(doc["tables"]) != expected
        or any(
            not isinstance(doc.get(key), str) or not doc[key].strip()
            for key in ("source", "version")
        )
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
                if key in {"name", "size"}:
                    if not isinstance(value, str) or not value.strip():
                        raise ValidationError(
                            name + " 規格名稱必須為非空白文字",
                            code="invalid_database",
                        )
                elif not positive(value):
                    raise ValidationError(
                        name + " 數值必須有限且大於零", code="invalid_database"
                    )
    sizes = doc["tables"]["NFB_SIZES"]
    if (
        not isinstance(sizes, list)
        or not sizes
        or any(not positive(v) for v in sizes)
        or sorted(set(sizes)) != sizes
    ):
        raise ValidationError("NFB 額定排序不合法", code="invalid_database")
    for name in ["VOLTAGE_MAP", "GAS_DESIGN_VELOCITY_MPS"]:
        values = doc["tables"][name]
        if not isinstance(values, dict) or not values or any(
            not isinstance(key, str) or not key.strip() or not positive(value)
            for key, value in values.items()
        ):
            raise ValidationError(name + " 資料不合法", code="invalid_database")
    cleanrooms = doc["tables"]["CLEANROOM_DB"]
    if not isinstance(cleanrooms, dict) or not cleanrooms:
        raise ValidationError("潔淨參考表不可空白且須為對照表", code="invalid_database")
    for key, row in cleanrooms.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(row, dict)
            or set(row) != {"ach", "pressure"}
            or any(
                not isinstance(v, (int, float))
                or isinstance(v, bool)
                or not math.isfinite(v)
                or v < 0
                for v in row.values()
            )
        ):
            raise ValidationError("潔淨參考表不合法", code="invalid_database")
    return doc
