"""C2 search must find coil-feasible airflow without relaxing physical checks."""
import math
import os
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / os.environ.get("FACILITY_TEST_PLATFORM", "macos")))
from facility_studio import api, i18n
from facility_studio.errors import ValidationError


def sat_w(t, pressure=101.325):
    k = t + 273.15
    ps = math.exp(-5800.2206/k + 1.3914993 - .048640239*k + .000041764768*k*k
                  - .000000014452093*k**3 + 6.5459673*math.log(k))
    return .621945 * ps / (pressure*1000 - ps)


def enthalpy(t, w):
    return 1.006*t + w*(2501 + 1.86*t)


def project(**changes):
    p = api.default_project()
    p["inputs"].update(sys_type="AHU (OA+RA 混合)", ra_rh="40", ppl_A="30",
                       process_latent_kw="8", chw2_in="6.5", c2_bf_min=".1")
    p["inputs"].update({k: str(v) for k, v in changes.items()})
    return p


def verify_coil(r, minimum):
    s = r["summer"]
    c = s["c2"]
    bf = c["bf_req"]
    assert bf >= minimum - 1e-9
    assert c["adp_req_c"] >= r["airflow_basis"]["adp_floor_c"] - 1e-9
    w_adp = sat_w(c["adp_req_c"], float(r["project"]["inputs"]["atm_kpa"]))
    assert c["outlet"]["w"] == pytest.approx(bf*c["inlet"]["w"] + (1-bf)*w_adp, abs=1e-11)
    h_out = bf*enthalpy(c["inlet"]["t"], c["inlet"]["w"]) + (1-bf)*enthalpy(c["adp_req_c"], w_adp)
    # The existing coil solver allows 5e-7 K at its reachable boundary.
    assert c["outlet"]["h"] == pytest.approx(h_out, abs=1e-6)
    assert c["outlet"]["w"] <= sat_w(c["outlet"]["t"], float(r["project"]["inputs"]["atm_kpa"])) + 1e-10
    assert c["outlet"]["t"] <= s["supply"]["t"] + 1e-7
    assert abs(s["energy_residual_kw"]) < 1e-6


@pytest.mark.parametrize("latent_mode,expected_moisture,min_mass", [
    ("尚不清楚（暫不計製程）", 1.65/2501, 9.2705776586),
    ("已知潛熱 kW", 9.65/2501, 36.2304271909),
])
def test_bf_humidity_bound_drives_automatic_airflow(latent_mode, expected_moisture, min_mass):
    r = api.calculate(project(latent_mode=latent_mode))
    verify_coil(r, .1)
    assert r["moisture"] == pytest.approx(expected_moisture, rel=1e-12)
    # Independent single-C2 mass-conservation lower bound, not the search code.
    w_adp = sat_w(7.5)
    bound = (r["moisture"] + .1*r["oa_mass"]*(r["oa"]["w"]-r["room"]["w"])) / (.9*(r["room"]["w"]-w_adp))
    assert bound == pytest.approx(min_mass, rel=1e-9)
    assert r["summer"]["mass"] == pytest.approx(bound, rel=1e-8)
    assert r["airflow_basis"]["c2_constrained_search"]
    assert r["airflow_basis"]["chw_needed_c"] is None  # old advice did not include BF
    if latent_mode == "已知潛熱 kW":
        assert r["airflow_basis"]["inflation"] > 5
        assert any(q["name"] == "供風量合理性" and q["status"] == "未達" for q in r["quality"]["items"])


@pytest.mark.parametrize("rh,bf,witness_ach", [(40,.5,30),(45,.3,20),(45,.5,30),
                                               (50,.3,20),(50,.5,30),(60,.1,30),
                                               (60,.3,30),(60,.5,50)])
