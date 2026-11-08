"""Independent v16 source-contract checks. No native GUI/FEED acceptance.

Uses actual calculate, text/HTML reports and the production MainView renderer.
UI output sinks replace widgets only; no display geometry or Tk acceptance is
claimed. The full-engine inputs are synthetic regression controls, not a
reconstruction of an owner's engineering project.
"""

import argparse
import ast
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import re
import sys
import traceback
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from probe_control import synthetic_project

ap = argparse.ArgumentParser()
ap.add_argument("--source", required=True, type=Path)
ap.add_argument("--platform", required=True, choices=["windows", "macos"])
ap.add_argument("--output", required=True, type=Path)
ap.add_argument("--legacy-result", type=Path)
args = ap.parse_args()
root = args.source.resolve()
out = args.output.resolve()
out.parent.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root / args.platform))

from facility_studio import dcc_sizing, i18n
from facility_studio.engine import calculate
from facility_studio.errors import InputError
from facility_studio.field_state import effective_main
from facility_studio.html_report import html_report
from facility_studio.main_view import MainView
from facility_studio.reports import executive_summary, report
from facility_studio.schema import FIELDS, default_project
from facility_studio.utils import US_RT_KW

checks, specimens = [], {}


def check(name, fn):
    try:
        detail = fn()
        checks.append({"name": name, "passed": True, "detail": detail})
    except Exception as e:  # noqa: BLE001 - record every failed audit case, then exit nonzero.
        checks.append(
            {
                "name": name,
                "passed": False,
                "error": repr(e),
                "traceback": traceback.format_exc(),
            }
        )


def eq(a, b):
    assert a == b, (a, b)


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-8), (a, b)


def run(heat=3250.551, unit_flow=12000, **changes):
    p = synthetic_project(default_project, heat, unit_flow, **changes)
    original = copy.deepcopy(p)
    r = calculate(p)
    eq(p, original)
    return r


def expect(heat, flow, nthermal, nflow, selected, **changes):
    r = run(heat, flow, **changes)
    s = r["dcc_selection"]
    eq(s["status"], "estimated")
    eq(s["thermal_count"], nthermal)
    eq(s["airflow_count"], nflow)
    eq(s["selected_count"], selected)
    eq(r["counts"]["DCC"], selected)
    eq(s["airflow_margin_factor"], 1.0)
    eq(s["airflow_reference"], "room")
    eq(
        s["governing"],
        "both" if nthermal == nflow else "thermal" if nthermal > nflow else "airflow",
    )
    close(s["flow_cmh"], r["dcc_design_cmh"])
    return r


def numeric_controls():
    hi = expect(3250.551, 12000, 170, 166, 170)
    lo = expect(2840.551, 12000, 149, 166, 166)
    close(hi["ffu_total_cmh"], 2050000)
    close(hi["dcc_return_cmh"], 1992000)
    eq(hi["counts"]["FFU"], 2050)
    close(lo["dcc_selection"]["flow_cmh"] - 149 * 12000, 204000)
    close(hi["rt_kw"], 12000 * 1055.05585262 / 3600000)
    expect(3250.551, 11500, 170, 174, 174)
    specimens.update(thermal=hi, airflow=lo)
    return {k: r["dcc_selection"] for k, r in specimens.items()}


check(
    "Bounded historical values via explicitly synthetic complete-engine controls",
    numeric_controls,
)
check(
    "Zero thermal load still requires positive airflow count",
    lambda: expect(0, 12000, 0, 166, 166)["dcc_selection"],
)
check(
    "Thermal margin does not inflate airflow lower bound",
    lambda: expect(1, 12000, 1, 166, 166, sf="100")["dcc_selection"],
)
check(
    "Exact airflow boundary",
    lambda: expect(
        0, 12000, 0, 2, 2, dcc_airflow_mode="獨立 DCC 循環", dcc_airflow_cmh="24000"
    )["dcc_selection"],
)
check(
    "One ULP above airflow boundary is not rounded down",
    lambda: expect(
        0,
        12000,
        0,
        3,
        3,
        dcc_airflow_mode="獨立 DCC 循環",
        dcc_airflow_cmh=str(math.nextafter(24000.0, math.inf)),
    )["dcc_selection"],
)
check(
    "Decimal capacity boundary is not inflated by binary representation",
    lambda: expect(
        0, 1.2, 0, 10, 10, dcc_airflow_mode="獨立 DCC 循環", dcc_airflow_cmh="12"
    )["dcc_selection"],
)
check(
    "One ULP above decimal capacity boundary still rounds up",
    lambda: expect(
        0,
        1.2,
        0,
        11,
        11,
        dcc_airflow_mode="獨立 DCC 循環",
        dcc_airflow_cmh=str(math.nextafter(12.0, math.inf)),
    )["dcc_selection"],
)


