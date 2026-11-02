"""Verify the simple PV workflow and the separately requested workbench route."""
import copy
import math


def run_ui(root, app, check, pump):
    from . import i18n
    from .utils import project_hash
    from .version import BUILD_VERSION

    language, geometry, original_tool = i18n.language(), root.geometry(), app.current
    prior_main = app.workbench
    main = None
    saved_vacuum = None
    try:
        for lang in ("zh-Hant", "en"):
            i18n.set_language(lang, persist=False)
            app.show_tool("electrical")
            root.geometry("900x600+0+0")
            root.deiconify()
            pump()
            check("PV shortcut visible in simple tools / " + lang,
                  lambda: app.pv_button.winfo_ismapped()
                  and app.pv_button.winfo_rootx() + app.pv_button.winfo_width() <= root.winfo_rootx() + root.winfo_width())
            app.pv_button.invoke()
            pump()
            page = app.active_page()
            if saved_vacuum is None:
                saved_vacuum = page.data()
            check("PV opens on the existing simple page without creating a workbench / " + lang,
                  lambda: app.current == "vacuum" and not app.workbench_mode
                  and app.workbench is prior_main and page.widgets["vacuum_p"].winfo_ismapped()
                  and BUILD_VERSION in root.title())
            page.reset()
            for unit, expected in (("kPa(abs)", 150 * 101325 / 760 / 1000),
                                   ("mbar(abs)", 150 * 101325 / 760 / 100),
                                   ("Torr(abs)", 150.0)):
                page.variables["vacuum_unit"].set(unit)
                page.calculate()
                pump()
                data = page.data()
                expected_flow = 100 * float(data["standard_p"]) * 1000 / (150 * 101325 / 760) * (float(data["temperature"]) + 273.15) / (float(data["standard_t"]) + 273.15)
                check("Simple PV absolute-pressure and gas-flow equivalence / " + lang + " / " + unit,
                      lambda: page.result is not None
                      and math.isclose(float(page.variables["vacuum_p"].get()), expected, rel_tol=1e-12)
                      and math.isclose(page.result["actual_lpm"], expected_flow, rel_tol=1e-10))

        # The full workbench still offers its own PV route after an explicit
        # workbench action; the simple sidebar never navigates there.
        main = app.open_workbench()
        original = copy.deepcopy(main.snapshot())
        scope, original_page = main.task_scope.get(), main.current
        for lang in ("zh-Hant", "en"):
            i18n.set_language(lang, persist=False)
            main.task_scope.set("空調與熱負荷")
            main.show_page(0)
            main.update_visibility()
            before = project_hash(main.snapshot())
            main.pv_button.invoke()
            pump()
            check("Explicit workbench PV route retains project / " + lang,
                  lambda: main.current == 3 and bool(main.nav[3].winfo_manager())
                  and project_hash(main.snapshot()) == before)
            main.suspended = True
            for key, value in dict(pv_q="100", u_pv="SLPM", pv_torr="150", pv_pressure_unit="Torr(abs)").items():
                main.variables[key].set(value)
            main.pv_unit_last = "Torr(abs)"
            main.suspended = False
            for unit, expected in (("kPa(abs)", 19.998355263157894),
                                   ("mbar(abs)", 199.98355263157896),
                                   ("Torr(abs)", 150.0)):
                main.variables["pv_pressure_unit"].set(unit)
                main.recalculate()
                pump()
                inputs = main.snapshot()["inputs"]
                reference = (100 * float(inputs["gas_std_kpa"]) * 1000 / (150 * 133.322368421)
                             * (float(inputs["gas_temp"]) + 273.15) / (float(inputs["gas_std_t"]) + 273.15)
                             * float(inputs["gas_z_ratio"]))
                check("Workbench PV pressure and actual-flow equivalence / " + lang + " / " + unit,
                      lambda: math.isclose(float(main.variables["pv_torr"].get()), expected, rel_tol=1e-12)
                      and math.isclose(main.result["gas"]["4"]["actual_lpm"], reference, rel_tol=1e-10))
            main.restore_snapshot(original)
        main.task_scope.set(scope)
        main.show_page(original_page)
    finally:
        if main is not None:
            main.restore_snapshot(original)
        app.show_tool("vacuum")
        page = app.active_page()
        if saved_vacuum is not None:
            page.suspended = True
            for key, value in saved_vacuum.items():
                page.variables[key].set(value)
            page.suspended = False
            page.previous = page.data()
            page.update_visibility()
            page.calculate()
        app.show_tool(original_tool)
        root.geometry(geometry)
        i18n.set_language(language, persist=False)
        pump()