def test_full_temperature_reachability_not_just_humidity_bound(rh, bf, witness_ach):
    r = api.calculate(project(ra_rh=rh, ppl_A=5, chw2_in=5, c2_bf_min=bf))
    witness = api.calculate(project(ra_rh=rh, ppl_A=5, chw2_in=5, c2_bf_min=bf, en_ach_A=witness_ach))
    verify_coil(r, bf)
    assert r["summer"]["mass"] <= witness["summer"]["mass"] + 1e-7
    assert r["airflow_basis"]["c2_constrained_search"]


@pytest.mark.parametrize("bf", [.01,.05,.1,.2,.3,.4,.5])
def test_bf_boundary_sweep_keeps_realizable_coil_points(bf):
    r = api.calculate(project(c2_bf_min=bf))
    verify_coil(r, bf)
    assert r["summer"]["reheat_kw"] >= 0


@pytest.mark.parametrize("pre_t", [18,20])
@pytest.mark.parametrize("bf", [0,.1,.3])
def test_actual_precoil_outlet_is_used_in_search(pre_t, bf):
    r = api.calculate(project(ra_rh=50, ppl_A=5, chw2_in=5, c2_bf_min=bf,
                              pre_mode="自動旁通因子估算", pre_t=pre_t))
    assert r["summer"]["c1"]["outlet"] == r["summer"]["c2"]["inlet"]
    verify_coil(r, bf)


def test_f1_infinite_airflow_is_still_rejected_before_search():
    p = project(oa_t=45.69, oa_rh=53.81, ra_t=22, ra_rh=40, chw2_in=7.06,
                eq_kw=199.09, en_L_A=75.19, en_W_A=34.58, en_H_A=4.57, ppl_A=1)
    with pytest.raises(ValidationError) as error:
        api.calculate(p)
    assert "任何風量都無法除濕" in str(error.value)
    assert error.value.field_name == "chw2_in"


def test_reheat_required_cannot_be_bypassed_by_the_search():
    with pytest.raises(ValidationError) as error:
        api.calculate(project(allow_reheat=0))
    assert "不允許再熱" in str(error.value)
    assert error.value.field_name == "allow_reheat"
    assert not re.search(r"[\u3400-\u9fff]", i18n.translate(str(error.value), "en"))


def test_no_reheat_direct_solution_remains_allowed():
    r = api.calculate(project(ra_rh=45, ppl_A=5, chw2_in=5, c2_bf_min=.3, allow_reheat=0))
    verify_coil(r, .3)
    assert r["summer"]["reheat_kw"] < 1e-6
    assert r["summer"]["c2"]["achievable_without_reheat"]


@pytest.mark.parametrize("moisture", ["0.00001", "0.0001", "0.001"])
@pytest.mark.parametrize("allow_reheat", ["0", "1"])
def test_huge_airflow_cannot_hide_nonzero_moisture_below_ratio_resolution(moisture, allow_reheat):
    p = project(oa_t=22, oa_rh=40, ra_t=22, ra_rh=40, ow_t=22, ow_rh=40,
                ppl_A=0, eq_kw=0, pcw_n=0, light_lux=0, en_wall=0, en_floor=0,
                oven_kw=0, solar_kw=0, fan_room_kw=0, latent_mode="已知產濕量 kg/h",
                process_moisture_kg_h=moisture, allow_reheat=allow_reheat)
    if allow_reheat == "0":
        with pytest.raises(ValidationError) as error:
            api.calculate(p)
        assert "C2 仍有淨除濕需求" in str(error.value)
        assert "不能視為旁通可行" in str(error.value)
        assert not re.search(r"[\u3400-\u9fff]", i18n.translate(str(error.value), "en"))
    else:
        r = api.calculate(p)
        verify_coil(r, .1)
        assert r["summer"]["mass"] == pytest.approx(3.15601418089986, rel=1e-10)
        assert r["summer"]["reheat_kw"] > 0
        assert r["moisture"] == pytest.approx(float(moisture)/3600, rel=1e-12)
