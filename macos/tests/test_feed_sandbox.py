"""Analytical fixtures, adversarial inputs, properties and sandbox GUI regressions."""

import copy
import json
import math
from pathlib import Path
import sys

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.ahu_engine import nm_calculate
from facility_studio.engineering_verification import (
    UNIT_GROUPS,
    compare_inputs,
    compare_file,
    convert_units,
    export_report,
    pipe_calculate,
    pipe_from_water_tool,
)
from facility_studio.feed_review_preview import PIPE_DEFAULTS, VerificationWindow

PROPERTIES = settings(max_examples=100, derandomize=True, database=None, deadline=None)


def test_ahu_quality_preserved_and_references_recomputed():
    data = copy.deepcopy(NM_DEFAULTS)
    before = copy.deepcopy(data)
    r = compare_inputs(data)
    assert data == before
    assert r["model_quality"] == nm_calculate(data)["quality"]
    assert r["model_quality"]["status"] == "未達條件"
    assert r["model_quality"]["failed"] == 4
    assert r["numerical_summary"]["checks"] == 64
    assert r["numerical_summary"]["outside_limit"] == 0
    assert r["inputs"] == nm_calculate(data)["inputs"]
    assert len(r["reference_balances"]) == 2
    for balance in r["reference_balances"]:
        assert abs(balance["reference_energy_residual_kw"]) < 0.01
        assert abs(balance["reference_moisture_residual_kg_h"]) < 0.001
        assert balance["psychrolib_mass_kg_s"] == pytest.approx(
            balance["engine_mass_kg_s"], rel=0.0002
        )
    assert {x["season"] for x in r["comparison"]} == {"summer", "winter"}


def test_psychrolib_documented_dewpoint():
    import psychrolib

    psychrolib.SetUnitSystem(psychrolib.SI)
    # Published example: https://psychrometrics.github.io/psychrolib/api_docs.html
    assert psychrolib.GetTDewPointFromRelHum(25, 0.8) == pytest.approx(
        21.309397163661785, abs=1e-7
    )


def test_scenarios_preserve_expected_engineering_outcomes():
    cases = json.loads((Path(__file__).parent / "scenarios.json").read_text())
    cases = [c for c in cases if c["model"] == "nm"]
    assert len(cases) == 16
    for c in cases:
        if c["id"] == "N13":
            with pytest.raises(Exception, match="冷卻出口不得加熱或增加水氣"):
                compare_inputs(c["project"])
        else:
            r = compare_inputs(c["project"])
            assert r["model_quality"] == nm_calculate(c["project"])["quality"]
            assert all(
                math.isfinite(x[k])
                for x in r["comparison"]
                if "node" in x
                for k in (
                    "engine_w",
                    "psychrolib_w",
                    "coolprop_w",
                    "engine_h",
                    "psychrolib_h",
                    "coolprop_h",
                )
            )


def test_pipe_laminar_against_hagen_poiseuille():
    data = {
        **PIPE_DEFAULTS,
        "flow_lpm": "0.1",
        "id_mm": "10",
        "length_m": "20",
        "sum_k": "0",
    }
    r = pipe_calculate(data)
    assert r["reynolds"] < 2040
    q = 0.1 / 60000
    d = 0.01
    analytic = 128 * r["mu_pa_s"] * 20 * q / (math.pi * d**4)
    assert r["straight_pa"] == pytest.approx(analytic, rel=1e-12)
    assert r["total_pa"] == pytest.approx(analytic, rel=1e-12)


def test_pipe_turbulent_colebrook_residual():
    r = pipe_calculate(PIPE_DEFAULTS)
    f = r["darcy_factor"]
    re = r["reynolds"]
    ed = 0.000045 / 0.05
    residual = 1 / math.sqrt(f) + 2 * math.log10(ed / 3.7 + 2.51 / (re * math.sqrt(f)))
    assert re > 4000 and abs(residual) < 1e-9
    assert 990 < r["rho_kg_m3"] < 1005
    assert 0.0009 < r["mu_pa_s"] < 0.0011


