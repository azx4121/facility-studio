"""Feeder design demand for one panel group.

A group is one panel (UP or NP) at one line voltage; the ledger rejects sources
at any other voltage, so every part shares the divisor sqrt(3) x V.
Applied rule for the same feeder group:
    design = 1.25 x non-motor continuous + 1.00 x other non-motor
           + 1.00 x all motors + 0.25 x the single largest motor of the group
P and Q are summed separately, so every part keeps its own power factor.

A source states its composition at its demand basis (same P/Q as kw/kvar).
largest_motor is the rated single-unit motor used for the 25 % allowance; it
may exceed the motor demand when the source applied a usage factor below 100 %.
"""
import math
from .errors import ValidationError

PARTS = ("continuous", "noncontinuous", "motor", "largest_motor")
COMPOSITION_KEYS = frozenset(f"{part}_{unit}" for part in PARTS for unit in ("kw", "kvar"))
CONTINUOUS_FACTOR = 1.25
LARGEST_MOTOR_ADD = 0.25
_TOL = 1e-6


def make_composition(continuous=(0.0, 0.0), noncontinuous=(0.0, 0.0), motor=(0.0, 0.0), largest_motor=(0.0, 0.0)):
    parts = dict(continuous=continuous, noncontinuous=noncontinuous, motor=motor, largest_motor=largest_motor)
    return {f"{name}_{unit}": float(pair[n]) for name, pair in parts.items() for n, unit in enumerate(("kw", "kvar"))}


def composition_design(comp):
    """Design P/Q of one classified source on its own."""
    p = (CONTINUOUS_FACTOR * comp["continuous_kw"] + comp["noncontinuous_kw"] + comp["motor_kw"]
         + LARGEST_MOTOR_ADD * comp["largest_motor_kw"])
    q = (CONTINUOUS_FACTOR * comp["continuous_kvar"] + comp["noncontinuous_kvar"] + comp["motor_kvar"]
         + LARGEST_MOTOR_ADD * comp["largest_motor_kvar"])
    return p, q


def _close(a, b):
    return abs(a - b) <= _TOL * max(1.0, abs(a), abs(b))


def validate_composition(comp, power):
    """Reject a composition that does not describe the same source P/Q and design."""
    if not isinstance(comp, dict) or set(comp) != COMPOSITION_KEYS:
        raise ValidationError("盤別負載分類格式不符")
    for value in comp.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1e9:
            raise ValidationError("盤別負載分類數值不合法")
    for unit in ("kw", "kvar"):
        total = comp["continuous_" + unit] + comp["noncontinuous_" + unit] + comp["motor_" + unit]
        if not _close(total, power[unit]):
            raise ValidationError("盤別負載分類合計與來源運轉 P／Q 不符")
    if comp["motor_kw"] > _TOL and comp["largest_motor_kw"] <= 0:
        raise ValidationError("有馬達負載時必須指明最大單台馬達")
    design_kw, design_kvar = composition_design(comp)
    if not (_close(design_kw, power["design_kw"]) and _close(design_kvar, power["design_kvar"])):
        raise ValidationError("盤別負載分類與來源設計 P／Q 不符")


def group_design(parts):
    """parts: dicts with name, design_kw, design_kvar and composition (or None).

    Unclassified parts contribute their own design P/Q unchanged; they cannot
    join the largest-motor selection, so the result stays conservative.
    """
    p = q = 0.0
    largest = (0.0, 0.0, None)
    unclassified = []
    for part in parts:
        comp = part.get("composition")
        if comp is None:
            p += part["design_kw"]
            q += part["design_kvar"]
            unclassified.append(part["name"])
            continue
        p += CONTINUOUS_FACTOR * comp["continuous_kw"] + comp["noncontinuous_kw"] + comp["motor_kw"]
        q += CONTINUOUS_FACTOR * comp["continuous_kvar"] + comp["noncontinuous_kvar"] + comp["motor_kvar"]
        if math.hypot(comp["largest_motor_kw"], comp["largest_motor_kvar"]) > math.hypot(largest[0], largest[1]):
            largest = (comp["largest_motor_kw"], comp["largest_motor_kvar"], part["name"])
    p += LARGEST_MOTOR_ADD * largest[0]
    q += LARGEST_MOTOR_ADD * largest[1]
    return dict(design_kw=p, design_kvar=q, largest_motor_kw=largest[0], largest_motor_kvar=largest[1],
                largest_motor_source=largest[2], unclassified=unclassified)


def design_current_a(p_kw, q_kvar, voltage):
    return math.hypot(p_kw, q_kvar) * 1000 / (math.sqrt(3) * voltage)


def base_composition(rows, kind, largest_kw, pf):
    """Classify the panel's untouched base rows; return (composition, pending or None).

    rows: (kw, entered_in_hp) per base value. kind is the panel type saved before
    the first adoption. largest_kw counts only when the panel form uses it.
    """
    tan_phi = math.tan(math.acos(pf))
    total = sum(kw for kw, _ in rows)
    hp_total = sum(kw for kw, hp in rows if hp)
    pending = None
    if kind == "連續負載":
        continuous, noncontinuous, motor = total, 0.0, 0.0
    elif kind == "馬達負載":
        continuous, noncontinuous, motor = 0.0, 0.0, total
    elif kind == "一般負載":
        continuous, noncontinuous, motor = 0.0, total - hp_total, hp_total
    else:
        continuous, noncontinuous, motor = total, 0.0, 0.0
        pending = f"原盤負載類型「{kind}」無法辨識，基底暫以非馬達連續負載 125% 計，請確認盤型。"
    largest = 0.0
    if motor > _TOL:
        if largest_kw > 0:
            largest = min(largest_kw, motor)
        else:
            largest = max(kw for kw, hp in rows if kw > 0 and (hp or kind == "馬達負載"))
            pending = "原盤最大單台馬達未填：暫以最大一列馬達負荷 " + format(largest, ".6g") + " kW 視為單台（上界），請補最大馬達 kW／HP。"
    comp = make_composition(
        continuous=(continuous, continuous * tan_phi),
        noncontinuous=(noncontinuous, noncontinuous * tan_phi),
        motor=(motor, motor * tan_phi),
        largest_motor=(largest, largest * tan_phi),
    )
    return comp, pending
