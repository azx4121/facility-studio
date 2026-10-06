"""Optional independent comparison against unmodified PsychroLib 2.5.0."""

import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.quick_tools import psychrometric

try:
    import psychrolib
except ImportError:
    raise SystemExit("此參考測試需先執行：python -m pip install psychrolib==2.5.0")

psychrolib.SetUnitSystem(psychrolib.SI)
checks = []
conditions = list(itertools.product(
    (-50, -20, -1, 0, 0.01, 1, 15, 22, 35, 45, 60),
    (1, 10, 50, 70, 99, 100), (60, 80, 101.325, 120)
))

for t, rh, p in conditions:
    state = psychrometric("乾球＋RH", t, rh, p)
    w = psychrolib.GetHumRatioFromRelHum(t, rh / 100, p * 1000)
    expected = {
        "w": w,
        "h": psychrolib.GetMoistAirEnthalpy(t, w) / 1000,
        "v_da": psychrolib.GetMoistAirVolume(t, w, p * 1000),
        "wetbulb_c": psychrolib.GetTWetBulbFromRelHum(t, rh / 100, p * 1000),
        "dewpoint_c": psychrolib.GetTDewPointFromRelHum(t, rh / 100),
    }
    # PsychroLib uses 1.607858; this model uses 1 / 0.621945.
    # Allow exactly that coefficient-rounding difference, plus float noise.
    volume_rounding = abs(
        0.287042 * (t + 273.15) / p * w * (1 / 0.621945 - 1.607858)
    )
    tolerance = {
        "w": 1e-10, "h": 1e-8, "v_da": volume_rounding + 1e-12,
        "wetbulb_c": 0.002, "dewpoint_c": 0.002,
    }
    for name, reference in expected.items():
        error = abs(state[name] - reference)
        checks.append(dict(
            dry_bulb_c=t, rh_percent=rh, pressure_kpa=p, quantity=name,
            actual=state[name], reference=reference, absolute_error=error,
            tolerance=tolerance[name], passed=error <= tolerance[name],
        ))

failed = [record for record in checks if not record["passed"]]
record = dict(
    reference="PsychroLib 2.5.0 SI",
    reference_source="https://github.com/psychrometrics/psychrolib",
    conditions=len(conditions), checks=checks, failed=len(failed),
    volume_tolerance_basis="僅容許1/0.621945與1.607858的係數取位差，加1e-12浮點誤差",
    max_absolute_errors={
        name: max(c["absolute_error"] for c in checks if c["quantity"] == name)
        for name in tolerance
    },
)
(ROOT / "evidence/Reference_Psychrometrics.json").write_text(
    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
)
assert not failed, failed[:5]
print(f"{len(conditions)} independent reference conditions; {len(checks)} checks passed")