def topology(mode, basis, expected_flow, nflow):
    r = expect(10, 12000, 1, nflow, nflow, ffu_topology=mode, ffu_airflow_basis=basis)
    close(r["dcc_selection"]["flow_cmh"], expected_flow)
    eq(r["dcc_selection"]["flow_source"], "dcc_return")
    return r["dcc_selection"]


check(
    "Plenum recirculation excludes downstream OA",
    lambda: topology("MAU入靜壓箱經FFU送風", "室內基本循環（另加OA）", 1992000, 166),
)
check(
    "Plenum total includes OA and subtracts it once",
    lambda: topology("MAU入靜壓箱經FFU送風", "FFU總送風（已含OA）", 1934000, 162),
)
check(
    "Independent FFU does not add OA",
    lambda: topology(
        "獨立FFU循環（MAU直接入室）", "室內基本循環（另加OA）", 1992000, 166
    ),
)


def independent():
    r = expect(
        10, 12000, 1, 3, 3, dcc_airflow_mode="獨立 DCC 循環", dcc_airflow_cmh="25000"
    )
    eq(r["dcc_selection"]["flow_source"], "independent")
    close(r["dcc_selection"]["flow_cmh"], 25000)
    return r["dcc_selection"]


check("Independent DCC circulation overrides return and FFU flows", independent)


def invalid_topology():
    try:
        run(100, 12000, en_ach_A="1", ffu_airflow_basis="FFU總送風（已含OA）")
    except InputError as e:
        eq(e.field_name, "ffu_airflow_basis")
        return {"field": e.field_name, "message": str(e)}
    raise AssertionError("DCC unit flow must not repair FFU total below OA")


check("Known unit airflow cannot bypass infeasible OA/FFU topology", invalid_topology)
check(
    "Derived return ignores malformed inactive independent-flow draft",
    lambda: expect(
        100,
        12000,
        6,
        166,
        166,
        dcc_airflow_mode="沿用 FFU 循環",
        dcc_airflow_cmh="inactive draft",
    )["dcc_selection"],
)


def winter():
    r = run(2000, 12000, winter_gain_ratio="200")
    close(r["dcc_kw"], 2000)
    close(r["dcc_design_kw"], 4000)
    eq(r["dcc_design_season"], "winter")
    eq(r["dcc_selection"]["thermal_count"], 209)
    eq(r["counts"]["DCC"], 209)
    return r["dcc_selection"]


check("Winter rather than summer governs thermal lower bound", winter)


def japan():
    r = run(3250.551, 12000, rt_type="JIS RT (日制 3320 kcal/hr)")
    expected_kw = 3320 * 4.1868 / 3600
    close(r["rt_kw"], expected_kw)
    n = math.ceil(3250.551 * 1.1 / (6 * expected_kw) - 1e-12)
    eq(r["dcc_selection"]["thermal_count"], n)
    eq(r["counts"]["DCC"], max(n, 166))
    return r["dcc_selection"]


check("JIS RT retains selected thermal conversion", japan)


def pending(value):
    r = run(2840.551, value)
    s = r["dcc_selection"]
    eq(s["status"], "pending")
    eq(s["selected_count"], None)
    eq(s["airflow_count"], None)
    eq(s["thermal_count"], 149)
    eq(r["counts"]["DCC"], 149)
    assert dcc_sizing.UNIT_FLOW_KEY in s["pending_fields"]
    specimens["pending"] = r
    return s


