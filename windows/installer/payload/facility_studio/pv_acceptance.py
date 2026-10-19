"""Exercise the discoverable PV entry and absolute-pressure conversions."""
import copy
import math


def run_ui(root, app, check, pump):
    from . import i18n
    from .utils import project_hash

    language, geometry = i18n.language(), root.geometry()
    main = app.open_workbench()
    original = copy.deepcopy(main.snapshot())
    scope, page, state = main.task_scope.get(), main.current, main.root.state()
    main_geometry = main.root.geometry()
    try:
        for lang in ("zh-Hant", "en"):
            i18n.set_language(lang, persist=False)
            root.geometry("900x600+0+0")
            main.root.withdraw()
            root.lift()
            pump()
            def visible_shortcut():
                button = app.pv_button
                return (button.winfo_ismapped()
                        and root.winfo_rootx() <= button.winfo_rootx()
                        and button.winfo_rootx()+button.winfo_width() <= root.winfo_rootx()+root.winfo_width())
            check("PV shortcut is visible at minimum width / "+lang, visible_shortcut)
            before = project_hash(main.snapshot())
            app.pv_button.invoke()
            pump()
            check("PV shortcut exposes vacuum without changing project / "+lang,
                  lambda: main.current == 3 and main.task_scope.get() == "全部工程分頁"
                  and bool(main.widgets["pv_q"].winfo_ismapped())
                  and project_hash(main.snapshot()) == before)
            def vacuum_in_view():
                widget, canvas = main.widgets["pv_q"], main.pages[3].canvas
                return (canvas.winfo_rooty() <= widget.winfo_rooty()
                        and widget.winfo_rooty()+widget.winfo_height() <= canvas.winfo_rooty()+canvas.winfo_height())
            check("PV shortcut scrolls to the vacuum flow field / "+lang, vacuum_in_view)
            main.task_scope.set("空調與熱負荷")
            main.show_page(0)
            main.update_visibility()
            main.pv_button.invoke()
            pump()
            check("PV remains reachable from the HVAC-only workbench / "+lang,
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
                             * (float(inputs["gas_temp"])+273.15)/(float(inputs["gas_std_t"])+273.15)
                             * float(inputs["gas_z_ratio"]))
                check("PV absolute pressure and actual flow agree / "+lang+" / "+unit,
                      lambda: math.isclose(float(main.variables["pv_torr"].get()), expected, rel_tol=1e-12)
                      and math.isclose(main.result["gas"]["4"]["actual_lpm"], reference, rel_tol=1e-10))
            main.restore_snapshot(original)
    finally:
        main.restore_snapshot(original)
        main.task_scope.set(scope)
        main.show_page(page)
        main.root.geometry(main_geometry)
        main.root.state(state)
        root.geometry(geometry)
        i18n.set_language(language, persist=False)
        pump()
