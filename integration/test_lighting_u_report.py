"""Real full-project TXT/HTML reports identify the manually entered lighting U.

Use a separate process for each FACILITY_TEST_PLATFORM. No GUI or report mocks.
"""
import copy
from html import unescape
import math
import os
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = os.environ.get("FACILITY_TEST_PLATFORM", "windows")
sys.path.insert(0, str(ROOT / PLATFORM))
from facility_studio import reports
from facility_studio.engine import calculate
from facility_studio.html_report import html_report
from facility_studio.schema import default_project

MODES = ("手動固定 U", "型錄 U＋室指數 K 檢核")
LABELS = {
    "zh-Hant": "手動輸入利用係數 U（無因次）=",
    "en": "Manually entered utilization factor U (dimensionless)=",
}


def test_selected_platform_is_the_actual_report_source():
    assert Path(reports.__file__).resolve().is_relative_to(ROOT / PLATFORM)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("u", ["0.35", "0.6", "0.85"])
@pytest.mark.parametrize("language", ["zh-Hant", "en"])
@pytest.mark.parametrize("format", ["txt", "html"])
def test_real_reports_identify_manual_u_and_dimensionless_unit(mode, u, language, format):
    project = default_project()
    project["inputs"].update(light_u_mode=mode, light_u=u)
    result = calculate(project)
    before = copy.deepcopy(result)
    render = reports.report if format == "txt" else html_report
    text = unescape(str(render(result, language=language)))
    line = next(line for line in text.splitlines() if "N=ceil(E×A/(Φ×U×M))" in line)
    assert re.search(re.escape(LABELS[language]) + r"\s*" + re.escape(f"{float(u):.4f}"), line)
    assert "U(K)" not in text
    assert "W/(m²" not in line and "kcal/" not in line
    assert result["light"]["u"] == float(u)
    inputs = project["inputs"]
    expected_qty = math.ceil(float(inputs["light_lux"]) * result["light"]["area_m2"] /
                             (float(inputs["light_lm"]) * float(u) * float(inputs["light_m"])) - 1e-12)
    assert result["light"]["qty"] == expected_qty
    assert re.search(r"=\s*" + str(expected_qty) + r"\s*(?:盞|luminaires)", line)
    if mode == MODES[1]:
        assert re.search(r"K=\s*" + re.escape(f"{result['light']['room_index_k']:.2f}"), line)
    else:
        assert result["light"]["room_index_k"] is None
    assert result == before


@pytest.mark.parametrize("u", ["0.35", "0.6", "0.85"])
def test_room_index_changes_do_not_rederive_u_or_luminaire_count(u):
    results = []
    for height in ("3", "5"):
        project = default_project()
        project["inputs"].update(light_u_mode=MODES[1], light_u=u, en_H_A=height, en_H_B=height)
        results.append(calculate(project))
    a, b = (result["light"] for result in results)
    assert a["room_index_k"] != b["room_index_k"]
    assert a["u"] == b["u"] == float(u)
    assert a["qty"] == b["qty"]
    for result in results:
        for language in LABELS:
            text = str(reports.report(result, language=language))
            assert "U(K)" not in text
            assert re.search(re.escape(LABELS[language]) + r"\s*" + re.escape(f"{float(u):.4f}"), text)