for value in (None, "", " ", "0"):
    check(
        "Missing/blank/zero unit airflow stays pending: " + repr(value),
        lambda value=value: pending(value),
    )


def invalid(value, key="dcc_unit_airflow_cmh"):
    p = synthetic_project(default_project, 100, 12000)
    p["inputs"][key] = value
    try:
        calculate(p)
    except InputError as e:
        eq(e.field_name, key)
        return {"field": e.field_name, "code": e.code}
    raise AssertionError("Invalid active input was accepted: " + repr(value))


for value in ("-1", "nan", "NaN", "inf", "-inf", "1e309", "garbage", True, 12000, None):
    check(
        "Invalid active unit airflow rejected: " + repr(value),
        lambda value=value: invalid(value),
    )
for value in ("", "0", "-1", "nan", "inf"):
    check(
        "Invalid active thermal capacity rejected: " + repr(value),
        lambda value=value: invalid(value, "en_dcc_rt"),
    )


def missing_capacity():
    p = synthetic_project(default_project, 100, 12000)
    del p["inputs"]["en_dcc_rt"]
    try:
        calculate(p)
    except InputError as e:
        eq(e.field_name, "en_dcc_rt")
        return e.code
    raise AssertionError("Missing mandatory capacity accepted")


check("Missing mandatory thermal capacity remains rejected", missing_capacity)


def inactive(system):
    p = default_project()
    p["inputs"].update(
        sys_type=system, dcc_unit_airflow_cmh="not-a-number", en_dcc_rt="not-a-number"
    )
    before = copy.deepcopy(p)
    r = calculate(p)
    eq(p, before)
    eq(r["dcc_selection"]["status"], "not_applicable")
    eq(r["counts"]["DCC"], 0)
    assert "dcc_unit_airflow_cmh" not in effective_main(p["inputs"])
    return r["dcc_selection"]


for system in FIELDS["sys_type"]["options"]:
    if not system.startswith("MAU"):
        check(
            "Inactive non-MAU preserves malformed DCC drafts: " + system,
            lambda system=system: inactive(system),
        )


def no_flow():
    r = run(100, 12000, dcc_airflow_mode="獨立 DCC 循環", dcc_airflow_cmh="0")
    eq(r["dcc_selection"]["status"], "pending")
    eq(r["dcc_selection"]["selected_count"], None)
    assert "dcc_airflow_mode" in r["dcc_selection"]["pending_fields"]
    assert any(
        x["status"] == "未達" and "DCC" in json.dumps(x, ensure_ascii=False)
        for x in r["quality"]["items"]
    )
    specimens["no_flow"] = r
    return r["dcc_selection"]


check("Positive heat with zero DCC flow remains pending and physics unmet", no_flow)
check(
    "Explicit zero heat/zero flow needs zero units",
    lambda: expect(
        0, 12000, 0, 0, 0, dcc_airflow_mode="獨立 DCC 循環", dcc_airflow_cmh="0"
    )["dcc_selection"],
)


def zero_heat_pending():
    r = run(0, None)
    eq(r["counts"]["DCC"], 0)
    eq(r["dcc_selection"]["selected_count"], None)
    eq(r["dcc_selection"]["status"], "pending")
    assert any(
        x["status"] == "待資料" and x.get("field") == dcc_sizing.UNIT_FLOW_KEY
        for x in r["quality"]["items"]
    )
    specimens["zero_heat_pending"] = r
    return r["dcc_selection"]


check(
    "Zero thermal count cannot hide unknown airflow and positive circulation",
    zero_heat_pending,
)


class Sink:
    def __init__(self):
        self.values = {}

    def config(self, **kw):
        self.values.update(kw)

    configure = config

    def set(self, value):
        self.values["text"] = value

    def item(self, name, **kw):
        self.values[name] = kw


def rendered_ui(result):
    owner = NS(
        result=result,
        summary=Sink(),
        psy_label=Sink(),
        topology=Sink(),
        result_labels={k: Sink() for k in range(1, 7)},
        latent_text=Sink(),
        grid=Sink(),
    )
    MainView.render_results(owner)
    return owner.result_labels[1].values["text"]


