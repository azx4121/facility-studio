"""Storage regressions and independent checks for the truncated-review follow-up."""
import copy
import json
import math
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace

from .ahu_engine import nm_calculate, nm_draft_inputs, nm_read_project, nm_validate
from .ahu_schema import NM_DEFAULTS
from .engine import condition_air
from .errors import InputError
from .schema import default_project
from .utils import project_hash, state_trh
from .version import VERSION


def run_checks():
    from unittest.mock import patch
    from .ahu_desktop import AHUWindow
    from . import i18n

    checks = []

    def record(name, action):
        action()
        checks.append({"name": name, "passed": True})

    def expect_input_error(action, field=None):
        try:
            action()
        except InputError as error:
            if field is not None:
                assert error.field_name == field
        else:
            raise AssertionError("Expected InputError")

    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        for index, invalid in enumerate(("", "abc", "NaN", "-1", "1e999")):
            raw = dict(NM_DEFAULTS, flow=invalid)
            target = folder / ("draft-%d.json" % index)
            ui = SimpleNamespace(path=str(target), snapshot=lambda: raw, win=None,
                                 saved_hash="before", status=SimpleNamespace(config=lambda **kw: None))
            with patch("facility_studio.ahu_desktop.messagebox.askyesno", return_value=True), \
                 patch("facility_studio.ahu_desktop.messagebox.showerror") as errors:
                AHUWindow.save(ui)
                assert not errors.called
            loaded = nm_read_project(target)

            def roundtrip():
                assert loaded["schema_version"] == 5 and loaded["draft"] is True
                assert loaded["inputs"] == raw
                assert ui.saved_hash == project_hash(raw)
                expect_input_error(lambda: nm_calculate(loaded["inputs"]), "flow")
            record("AHU draft save/read retains invalid flow " + repr(invalid), roundtrip)

        original = dict(NM_DEFAULTS)
        target = folder / "existing.json"
        baseline = {"kind": "ahu_stage", "schema_version": 4, "inputs": original}
        target.write_text(json.dumps(baseline), encoding="utf-8")
        original_bytes = target.read_bytes()
        raw = dict(original, flow="abc")
        ui = SimpleNamespace(path=str(target), snapshot=lambda: raw, win=None,
                             saved_hash=project_hash(original), status=SimpleNamespace(config=lambda **kw: None))

        def declined_save():
            before = ui.saved_hash
            with patch("facility_studio.ahu_desktop.messagebox.askyesno", return_value=False):
                AHUWindow.save(ui)
            assert target.read_bytes() == original_bytes and ui.saved_hash == before
            assert not target.with_suffix(".json.bak").exists()
        record("Declined draft save leaves existing file and saved state unchanged", declined_save)

        with patch("facility_studio.ahu_desktop.messagebox.askyesno", return_value=True):
            AHUWindow.save(ui)
        record("Accepted draft overwrite preserves prior valid backup",
               lambda: _assert(target.with_suffix(".json.bak").read_bytes() == original_bytes))
        raw["flow"] = original["flow"]
        AHUWindow.save(ui)
        record("Corrected draft saves as ordinary v4 project",
               lambda: _assert(nm_read_project(target) == baseline))
        backup = nm_read_project(target.with_suffix(".json.bak"))
        record("Corrected draft retains invalid draft in backup",
               lambda: _assert(backup["draft"] is True and backup["inputs"]["flow"] == "abc"))

        def save_failure():
            ui.saved_hash = "unchanged"
            with patch("facility_studio.ahu_desktop.save_project_file", side_effect=OSError("read only")), \
                 patch("facility_studio.ahu_desktop.messagebox.showerror") as errors:
                AHUWindow.save(ui)
            assert ui.saved_hash == "unchanged" and errors.called
        record("I/O failure does not mark draft saved", save_failure)

        # Exercise the actual load and apply methods without creating a Tk window.
        # The native suite separately tests real widgets and export state.
        class Value:
            def __init__(self, value):
                self.value = value
            def get(self):
                return self.value
            def set(self, value):
                self.value = value

        ui = object.__new__(AHUWindow)
        ui.vars = {k: Value(v) for k, v in original.items()}
        ui.win = None
        ui.source_project_id = ""
        ui.saved_hash = project_hash(original)
        ui.result = {"old": "result"}
        ui.last_good_result = {"old": "result"}
        ui.changed = lambda: None
        calculations = []
        ui.calculate = lambda: calculations.append(ui.snapshot())
        with patch("facility_studio.ahu_desktop.filedialog.askopenfilename", return_value=str(folder / "draft-1.json")):
            ui.load()
        record("Actual AHU load/apply restores invalid text and clears prior results",
               lambda: _assert(ui.vars["flow"].get() == "abc" and ui.result is None
                               and ui.last_good_result is None and calculations[-1]["flow"] == "abc"))

        def explicit_draft_only():
            target.write_text(json.dumps({"kind": "ahu_stage", "schema_version": 4,
                                         "inputs": dict(NM_DEFAULTS, flow="abc")}), encoding="utf-8")
            expect_input_error(lambda: nm_read_project(target), "flow")
        record("Legacy ordinary documents still require valid inputs", explicit_draft_only)

        malformed = []
        draft = {"kind": "ahu_stage", "schema_version": 5, "draft": True, "inputs": dict(NM_DEFAULTS, flow="abc")}
        for flag in (False, 1, "true", None):
            malformed.append(dict(draft, draft=flag))
        malformed += [{k: v for k, v in draft.items() if k != "draft"},
                      dict(draft, unknown="x"), dict(draft, schema_version=5.0)]
        for value in (None, 10, {"nested": "object"}, "x" * 1001):
            malformed.append(dict(draft, inputs=dict(NM_DEFAULTS, flow=value)))
        malformed.append(dict(draft, inputs={k: v for k, v in NM_DEFAULTS.items() if k != "flow"}))
        malformed.append(dict(draft, inputs=dict(NM_DEFAULTS, unknown="x")))
        for index, bad in enumerate(malformed):
            def rejects(document=bad):
                target.write_text(json.dumps(document), encoding="utf-8")
                expect_input_error(lambda: nm_read_project(target))
            record("Malformed draft rejected %02d" % index, rejects)

    rng = random.Random(557)
    minimum = math.inf
    max_error = 0.0
    samples = 0
    for _ in range(20000):
        pressure = rng.uniform(60, 120)
        adp_t = rng.uniform(.1, 50)
        inlet_t = rng.uniform(adp_t + 1.1e-8, 60)
        outlet_t = rng.uniform(adp_t, inlet_t)
        adp = state_trh(adp_t, 100, pressure)
        enter = state_trh(inlet_t, rng.uniform(0, 100), pressure)
        if enter["w"] <= adp["w"] or not outlet_t < inlet_t - 1e-8:
            continue
        hv = 2501 + 1.86 * outlet_t
        actual = enter["h"] - adp["h"] - (enter["w"] - adp["w"]) * hv
        independent = (1.006 + 1.86 * adp["w"]) * (inlet_t - adp_t) + 1.86 * (enter["w"] - adp["w"]) * (inlet_t - outlet_t)
        assert actual > 0 and math.isclose(actual, independent, rel_tol=1e-10, abs_tol=1e-10)
        minimum = min(minimum, actual)
        max_error = max(max_error, abs(actual - independent))
        samples += 1
    record("Physical bypass denominator agrees with expanded positive expression",
           lambda: _assert(samples == 10720 and minimum > 0))

    for adp_t in (.1, 5., 14., 30., 45.):
        for pressure in (60., 101.325, 120.):
            for delta in (1.0001e-8, 1.1e-8, 2e-8, 1e-7, 1e-6, .001):
                def boundary():
                    i = default_project()["inputs"]
                    i.update(chw1_in=str(adp_t-.1), adp_approach=".1", chw2_in="0",
                             coil_approach=".1", pre_t=str(adp_t), pre_mode="自動旁通因子估算",
                             atm_kpa=str(pressure), allow_reheat="1", allow_humidify="1")
                    adp = state_trh(adp_t, 100, pressure)
                    enter = state_trh(adp_t+delta, 100, pressure)
                    r = condition_air(i, enter, 1., adp_t, adp["w"])
                    assert r["pre_bf"] == 0 and abs(r["energy_residual_kw"]) < 1e-5
                record("Near-boundary real coil %.1f/%.3f/%.6g" % (adp_t, pressure, delta), boundary)

    i = default_project()["inputs"]
    i.update(pre_mode="自動旁通因子估算", pre_t="14", chw1_in="13", adp_approach="1")
    adp = state_trh(14, 100, float(i["atm_kpa"]))
    valid = state_trh(35, 90, float(i["atm_kpa"]))
    hv = 2501+1.86*14
    for name, enthalpy in (("zero", adp["h"]+(valid["w"]-adp["w"])*hv),
                           ("negative", -1000), ("NaN", float("nan")), ("infinite", float("inf"))):
        invalid = dict(valid, h=enthalpy)
        record("Inconsistent internal inlet state rejected: " + name,
               lambda bad=invalid: expect_input_error(lambda: condition_air(i, bad, 1., 22., .008), "pre_t"))

    for authored in ("廠務簡易工具\nV" + VERSION, "分段空調箱設計｜V" + VERSION,
                     "工程快算｜V" + VERSION):
        translated = i18n.translate(authored, "en")
        record("Current version translated: " + repr(authored),
               lambda: _assert(VERSION in translated and not any(0x3400 <= ord(c) <= 0x9fff for c in translated)))

    record("Draft warning translated to English",
           lambda: _assert(i18n.translate("儲存單機草稿", "en") == "Save AHU draft"))
    try:
        from .platform_support import app_data_root
    except ImportError:
        path_check = "not applicable to Windows-only source tree"
    else:
        location = app_data_root(platform="darwin", home="/Users/reviewer", environ={})
        record("Mac callback app-data root is platform-specific",
               lambda: _assert(location == Path("/Users/reviewer/Library/Application Support/Facility_Studio_V5_5")))
        path_check = str(location)
    return {"version": VERSION, "checks": checks, "passed": True,
            "bypass_samples": samples, "minimum_sample_denominator": minimum,
            "maximum_expression_roundoff": max_error, "mac_app_data_check": path_check}


