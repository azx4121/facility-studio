"""Report completeness and seasonal C1 diagnostics, including native UI checks."""
import copy

from .ahu_engine import nm_calculate, nm_precoil
from .ahu_schema import NM_DEFAULTS
from .engine import calculate, condition_air
from .errors import InputError
from .i18n import translate
from .reports import report
from .schema import default_project
from .utils import project_hash, state_trh
from .version import VERSION


def _error(action, code, field=None):
    try:
        action()
    except InputError as error:
        assert error.code == code and error.field_name == field
        assert not any(0x3400 <= ord(c) <= 0x9fff for c in translate(str(error), "en"))
        return error
    raise AssertionError("Expected structured validation failure")


def hot_main():
    project = default_project()
    project["inputs"].update(sys_type="MAU+FFU+DCC (全外氣/無塵室)",
                             oa_t="40", oa_rh="90", pre_t="22.35",
                             chw1_in="14", adp_approach="1")
    project["inputs"]["pre_mode"] = "自動旁通因子估算"
    return project


def run_checks():
    checks = []

    def record(name, action):
        action()
        checks.append({"name": name, "passed": True})

    project = default_project()
    complete = calculate(project)
    before = project_hash(complete)
    for language in ("zh-Hant", "en"):
        text = report(complete, language=language)
        assert VERSION in text and len(text) > 1000
        record("Complete report remains available in " + language,
               lambda: _assert(project_hash(complete) == before))
    partial = calculate(project, isolate_utilities=True)
    record("Isolated HVAC cannot emit a complete project report",
           lambda: _error(lambda: report(partial), "incomplete_result"))
    for key in complete:
        if key in ("hash", "version", "parts", "oa", "winter_oa", "oa_mass",
                   "mass_residual", "sensible_residual", "inactive_fields", "winter_room",
                   "airflow_basis"):  # diagnostic of how the airflow was set; the quality gate reads it, the report does not
            continue
        bad = copy.deepcopy(complete)
        del bad[key]
        record("Missing report section rejected: " + key,
               lambda value=bad: _error(lambda: report(value), "incomplete_result"))
    for domain, keys in (("gas", ("1", "2", "3", "4")), ("electric", ("UP", "NP"))):
        for key in keys:
            for value in (None, {}, "invalid"):
                bad = copy.deepcopy(complete)
                bad[domain][key] = value
                record("Incomplete utility record rejected: " + domain + "/" + key + "/" + repr(value),
                       lambda result=bad: _error(lambda: report(result), "incomplete_result"))
    for invalid in (None, [], {}, {"gas": {}, "electric": {}}):
        record("Incomplete result object rejected: " + repr(invalid),
               lambda result=invalid: _error(lambda: report(result), "incomplete_result"))
    record("Rejected reports do not mutate isolated result",
           lambda: _assert(partial["gas"] == {} and partial["electric"] == {}))

    record("Main project C1 supersaturation identifies pre_t",
           lambda: _error(lambda: calculate(hot_main()), "supersaturated_air", "pre_t"))
    enter = state_trh(40, 90, 101.325)
    for target in (22.35, 22.7, 23.05):
        for season, label in (("summer", "夏季"), ("winter", "冬季")):
            inputs = hot_main()["inputs"]
            inputs["pre_t"] = str(target)
            error = _error(lambda: condition_air(inputs, enter, 1, 22, .008, season=season),
                           "supersaturated_air", "pre_t")
            record("Main C1 diagnostic context " + season + "/" + str(target),
                   lambda e=error, title=label, t=target: _assert(
                       title + " C1" in str(e) and "ADP 15.0000°C" in str(e)
                       and "入口 40.0000°C / 90.0000%RH" in str(e)
                       and format(t, ".4f") + "°C" in str(e)))
    for season, label in (("summer", "夏季"), ("winter", "冬季")):
        auto = dict(NM_DEFAULTS, c1_in="14", c1_out="19", c1_adp="1", c1_t="22.35")
        auto[season + "_c1_mode"] = "自動需求"
        auto.update(summer_h1_mode="自動需求", winter_h1_mode="自動需求", summer_h2_mode="自動需求", winter_h2_mode="自動需求")
        auto[season + "_t"] = "40"
        auto[season + "_rh"] = "90"
        other = "winter" if season == "summer" else "summer"
        auto[other + "_c1_mode"] = "旁通"
        auto["humidifier"] = "電熱式蒸汽"
        auto["wash_mode"] = "只在需要加濕時"
        record("Standalone automatic C1 field " + season,
               lambda i=auto: _error(lambda: nm_calculate(i), "supersaturated_air", "c1_t"))
        explicit = dict(auto)
        explicit[season + "_c1_mode"] = "指定出口乾球"
        explicit[season + "_c1_t"] = "22.35"
        field = season + "_c1_t"
        error = _error(lambda: nm_calculate(explicit), "supersaturated_air", field)
        record("Standalone explicit seasonal C1 field " + season,
               lambda e=error, title=label: _assert(title + " C1" in str(e)))
        # Inconsistent internal states must never divide by zero or be clamped
        # into a fabricated feasible result.
        adp = state_trh(15, 100, 101.325)
        invalid = dict(enter, h=adp["h"] + (enter["w"] - adp["w"]) * (2501 + 1.86 * 22.35))
        record("Standalone inconsistent internal denominator " + season,
               lambda s=invalid, i=auto, name=season: _error(
                   lambda: nm_precoil(s, i, 101.325, season=name), "invalid_input", "c1_t"))
    return {"version": VERSION, "passed": True, "checks": checks}