def surfaces(name):
    r = specimens[name]
    original = copy.deepcopy(r)
    snippets = {}
    for language in ("zh-Hant", "en"):
        i18n.set_language(language, persist=False)
        text = str(report(r, language=language))
        html = str(html_report(r, language=language))
        ui = i18n.translate(rendered_ui(r), language)
        row = next(
            row for row in executive_summary(r) if row["equipment"].startswith("DCC")
        )
        executive = i18n.translate(json.dumps(row, ensure_ascii=False), language)
        marker = i18n.translate(dcc_sizing.selection_text(r), language)
        for route, content in [
            ("text", text),
            ("HTML", html),
            ("main_view", ui),
            ("executive", executive),
        ]:
            assert marker in content, (name, language, route, marker, content[:300])
            if language == "en":
                assert not re.search(r"[\u3400-\u9fff]", marker), marker
            if name == "pending":
                assert "DCC 149 台" not in content
                assert "DCC 149 units" not in content
        snippets[language] = {"ui": ui, "row": executive, "marker": marker}
        (out.parent / f"{args.platform}-{name}-{language}.html").write_text(html)
        (out.parent / f"{args.platform}-{name}-{language}.txt").write_text(text)
    eq(r, original)
    return snippets


for name in ("thermal", "airflow", "pending", "no_flow", "zero_heat_pending"):
    check(
        "Actual text/HTML/executive/MainView ZH/EN routes: " + name,
        lambda name=name: surfaces(name),
    )


def legacy():
    assert args.legacy_result
    r = json.loads(args.legacy_result.read_text())
    # A later draft must not retroactively validate a saved thermal-only result.
    r["project"]["inputs"]["dcc_unit_airflow_cmh"] = "12000"
    r["effective_inputs"]["dcc_unit_airflow_cmh"] = "12000"
    original = copy.deepcopy(r)
    outputs = {}
    for language in ("zh-Hant", "en"):
        i18n.set_language(language, persist=False)
        marker = i18n.translate(dcc_sizing.LEGACY_NOTE, language)
        row = next(
            row for row in executive_summary(r) if row["equipment"].startswith("DCC")
        )
        for label, content in [
            ("text", report(r, language=language)),
            ("html", html_report(r, language=language)),
            ("ui", i18n.translate(rendered_ui(r), language)),
            ("executive", i18n.translate(row["selection"], language)),
        ]:
            assert marker in content, (label, language, content[:300])
        outputs[language] = i18n.translate(rendered_ui(r), language)
    eq(r, original)
    return outputs


check("Genuine v15 result remains visibly legacy despite later input draft", legacy)


def preserved_physics():
    prior = json.loads(args.legacy_result.read_text())
    now = specimens["thermal"]
    keys = (
        "qs",
        "ql",
        "parts",
        "room",
        "summer",
        "winter",
        "winter_room",
        "dcc_kw",
        "dcc_design_kw",
        "dcc_design_season",
        "dcc_design_cmh",
        "dcc_return_cmh",
        "ffu_total_cmh",
        "water",
        "pressure",
        "ducts",
        "electric",
        "gas",
        "upw",
        "q_total_kw",
        "q_water_capacity_envelope_kw",
    )
    for key in keys:
        if key != 'electric':
            eq(now[key], prior[key])
            continue
        eq(set(now[key]), set(prior[key]))
        for panel, old in prior[key].items():
            current = now[key][panel]
            eq(set(current), set(old) | {'selection_status', 'selection_reason'})
            eq(current['selected'], None)
            eq(current['candidate_count'], None)
            zero = old['kw'] == old['current_a'] == old['design_current_a'] == 0
            eq(current['selection_status'], 'no_electrical_load' if zero else 'blocked_unverified_ampacity_basis')
            eq(current['selection_reason'], '無電氣負載；未進行配線選型。' if zero else '自動配線選型已暫停；導線、NFB、有效載流量、壓降及衍生 PE 須另行工程核實，本工具未採用選型。')
            eq({k: current[k] for k in old if k not in ('selected', 'candidate_count')},
               {k: v for k, v in old.items() if k not in ('selected', 'candidate_count')})
    eq(now["quality"], prior["quality"])
    return list(keys) + ["quality"]


