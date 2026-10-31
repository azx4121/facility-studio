"""Calculation inputs stored outside the form schema (FIELDS).

Numeric limits are the ones v2 already enforced in engine.validate_project.
No default lives here: an absent or inactive key is left to each reader's own
default (winter.py, quality.py, engine.py, contributions.py), so this module
never introduces a device limit such as a bypass-factor floor.

Keys that already belong to FIELDS (e_up_largest_hp, e_np_largest_hp) are not
optional inputs. FIELDS validation and field_state.main_inactive own their
activation; v2's extra upper limit for them is kept in FIELD_EXTRA_BOUNDS.
"""
from .errors import ValidationError
from .schema import FIELDS
from .utils import number

OPTIONAL_INPUTS = {
    "winter_ffu_ratio": dict(bounds=(0.0, 100.0)),
    "winter_mau_max_t": dict(bounds=(15.0, 60.0)),
    "coil_pinch_min_k": dict(bounds=(0.0, 20.0)),
    "c2_bf_min": dict(bounds=(0.0, 0.5)),
    "airflow_search_floor": dict(bounds=None),
    "e_up_largest_motor_kw": dict(bounds=(0.0, 1e6), pair="e_up_largest_hp"),
    "e_np_largest_motor_kw": dict(bounds=(0.0, 1e6), pair="e_np_largest_hp"),
}
FIELD_EXTRA_BOUNDS = {
    "e_up_largest_hp": (0.0, 1e6),
    "e_np_largest_hp": (0.0, 1e6),
}

if set(OPTIONAL_INPUTS) & set(FIELDS) or not set(FIELD_EXTRA_BOUNDS) <= set(FIELDS):
    raise RuntimeError("optional inputs must not duplicate FIELDS")

ALLOWED_INPUT_KEYS = frozenset(FIELDS) | frozenset(OPTIONAL_INPUTS)


def split_inputs(inputs, form_keys):
    """Separate form-backed values from preserved optional values."""
    form = {k: v for k, v in inputs.items() if k in form_keys}
    extra = {k: v for k, v in inputs.items() if k not in form_keys}
    return form, extra


def check_input_keys(inputs, message):
    """Require every FIELDS key; allow only the listed optional extras."""
    if not isinstance(inputs, dict):
        raise ValidationError(message)
    missing = set(FIELDS) - set(inputs)
    unknown = set(inputs) - ALLOWED_INPUT_KEYS
    if missing or unknown:
        raise ValidationError(message, field_name=sorted(unknown or missing)[0])


def validate_optional_inputs(inputs, main_off, optional_off, exclude=()):
    """Validate active values only; inactive drafts are kept as bounded text."""
    for key, spec in OPTIONAL_INPUTS.items():
        if key not in inputs:
            continue
        value = inputs[key]
        if not isinstance(value, str) or len(value) > 1000:
            raise ValidationError("專案值必須為文字", field_name=key)
        if key in optional_off or key in exclude or spec.get("pair") in exclude:
            continue
        if spec["bounds"] is not None:
            number(value, key, *spec["bounds"])
    for key, bounds in FIELD_EXTRA_BOUNDS.items():
        if key in main_off or key in exclude:
            continue
        number(inputs[key], key, *bounds)
    active_cap = (
        "winter_mau_max_t" in inputs
        and "winter_mau_max_t" not in optional_off
        and "winter_mau_max_t" not in exclude
    )
    if active_cap and "mau_supply_t" not in main_off:
        cap = number(inputs["winter_mau_max_t"], "winter_mau_max_t")
        if cap < number(inputs["mau_supply_t"], "mau_supply_t"):
            raise ValidationError(
                "冬季 MAU 送風上限不得低於 MAU 送風溫度", field_name="winter_mau_max_t"
            )
