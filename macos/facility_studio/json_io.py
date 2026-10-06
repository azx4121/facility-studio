"""Bounded, non-executable JSON reading for imported files and saved settings."""

import json
import math
from pathlib import Path

from .errors import ValidationError

MAX_JSON_BYTES = 15_000_000
MAX_JSON_DEPTH = 64


def _check_depth(text):
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValidationError("JSON 結構超過 64 層，請使用本工具匯出的檔案", code="invalid_json")
        elif char in "]}":
            depth -= 1


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("JSON 欄位重複：" + key[:60], code="invalid_json")
        result[key] = value
    return result


def _constant(value):
    raise ValidationError("JSON 不接受 NaN 或無限大", code="invalid_json")


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError("JSON 數值超過有限範圍", code="invalid_json")
    return result


def read_json_file(path, max_bytes=MAX_JSON_BYTES):
    path = Path(path)
    try:
        with path.open("rb") as file:
            data = file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValidationError("JSON 檔案超過允許大小", code="invalid_json")
        text = data.decode("utf-8-sig")
        _check_depth(text)
        return json.loads(text, parse_constant=_constant, parse_float=_float,
                          object_pairs_hook=_object)
    except ValidationError:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValidationError("JSON 格式、編碼或巢狀結構不合法", code="invalid_json") from error