check(
    "Independent saved v15 control retains thermal, water, electrical and physical quality outputs",
    preserved_physics,
)


def settings_callbacks():
    """Execute actual settings construction/apply/focus with headless UI sinks."""
    from facility_studio import (
        fusion_settings,
        localized_tk,
        main_view,
        platform_support,
        window_geometry,
    )

    elements, errors, calls = [], [], []

    class Var:
        def __init__(self, *a, value="", **kw):
            self.value, self.traces = value, []

        def get(self):
            return self.value

        def set(self, value):
            self.value = value
            for f in self.traces:
                f()

        def trace_add(self, mode, f):
            self.traces.append(f)

    class Widget:
        def __init__(self, parent=None, **kw):
            self.parent, self.kw, self.live, self.tabs, self.selected = (
                parent,
                kw,
                True,
                [],
                0,
            )
            self.focused = False
            self.bindings = {}
            self.tk = NS(call=lambda *a: "8.6.16" if a[0] == "package" else "x11")
            elements.append(self)

        def pack(self, **kw):
            pass

        def grid(self, **kw):
            pass

        def columnconfigure(self, *a, **kw):
            pass

        def configure(self, **kw):
            self.kw.update(kw)

        config = configure

        def bind(self, event, callback, **kw):
            self.bindings[event] = callback
            return "test-binding-" + event

        def unbind(self, event, binding):
            self.bindings.pop(event, None)

        def after_idle(self, callback):
            callback()

        def title(self, *a):
            pass

        def geometry(self, *a):
            pass

        def minsize(self, *a):
            pass

        def add(self, page, **kw):
            self.tabs.append((page, kw))

        def index(self, arg):
            return arg

        def select(self, arg=None):
            if arg is not None:
                self.selected = arg
            return self.selected

        def focus_set(self):
            self.focused = True

        def destroy(self):
            self.live = False

        def winfo_exists(self):
            return self.live

        def see(self, *a):
            pass

    class Page(Widget):
        def __init__(self, parent):
            super().__init__(parent)
            self.body, self.canvas = Widget(self), Widget(self)

        def reveal(self, widget):
            calls.append(("reveal", widget))

    p = synthetic_project(default_project, 100, None)
    extra = {}
    app = NS(
        root=Widget(),
        project_id="synthetic-owner",
        _workspace_generation=1,
        extra_inputs=extra,
    )
    app.snapshot = lambda: dict(p, inputs=dict(p["inputs"], **extra))
    app.remember_main_undo = lambda: calls.append("undo")
    app.changed = lambda: calls.append("changed")
    app.recalculate = lambda: calls.append("recalculate")
    with ExitStack() as stack:
        # Headless UI sinks have no native monitor; retain production sizing
        # against explicit synthetic bounds, scoped to these callback checks.
        monitor = stack.enter_context(
            patch.object(window_geometry, "_windows_work_area", return_value=(1024, 728))
        )
        stack.enter_context(patch.object(localized_tk.tk, "Toplevel", Widget))
        stack.enter_context(patch.object(localized_tk.tk, "StringVar", Var))
        stack.enter_context(
            patch.object(localized_tk, "attach_window", lambda win: None)
        )
        for name in ("Label", "Notebook", "Frame", "Combobox", "Entry", "Button"):
            stack.enter_context(patch.object(localized_tk.ttk, name, Widget))
        stack.enter_context(patch.object(main_view, "ScrollPage", Page))
        stack.enter_context(
            patch.object(platform_support, "wheel_sequences", lambda tk: ())
        )
        stack.enter_context(
            patch.object(
                localized_tk.messagebox, "showerror", lambda *a, **kw: errors.append(a)
            )
        )
        win = fusion_settings.open_settings(app, focus_key=dcc_sizing.UNIT_FLOW_KEY)
        if args.platform == "windows":
            monitor.assert_called_once_with(app.root)
        else:
            monitor.assert_not_called()
        if "<Map>" in win.bindings:
            win.bindings["<Map>"](NS(widget=win))
        var = win.fusion_values[dcc_sizing.UNIT_FLOW_KEY]
        entry = next(w for w in elements if w.kw.get("textvariable") is var)
        eq(var.get(), "")
        eq(entry.kw["state"], "normal")
        eq(win.fusion_notebook.selected, 0)
        assert entry.focused
        var.set("-1")
        win.apply_fusion_settings()
        assert errors and entry.focused and win.live
        eq(win.fusion_notebook.selected, 0)
        eq(extra, {})
        eq(calls, [])
        var.set("12000")
        win.apply_fusion_settings()
        eq(extra[dcc_sizing.UNIT_FLOW_KEY], "12000")
        eq(calls, ["undo", "changed", "recalculate"])
        assert not win.live
        # Clear the optional value without manufacturing a default.
        win = fusion_settings.open_settings(app)
        win.fusion_values[dcc_sizing.UNIT_FLOW_KEY].set("")
        win.apply_fusion_settings()
        eq(extra.get(dcc_sizing.UNIT_FLOW_KEY, ""), "")
        eq(calculate(app.snapshot())["dcc_selection"]["status"], "pending")
        # Inactive field stays disabled and retains bounded draft text.
        p["inputs"]["sys_type"] = "AHU (OA+RA 混合)"
        extra[dcc_sizing.UNIT_FLOW_KEY] = "inactive draft"
        win = fusion_settings.open_settings(app)
        var = win.fusion_values[dcc_sizing.UNIT_FLOW_KEY]
        entry = next(w for w in elements if w.kw.get("textvariable") is var)
        eq(entry.kw["state"], "disabled")
        win.apply_fusion_settings()
        eq(extra[dcc_sizing.UNIT_FLOW_KEY], "inactive draft")
    return {
        "actions": calls,
        "errors": errors,
        "mode": "Production callbacks with headless widgets; no native Tk acceptance",
    }


