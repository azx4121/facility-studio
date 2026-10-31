"""Shared helpers for the FEED stress campaign. Reads the product; never imports its test code."""
import copy
import math
import sys
import traceback
from pathlib import Path

sys.path.insert(0, ".")
from facility_studio import api, i18n  # noqa: E402
from facility_studio.errors import ValidationError  # noqa: E402
from facility_studio.schema import FIELDS, default_project  # noqa: E402

DEFAULT = default_project()["inputs"]
NUMERIC = {k: f for k, f in FIELDS.items() if f.get("low") is not None and f.get("high") is not None}
OPTIONS = {k: f for k, f in FIELDS.items() if f.get("options")}
SYSTEMS = FIELDS["sys_type"]["options"]


def project(**overrides):
    p = default_project()
    for key, value in overrides.items():
        p["inputs"][key] = value if isinstance(value, str) else format(value, ".12g")
    return p


def run(**overrides):
    """-> ('ok', result) | ('reject', ValidationError) | ('crash', traceback text)."""
    try:
        return "ok", api.calculate(project(**overrides))
    except ValidationError as exc:
        return "reject", exc
    except Exception:  # noqa: BLE001 - a crash is the finding
        return "crash", traceback.format_exc(limit=4)


def numbers(value, path=""):
    """Every float in a nested result, with its path."""
    if isinstance(value, float):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from numbers(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from numbers(v, f"{path}[{i}]")


def bad_numbers(result):
    return [(p, v) for p, v in numbers(result) if not math.isfinite(v)]


def states(result):
    """Every moist-air state dict (has t, w, h, rh, v_da) in the result, with its path."""
    def walk(value, path):
        if isinstance(value, dict):
            if {"t", "w", "h", "rh", "v_da"} <= value.keys() and all(isinstance(value[k], (int, float)) for k in ("t", "w", "h", "rh", "v_da")):
                yield path, value
            for k, v in value.items():
                if k not in ("project", "effective_inputs"):
                    yield from walk(v, f"{path}.{k}")
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                yield from walk(v, f"{path}[{i}]")
    yield from walk(result, "")