def test_zero_flow_static_and_transition_not_marked_pass():
    r = pipe_calculate({**PIPE_DEFAULTS, "flow_lpm": "0", "equipment_pa": "10000"})
    assert r["total_pa"] == 0 and r["reynolds"] == 0 and r["darcy_factor"] == 0
    opened = pipe_calculate({**PIPE_DEFAULTS, "boundary": "開式系統", "static_m": "10"})
    assert opened["static_pa"] == pytest.approx(opened["rho_kg_m3"] * 9.80665 * 10)
    transition = pipe_calculate({**PIPE_DEFAULTS, "id_mm": "10", "flow_lpm": "1.2"})
    assert "過渡流" in transition["regime"]
    with pytest.raises(ValueError, match="閉式循環"):
        pipe_calculate({**PIPE_DEFAULTS, "static_m": "10"})
    with pytest.raises(ValueError, match="單相液態水"):
        pipe_calculate({**PIPE_DEFAULTS, "temperature_c": "95", "pressure_kpa": "5"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("flow_lpm", "nan"),
        ("flow_lpm", "inf"),
        ("id_mm", "0"),
        ("id_mm", True),
        ("temperature_c", "-1"),
        ("sum_k", "-1"),
        ("pressure_kpa", "abc"),
        ("roughness_mm", "-1"),
    ],
)
def test_invalid_pipe_input(field, value):
    with pytest.raises(ValueError):
        pipe_calculate({**PIPE_DEFAULTS, field: value})


def test_water_tool_bridge_preserves_original():
    from facility_studio.simple_schema import defaults
    from facility_studio.simple_engines import water

    data = defaults("water")
    before = copy.deepcopy(data)
    old = water(data)
    carried = pipe_from_water_tool(data)
    assert data == before and water(data) == old
    assert float(carried["flow_lpm"]) == old["flow_lpm"]
    assert float(carried["id_mm"]) == old["pipe"]["id_mm"]
    r = pipe_calculate({**PIPE_DEFAULTS, **carried})
    assert r["velocity_m_s"] == pytest.approx(old["pipe"]["velocity_mps"])


@pytest.mark.parametrize(
    "group,unit,value,target,expected",
    [
        ("體積流量", "CMH", 1, "CFM", 1 / 1.69901079552),
        ("體積流量", "US GPM", 1, "LPM", 3.785411784),
        ("熱功率", "美制冷凍噸", 1, "kW", 3.5168533333333336),
        ("壓力", "bar", 1, "Pa", 100000),
        ("長度", "inch", 1, "mm", 25.4),
        ("溫度", "°C", 0, "°F", 32),
        ("質量流量", "kg/s", 1, "kg/h", 3600),
        ("能量", "kWh", 1, "kJ", 3600),
        ("密度", "kg/m³", 1, "kg/m³", 1),
        ("動力黏度", "cP", 1, "Pa·s", 0.001),
    ],
)
def test_independent_unit_fixtures(group, unit, value, target, expected):
    assert convert_units(value, group, unit)[target] == pytest.approx(
        expected, rel=1e-10, abs=1e-10
    )


@PROPERTIES
@given(
    st.sampled_from(tuple(UNIT_GROUPS)),
    st.floats(min_value=1, max_value=90, allow_nan=False, allow_infinity=False),
)
def test_units_round_trip(group, value):
    names = tuple(UNIT_GROUPS[group])
    a, b = names[0], names[-1]
    mid = convert_units(value, group, a)[b]
    assert convert_units(mid, group, b)[a] == pytest.approx(value, rel=1e-10, abs=1e-9)