check(
    "Actual advanced-settings callback routing, focus, rejection, apply, clear, inactive draft",
    settings_callbacks,
)


def scenario_oracle():
    path = root / args.platform / "tests" / "engineering_scenarios" / "checks.py"
    spec = importlib.util.spec_from_file_location("independent_scenario_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    c = {
        "system": "MAU+FFU+DCC (全外氣/無塵室)",
        "area_m2": 8300,
        "height_m": 3,
        "ach": 80,
        "id": "SYNTHETIC",
        "oa_cmh": 58000,
        "exhaust_cmh": 0,
    }
    records = []
    for label, result in (
        ("whitespace unknown", run(100, " ")),
        (
            "positive heat zero flow",
            run(100, 12000, dcc_airflow_mode="獨立 DCC 循環", dcc_airflow_cmh="0"),
        ),
        ("known airflow", run(100, 12000)),
    ):
        zh, en = (
            str(report(result, language="zh-Hant")),
            str(report(result, language="en")),
        )

        def g7(r, zh=zh, en=en):
            # Hold report fixtures constant so a deliberately inconsistent
            # metadata mutation reaches the adapted arithmetic/status oracle.
            items = module.check_accepted(c, {}, r, zh, en, {})
            return next(x for x in items if x["id"] == "G7")

        good = g7(result)
        eq(good["status"], "PASS")
        assert "arithmetic/status only" in good["note"]
        bad = copy.deepcopy(result)
        bad["dcc_selection"]["status"] = (
            "estimated" if result["dcc_selection"]["status"] == "pending" else "pending"
        )
        eq(g7(bad)["status"], "FAIL")
        records.append(
            {"case": label, "valid_oracle": good, "false_metadata_rejected": True}
        )
    return records


check(
    "Adapted scenario oracle accepts valid blank/zero-flow cases but rejects false completion metadata",
    scenario_oracle,
)