def _assert(value):
    assert value


def run_ui(main, check, pump):
    """Real standalone Tk draft save/load/export checks in the delivered app."""
    from .ahu_desktop import AHUWindow
    from .localized_tk import filedialog, messagebox
    from . import i18n

    language = i18n.language()
    previous = {name: getattr(obj, name) for obj, name in
                ((filedialog, "asksaveasfilename"), (filedialog, "askopenfilename"),
                 (messagebox, "askyesno"), (messagebox, "showerror"))}
    errors = []
    child = None
    try:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "AHU Draft.json"
            filedialog.asksaveasfilename = lambda **kw: str(target)
            filedialog.askopenfilename = lambda **kw: str(target)
            messagebox.askyesno = lambda *args, **kw: True
            messagebox.showerror = lambda *args, **kw: errors.append(args)
            child = AHUWindow(main.root)
            child.vars["flow"].set("abc")
            child.calculate()
            pump()
            check("V558 standalone invalid flow locates field and locks export",
                  lambda: child.result is None and child.bad_key == "flow"
                  and child.export_button.instate(["disabled"]))
            child.save()
            pump()
            check("V558 actual Save writes explicitly marked draft",
                  lambda: nm_read_project(target)["draft"] is True
                  and nm_read_project(target)["inputs"]["flow"] == "abc")
            check("V558 saved invalid draft satisfies standalone close guard", child.may_close)
            child.close()
            child = AHUWindow(main.root)
            child.load()
            pump()
            check("V558 actual Load restores invalid draft without valid result",
                  lambda: child.vars["flow"].get() == "abc" and child.result is None
                  and child.last_good_result is None and child.bad_key == "flow"
                  and child.export_button.instate(["disabled"]))
            i18n.set_language("en", persist=False)
            child.save()
            pump()
            check("V558 draft-save state is displayed in English",
                  lambda: "AHU draft saved" in child.status.cget("text"))
            child.vars["flow"].set(NM_DEFAULTS["flow"])
            child.calculate()
            pump()
            check("V558 corrected standalone draft recalculates and unlocks export",
                  lambda: child.result is not None and child.export_button.instate(["!disabled"]))
            child.save()
            pump()
            check("V558 corrected file is ordinary v4 AHU",
                  lambda: nm_read_project(target)["schema_version"] == 4
                  and "draft" not in nm_read_project(target))
            check("V558 overwritten draft retained as backup",
                  lambda: nm_read_project(target.with_suffix(".json.bak"))["inputs"]["flow"] == "abc")
            prior = target.read_bytes()
            saved = child.saved_hash
            child.vars["flow"].set("abc")
            child.calculate()
            messagebox.askyesno = lambda *args, **kw: False
            child.save()
            pump()
            check("V558 declined draft overwrite preserves file and saved hash",
                  lambda: target.read_bytes() == prior and child.saved_hash == saved
                  and child.export_button.instate(["disabled"]))
            check("V558 draft workflow reports no unexpected dialog error", lambda: not errors)
    finally:
        filedialog.asksaveasfilename = previous["asksaveasfilename"]
        filedialog.askopenfilename = previous["askopenfilename"]
        messagebox.askyesno = previous["askyesno"]
        messagebox.showerror = previous["showerror"]
        if child is not None and child.win.winfo_exists():
            child.close(force=True)
        i18n.set_language(language, persist=False)
        pump()