@PROPERTIES
@given(
    st.floats(min_value=1, max_value=1000, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
)
def test_pipe_length_adds_nonnegative_loss(flow, length):
    a = pipe_calculate({**PIPE_DEFAULTS, "flow_lpm": flow, "length_m": length})
    b = pipe_calculate({**PIPE_DEFAULTS, "flow_lpm": flow, "length_m": length + 1})
    assert b["total_pa"] >= a["total_pa"]
    assert b["total_pa"] - a["total_pa"] == pytest.approx(
        a["darcy_factor"] / 0.05 * a["rho_kg_m3"] * a["velocity_m_s"] ** 2 / 2, rel=1e-9
    )


def test_unit_limits_and_wrong_dimensions():
    for args in [
        ("nan", "熱功率", "kW"),
        (-274, "溫度", "°C"),
        (True, "長度", "mm"),
        (10, "壓力", "kW"),
    ]:
        with pytest.raises(ValueError):
            convert_units(*args)


def test_project_rejection_readonly_and_safe_report_export(tmp_path):
    p = tmp_path / "input.json"
    p.write_text(
        json.dumps(
            {"kind": "ahu_stage", "schema_version": 4, "inputs": NM_DEFAULTS},
            ensure_ascii=False,
        )
    )
    old = p.read_bytes()
    r = compare_file(p)
    assert p.read_bytes() == old
    with pytest.raises(ValueError, match="既有檔案"):
        export_report(r, p)
    assert p.read_bytes() == old
    r["case"] = "<script>alert(1)</script>"
    for ext in ("json", "txt", "html"):
        out = tmp_path / ("report." + ext)
        assert len(export_report(r, out)) == 64
        if ext == "json":
            assert json.loads(out.read_text())["inputs"] == r["inputs"]
        if ext == "html":
            assert (
                "<script>" not in out.read_text()
                and "&lt;script&gt;" in out.read_text()
            )
    p.write_text('{"kind":"invalid","schema_version":4,"inputs":{}}')
    with pytest.raises(Exception):
        compare_file(p)
    p.write_text('{"kind":"ahu_stage","schema_version":4,"inputs":NaN}')
    with pytest.raises(Exception):
        compare_file(p)


def test_gui_stale_error_recovery_and_current_ahu(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog

    data = copy.deepcopy(NM_DEFAULTS)
    root = tk.Tk()
    root.withdraw()
    view = VerificationWindow(root, ahu_provider=lambda: dict(data))
    try:
        root.update()
        assert view.source_snapshot == data
        assert "工程品質明細" in view.texts["ahu"].get("1.0", "end")
        data["flow"] = "6000"
        view.export_current()
        assert "ahu" not in view.results
        assert str(view.export_button.cget("state")) == "disabled"
        view.load_current_ahu()
        assert view.source_snapshot == data
        view.nb.select(1)
        root.update()
        view.run("pipe", lambda: pipe_calculate(view.pipe_data()))
        assert "pipe" in view.results
        view.pipe_vars["id_mm"].set("0")
        assert "pipe" not in view.results
        view.run("pipe", lambda: pipe_calculate(view.pipe_data()))
        assert "pipe" not in view.results
        assert "無法執行" in view.texts["pipe"].get("1.0", "end")
        view.pipe_vars["id_mm"].set("50")
        view.run("pipe", lambda: pipe_calculate(view.pipe_data()))
        out = tmp_path / "gui-report.json"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(out))
        view.export_current()
        assert json.loads(out.read_text())["kind"] == "liquid_pipe"
        view.nb.select(2)
        root.update()
        view.convert()
        assert "units" in view.results
        view.value.set("nan")
        assert "units" not in view.results
        view.convert()
        assert "units" not in view.results
        for size in ("1120x820", "720x520"):
            view.win.geometry(size)
            root.update()
            for text in view.texts.values():
                assert text.winfo_reqwidth() > 0
    finally:
        view.win.destroy()
        root.destroy()


def test_traditional_chinese_native_menu(monkeypatch):
    import tkinter as tk
    from facility_studio.sandbox_ui import install_menus

    monkeypatch.setenv("FACILITY_STUDIO_SANDBOX", "1")
    root = tk.Tk()
    root.withdraw()
    try:
        install_menus(root)
        menu = root._sandbox_menu
        labels = [
            menu.entrycget(i, "label")
            for i in range(menu.index("end") + 1)
            if menu.type(i) == "cascade"
        ]
        assert {"檔案", "編輯", "視窗", "說明"}.issubset(labels)
        assert not {"File", "Edit", "Window", "Help"}.intersection(labels)
    finally:
        root.destroy()
