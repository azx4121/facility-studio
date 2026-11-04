"""Airflow advice must not promise an unverified water-only remedy."""
import math
import os
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / os.environ.get("FACILITY_TEST_PLATFORM", "macos")))
from facility_studio import airflow_guard, api, i18n
from facility_studio.errors import ValidationError


def project(**changes):
    p = api.default_project()
    p["inputs"].update(sys_type="AHU (OA+RA 混合)", ra_t="22", ra_rh="95", ppl_A="0",
                       process_latent_kw="0", chw2_in="20", coil_approach="1")
    p["inputs"].update({k: str(v) for k, v in changes.items()})
    return p


def gate(r):
    return next(q for q in r["quality"]["items"] if q["name"] == "供風量合理性")


def saturation_w(t, pressure=101.325):
    """Independent ASHRAE liquid-water saturation formula for these warm cases."""
    k = t + 273.15
    ps = math.exp(-5800.2206/k + 1.3914993 - .048640239*k + .000041764768*k*k
                  - .000000014452093*k**3 + 6.5459673*math.log(k))
    return .621945*ps/(pressure*1000-ps)


def dewpoint(w):
    lo, hi = 0.0, 40.0
    for _ in range(80):
        mid = (lo+hi)/2
        if saturation_w(mid) < w:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


@pytest.mark.parametrize("rh,water,expected", [(95,20,11.5222059665),(95,20.14,11.5222059665),
    (95,19.06,11.5222059665),(95,7,11.5222059665),(90,19,5.6370714532),(90,18,5.6370714532)])
def test_colder_water_cannot_clear_zero_moisture_saturation_bound(rh, water, expected):
    r = api.calculate(project(ra_rh=rh, chw2_in=water))
    b = r["airflow_basis"]
    assert r["moisture"] == 0
    # Independent room balance proves every m <= 5*m_start is supersaturated.
    dp = dewpoint(r["room"]["w"])
    cp = 1.006 + 1.86*r["room"]["w"]
    target_t = 22-r["qs"]/(5*b["m_start_kg_s"]*cp)
    lower_inflation = r["qs"]/(cp*(22-dp))/b["m_start_kg_s"]
    assert dp > target_t
    assert lower_inflation > 5
    assert b["inflation"] == pytest.approx(expected, rel=1e-10)
    assert b["inflation"] == pytest.approx(lower_inflation, rel=3e-7)  # existing 1e-7 K search tolerance
    assert b["water_only_remedy_blocked"]
    assert b["governing"] == "送風飽和／室內露點條件"
    assert b["chw_needed_c"] is None and not b["chw_remedy_verified"]
    q = gate(r)
    assert q["status"] == "未達" and r["quality"]["status"] == "未達條件"
    assert "僅降低冰水供水無法達到此風量門檻" in q["detail"]
    assert "提高室內相對濕度" not in q["detail"] and "降至" not in q["detail"]
    en = i18n.translate(q["name"]+q["detail"], "en")
    assert not re.search(r"[\u3400-\u9fff]", en), en
    assert "Colder chilled water alone cannot meet this airflow limit" in en
    assert r["summer"]["supply"]["t"] >= dp-1.1e-7
    assert abs(r["summer"]["energy_residual_kw"]) < 1e-6


@pytest.mark.parametrize("rh", [70,80,85,90,95])
def test_zero_moisture_warning_matches_independent_saturation_boundary(rh):
    r = api.calculate(project(ra_rh=rh, chw2_in=7))
    b = r["airflow_basis"]
    cp = 1.006+1.86*r["room"]["w"]
    dp = dewpoint(r["room"]["w"])
    target_t = 22-r["qs"]/(5*b["m_start_kg_s"]*cp)
    assert b["water_only_remedy_blocked"] == (dp > target_t+1e-7)
    assert b["chw_needed_c"] is None


def test_nonzero_moisture_does_not_use_constant_humidity_impossibility_proof():
    r = api.calculate(project(ra_rh=40, ppl_A=30, latent_mode="已知潛熱 kW",
                              process_latent_kw=8, chw2_in=6.5, c2_bf_min=.1))
    assert r["moisture"] > 0
    assert not r["airflow_basis"]["water_only_remedy_blocked"]
    q = gate(r)
    assert q["status"] == "未達"
    assert "尚未驗證" in q["detail"] and "不能保證僅降水溫即可改善" in q["detail"]
    assert "僅降低冰水供水無法" not in q["detail"] and "降至" not in q["detail"]
    en = i18n.translate(q["detail"], "en")
    assert not re.search(r"[\u3400-\u9fff]", en), en
    assert "not a guaranteed remedy" in en


@pytest.mark.parametrize("moisture", [1e-12,1e-9,1e-6])
def test_even_tiny_positive_moisture_uses_only_unverified_warning(moisture):
    room = dict(t=22, w=.0155)
    b = airflow_guard.describe(70,6,3,room,60,moisture,.015,21,101.325,1,20,"load",
                              dict(m_lat=0,m_sens=60,lam=0))
    assert not b["water_only_remedy_blocked"]
    assert b["chw_needed_c"] is None


def test_normal_design_does_not_receive_failure_advice():
    r = api.calculate(api.default_project())
    assert not any("尚未驗證可滿足此門檻" in q["detail"] or "僅降低冰水供水無法" in q["detail"]
                   for q in r["quality"]["items"])


def test_true_infinite_airflow_rejection_is_unchanged():
    with pytest.raises(ValidationError, match="任何風量都無法除濕"):
        api.calculate(project(ra_rh=40,ppl_A=30,chw2_in=16))