def mutations():
    original = dcc_sizing.joint_selection
    killed = []
    variants = {
        "thermal_only_count": lambda kw: dict(kw),
        "double_OA_in_DCC_flow": lambda kw: dict(kw, flow_cmh=kw["flow_cmh"] + 58000),
        "thermal_margin_on_airflow": lambda kw: dict(
            kw, flow_cmh=kw["flow_cmh"] * kw["sf"]
        ),
        "summer_only_thermal": lambda kw: dict(
            kw, thermal_kw=min(2000, kw["thermal_kw"])
        ),
        "fabricated_unknown_unit_flow": lambda kw: dict(
            kw, unit_flow=kw["unit_flow"] or "12000"
        ),
        "ignore_independent_DCC_flow": lambda kw: dict(kw, flow_cmh=1992000),
        "US_conversion_for_JIS": lambda kw: dict(kw, rt_kw=3.5168528420667),
        # Historical 2,000 kW equipment component already includes 80% use.
        "double_equipment_utilization": lambda kw: dict(
            kw, thermal_kw=max(0, kw["thermal_kw"] - 2000 * 0.2)
        ),
    }
    for name, alter in variants.items():

        def mutant(_name=name, _alter=alter, **kw):
            s = original(**_alter(kw))
            if _name == "thermal_only_count":
                s["selected_count"] = s["compatibility_count"] = s["thermal_count"]
            return s

        try:
            with patch.object(dcc_sizing, "joint_selection", mutant):
                if name == "summer_only_thermal":
                    winter()
                elif name == "fabricated_unknown_unit_flow":
                    pending(None)
                elif name == "ignore_independent_DCC_flow":
                    independent()
                elif name == "US_conversion_for_JIS":
                    japan()
                elif name == "double_equipment_utilization":
                    expect(3250.551, 12000, 170, 166, 170)
                else:
                    expect(2840.551, 12000, 149, 166, 166)
        except AssertionError:
            killed.append(name)
    eq(killed, list(variants))
    return killed


check("Independent controls kill eight in-memory semantic mutations", mutations)


HAN = re.compile(r"[\u3400-\u9fff]")
NUMBER_TOKENS = re.compile(r"\d+(?:[.,]\d+)*(?:[eE][+-]?\d+)?")


def translated_dcc_text(raw):
    english = i18n.translate(raw, "en")
    assert not HAN.search(english), english
    eq(NUMBER_TOKENS.findall(raw), NUMBER_TOKENS.findall(english))
    return english


def authored_dcc_fragments():
    source = root / args.platform / "facility_studio" / "dcc_sizing.py"
    fragments = [
        node.value
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and HAN.search(node.value)
    ]
    fragments.extend(
        [
            "；DCC 適用風量 ",
            "DCC 適用風量",
            "\n；DCC 適用風量 \n",
            "DCC 適用風量 1,992,000.000000 CMH",
        ]
    )
    for fragment in fragments:
        translated_dcc_text(fragment)
    return {"authored_and_boundary_fragments": len(fragments)}


check(
    "DCC authored fragments translate without a following numeric value",
    authored_dcc_fragments,
)


def tied_report_routes():
    details = []
    for name, heat, flow, count in (
        ("positive_tie", 100, "72000", 6),
        ("zero_tie", 0, "0", 0),
    ):
        result = run(
            heat,
            12000,
            dcc_airflow_mode="獨立 DCC 循環",
            dcc_airflow_cmh=flow,
        )
        before = copy.deepcopy(result)
        selection = result["dcc_selection"]
        eq(selection["governing"], "both")
        eq(selection["thermal_count"], count)
        eq(selection["airflow_count"], count)
        eq(selection["selected_count"], count)
        marker = translated_dcc_text(dcc_sizing.selection_text(result))
        assert "thermal and airflow together" in marker
        translated_dcc_text(dcc_sizing.selection_text(result, detailed=True))
        for language in ("zh-Hant", "en"):
            i18n.set_language(language, persist=False)
            routes = {
                "text": str(report(result, language=language)),
                "HTML": str(html_report(result, language=language)),
                "MainView": i18n.translate(rendered_ui(result), language),
                "executive": i18n.translate(
                    json.dumps(executive_summary(result), ensure_ascii=False), language
                ),
            }
            expected = marker if language == "en" else dcc_sizing.selection_text(result)
            for route, content in routes.items():
                assert expected in content, (name, language, route)
                if language == "en":
                    assert not HAN.search(content), (name, route, content)
            (out.parent / f"{args.platform}-{name}-{language}.html").write_text(
                routes["HTML"], encoding="utf-8"
            )
            (out.parent / f"{args.platform}-{name}-{language}.txt").write_text(
                routes["text"], encoding="utf-8"
            )
        eq(result, before)
        details.append({"case": name, "count": count, "governing": "both"})
    return details