def _assert(value):
    assert value


def run_ui(main, check, pump):
    """Exercise the actual delivered widgets and their export/error state."""
    from .ahu_desktop import AHUWindow
    from . import i18n

    original = copy.deepcopy(main.snapshot())
    language = i18n.language()
    child = None
    try:
        for lang, label in (("zh-Hant", "夏季 C1"), ("en", "Summer")):
            i18n.set_language(lang, persist=False)
            main.apply_project(hot_main())
            pump()
            check("V559 native main C1 location and export lock " + lang,
                  lambda: main.result is None and main.bad_key == "pre_t"
                  and main.export_button.instate(["disabled"])
                  and label in main.status.cget("text"))
        p = default_project()
        p["inputs"].update(e_up_eq="1500", u_e_up_eq="kW", e_up_type="一般負載")
        main.apply_project(p)
        pump()
        check("V559 native partial HVAC remains visible with complete export locked",
              lambda: main.result is None and main.partial_hvac is not None
              and main.export_button.instate(["disabled"]))
        check("V559 delivered report API rejects incomplete domain result",
              lambda: bool(_error(lambda: report(main.partial_hvac), "incomplete_result")))
        child = AHUWindow(main.root)
        child.vars["summer_c1_mode"].set("自動需求")
        child.vars["summer_t"].set("40")
        child.vars["summer_rh"].set("90")
        child.vars["c1_in"].set("14")
        child.vars["c1_out"].set("19")
        child.vars["c1_adp"].set("1")
        child.vars["c1_t"].set("22.35")
        for lang in ("zh-Hant", "en"):
            i18n.set_language(lang, persist=False)
            child.calculate()
            pump()
            check("V559 native standalone C1 location and export lock " + lang,
                  lambda: child.result is None and child.bad_key == "c1_t"
                  and child.export_button.instate(["disabled"])
                  and "ADP" in child.status.cget("text"))
        child.vars["summer_c1_mode"].set("指定出口乾球")
        child.vars["summer_c1_t"].set("22.35")
        child.calculate()
        pump()
        check("V559 native standalone explicit C1 uses seasonal field",
              lambda: child.result is None and child.bad_key == "summer_c1_t")
        child.vars["summer_c1_t"].set("38")
        child.calculate()
        pump()
        check("V559 corrected C1 restores calculation and export",
              lambda: child.result is not None and child.export_button.instate(["!disabled"]))
    finally:
        if child is not None and child.win.winfo_exists():
            child.close(force=True)
        i18n.set_language(language, persist=False)
        main.apply_project(original)
        pump()