check(
    "Actual positive and zero tied-count output is fully bilingual", tied_report_routes
)


def scientific_and_tiny_formats():
    cases = 0
    display_observations = []
    for unit in (None, "", "0", "0.00000001", "0.12", "1.2", "12000", "1e8", "1e-300"):
        for flow in (0.0, 1e-9, 1e-7, 0.3, 12.0, 1992000.0, 100000000.0):
            selection = dcc_sizing.joint_selection(
                applicable=True,
                thermal_kw=0,
                sf=1.1,
                unit_rt=6,
                rt_kw=US_RT_KW,
                flow_cmh=flow,
                unit_flow=unit,
                flow_source="independent",
            )
            before = copy.deepcopy(selection)
            raw = dcc_sizing.selection_text({"dcc_selection": selection}, detailed=True)
            translated_dcc_text(raw)
            eq(selection, before)
            cases += 1
            if flow > 0 and "DCC 適用風量 0.000000 CMH" in raw:
                display_observations.append(
                    {"flow_cmh": flow, "unit_airflow_cmh": unit}
                )
    eq(cases, 63)
    return {
        "cases": cases,
        "deferred_fixed_precision_display_observations": display_observations,
        "scope": "Language and numeric-token parity; not a tiny-flow display-format fix",
    }


check(
    "Scientific zero tiny and large DCC values retain translated numeric tokens",
    scientific_and_tiny_formats,
)


def catalog_mutations():
    original = dict(i18n.TEXT)
    killed = []

    def restore():
        i18n.TEXT.clear()
        i18n.TEXT.update(original)
        i18n._pattern = None
        i18n._english_text.cache_clear()

    try:
        value = i18n.TEXT.pop("DCC 適用風量")
        i18n.TEXT["DCC 適用風量 "] = value
        i18n._pattern = None
        i18n._english_text.cache_clear()
        try:
            translated_dcc_text("；DCC 適用風量 ")
        except AssertionError:
            killed.append("trailing_space_only_airflow_key")
        restore()
        del i18n.TEXT["主導條件：熱量與風量同時"]
        i18n._pattern = None
        i18n._english_text.cache_clear()
        try:
            translated_dcc_text("主導條件：熱量與風量同時。")
        except AssertionError:
            killed.append("missing_full_tie_governing_phrase")
    finally:
        restore()
    eq(killed, ["trailing_space_only_airflow_key", "missing_full_tie_governing_phrase"])
    return killed


check("Independent presentation checks kill two catalog mutations", catalog_mutations)

data = {
    "scope": "Independent source audit; synthetic controls; no native GUI or engineering acceptance",
    "source": str(root),
    "source_platform": args.platform,
    "host": sys.platform,
    "python": sys.version,
    "display": os.environ.get("DISPLAY"),
    "checks": checks,
    "files": {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / args.platform / "facility_studio").glob("*.py"))
    },
    "dependencies": {
        name: importlib.metadata.version(name)
        for name in ("pytest", "CoolProp", "fluids", "psychrolib", "Pint")
    },
    "passed": sum(c["passed"] for c in checks),
    "failed": sum(not c["passed"] for c in checks),
}
out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print(
    json.dumps(
        {
            "passed": data["passed"],
            "failed": data["failed"],
            "failures": [
                {k: x[k] for k in ("name", "error")} for x in checks if not x["passed"]
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
)
sys.exit(1 if data["failed"] else 0)
