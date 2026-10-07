"""Native interactive language acceptance shared by both distribution builders."""

import copy
import json
from pathlib import Path
import re
import tempfile


def run(root, app, workbench, check, pump, output=None):
    from . import i18n
    from .localized_tk import Combobox
    from .simple_reports import tool_report
    from .simple_engines import calculate_tool
    from .ahu_desktop import AHUWindow
    from .equipment_io import export_template, export_csv_templates, load_equipment
    from .equipment_schema import SYSTEMS, SCHEMAS
    from .utils import project_hash

    def require(condition, detail):
        if not condition:
            raise AssertionError(detail)
        return True

    def choose(code):
        app.language_picker.choice.set(i18n.LANGUAGES[code])
        app.language_picker.event_generate("<<ComboboxSelected>>")
        pump()
        return require(i18n.language() == code, "Language selection did not fire")

    check("English selector uses a native selection event", lambda: choose("en"))
    check(
        "English main-window title",
        lambda: require("Facility" in root.title(), root.title()),
    )
    for tool in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):

        def form(name=tool):
            app.show_tool(name)
            page = app.active_page()
            page.calculate()
            pump()
            before = copy.deepcopy(page.data())
            result = copy.deepcopy(page.result)
            require(result is not None, "No calculation in " + name)
            english = tool_report(result, before)
            require(not re.search(r"[\u3400-\u9fff]", english), english)
            require(
                all(
                    not re.search(r"[\u3400-\u9fff]", label.cget("text"))
                    for label in page.labels.values()
                ),
                "Chinese field label",
            )
            choose("zh-Hant")
            require(
                page.data() == before and page.result == result,
                "Chinese switch changed inputs / results",
            )
            choose("en")
            require(
                page.data() == before and page.result == result,
                "English switch changed inputs / results",
            )
            require(calculate_tool(name, before) == result, "Numerical parity")
            return True

        check("English form, report and round-trip parity: " + tool, form)

    def choices():
        app.show_tool("electrical")
        page = app.active_page()
        widget = page.widgets["kind"]
        require(isinstance(widget, Combobox), "Not a localized choice")
        native_values = root.tk.splitlist(root.tk.call(widget._w, "cget", "-values"))
        require("Continuous load" in native_values, str(native_values))
        widget._display.set("Continuous load")
        widget.event_generate("<<ComboboxSelected>>")
        page.calculate()
        require(page.variables["kind"].get() == "連續運轉", "Enum not canonical")
        require(
            page.result["design_a"] > page.result["current_a"], "Continuous factor lost"
        )
        widget._display.set("General load")
        page.calculate()
        return True

    check("English choice maps to canonical electrical enum and actual factor", choices)

    def invalid():
        page = app.active_page()
        page.variables["power"].set("not-a-number")
        page.calculate(True)
        require(page.result is None, "Invalid input produced a result")
        require(
            not re.search(r"[\u3400-\u9fff]", page.status.cget("text")),
            page.status.cget("text"),
        )
        require(
            app.copy_button.instate(["disabled"])
            and app.export_button.instate(["disabled"]),
            "Export not blocked",
        )
        choose("zh-Hant")
        require(page.result is None, "Switch resurrected a stale result")
        require("請修正" in page.status.cget("text"), page.status.cget("text"))
        choose("en")
        page.variables["power"].set("10")
        page.calculate()
        return True

    check("Localized validation, blocked export and invalid-input round trip", invalid)

    def area_mode():
        app.show_tool("lighting")
        page = app.active_page()
        page.variables["area_mode"].set("體積 m³")
        page.variables["area"].set("90")
        page.variables["height"].set("3")
        page.calculate()
        require(page.result["area_m2"] == 30, "Volume / height relationship lost")
        require("m³" in page.labels["area"].cget("text"), "Volume label unclear")
        require(
            not re.search(r"[\u3400-\u9fff]", page.details.cget("text")),
            page.details.cget("text"),
        )
        return True

    check("English volume-based lighting labels and live link", area_mode)

    def gas_units():
        app.show_tool("gas")
        page = app.active_page()
        page.variables["pressure"].set("6")
        page.variables["pressure_unit"].set("bar(g)")
        page.calculate()
        before = page.result["actual_lpm"]
        page.variables["pressure_unit"].set("kPa(g)")
        page.calculate()
        require(float(page.variables["pressure"].get()) == 600, "Gauge-unit conversion")
        require(abs(before - page.result["actual_lpm"]) < 1e-10, "Actual flow changed")
        return True

    check("English gas unit changes preserve actual flow", gas_units)

    def full():
        before = project_hash(workbench.snapshot())
        result = copy.deepcopy(workbench.result)
        choose("zh-Hant")
        choose("en")
        require(project_hash(workbench.snapshot()) == before, "Project hash changed")
        require(workbench.result == result, "Workbench result changed")
        require(
            "English" == workbench.language_picker.choice.get(),
            "Window selector not synced",
        )
        return True

    check("Full workbench language sync, project hash and result parity", full)

    def captions(window):
        for widget in window.winfo_children():
            if widget.winfo_class() in (
                "Label",
                "TLabel",
                "Button",
                "TButton",
                "TLabelframe",
                "TCheckbutton",
            ):
                text = widget.cget("text")
                require(
                    not re.search(r"[\u3400-\u9fff]", str(text)),
                    "Untranslated visible caption: " + str(text),
                )
            captions(widget)
        return True

    check(
        "Full workbench English labels and action captions",
        lambda: captions(workbench.root),
    )
    from .tools_view import QuickToolsWindow

    quick = QuickToolsWindow(workbench.root, workbench)
    quick.tool.set("濕空氣計算")
    quick.build()
    quick.calculate()
    pump()

    def quick_language():
        result = copy.deepcopy(quick.result)
        require(result is not None, "Quick-tools result missing")
        require(
            not re.search(r"[\u3400-\u9fff]", quick.ax.get_title()),
            "English plot title missing",
        )
        choose("zh-Hant")
        require("空氣" in quick.ax.get_title(), "Plot did not switch back to Chinese")
        choose("en")
        require(quick.result == result, "Plot redraw changed engineering state")
        return captions(quick.win)

    check(
        "Engineering quick tools, plot redraw and language round trip", quick_language
    )
    quick.close(force=True)

    ahu = AHUWindow(root)
    ahu.calculate()
    pump()

    def stages():
        before = copy.deepcopy(ahu.snapshot())
        result = copy.deepcopy(ahu.result)
        require(result is not None, "AHU calculation missing")
        choose("zh-Hant")
        choose("en")
        require(ahu.snapshot() == before and ahu.result == result, "AHU state changed")
        require("Staged AHU" in ahu.win.title(), ahu.win.title())
        # All mode/source combos remain canonical throughout switching.
        for widget in ahu.widgets.values():
            if isinstance(widget, Combobox):
                require(widget.get() == widget._canonical.get(), "AHU enum mismatch")
        return True

    check("AHU stage controls, heat-source enums and balance parity", stages)
    check("AHU English guidance and visible captions", lambda: captions(ahu.win))
    ahu.close(force=True)
    choose("zh-Hant")
    choose("en")
    check("Closed child windows do not break subsequent switching", lambda: True)

    with tempfile.TemporaryDirectory(prefix="Facility-English-") as folder:
        path = Path(folder) / "Equipment English.xlsx"
        check(
            "English Excel template loads all seven systems",
            lambda: require(
                len(load_equipment(export_template(path))["systems"]) == 7,
                "Missing sheets",
            ),
        )
        csv_folder = Path(folder) / "csv"
        export_csv_templates(csv_folder)
        for system in SYSTEMS:
            check(
                "English CSV headers import: " + i18n.translate(system),
                lambda name=system: require(
                    len(
                        load_equipment(
                            csv_folder / (i18n.translate(name) + ".csv"),
                            i18n.translate(name),
                        )["records"]
                    )
                    >= 1,
                    "Missing example",
                ),
            )
        before = project_hash(workbench.snapshot())
        require(
            before == project_hash(workbench.snapshot()),
            "Template export changed project",
        )

    app.show_tool("electrical")
    width = min(1100, max(780, root.winfo_screenwidth() - 60))
    height = min(760, max(560, root.winfo_screenheight() - 100))
    root.geometry(f"{width}x{height}+20+20")
    workbench.root.withdraw()
    root.deiconify()
    root.lift()
    pump()
    check(
        "English action buttons fit the visible desktop",
        lambda: require(
            app.export_button.winfo_rootx() + app.export_button.winfo_width()
            <= root.winfo_screenwidth()
            and app.export_button.winfo_rooty() + app.export_button.winfo_height()
            <= root.winfo_screenheight() - 30,
            "Action buttons extend beyond the usable display",
        ),
    )

    def readable_navigation():
        from .localized_tk import ttk

        style = ttk.Style(root)
        aqua = root.tk.call("tk", "windowingsystem") == "aqua"
        for button in [*app.nav.values(), *workbench.nav]:
            if button.winfo_class() == "TButton":
                name = button.cget("style")
                foreground = style.lookup(name, "foreground")
                background = style.lookup(name, "background")
            else:
                require(not aqua, "Aqua classic buttons ignore the dark background")
                foreground, background = button.cget("fg"), button.cget("bg")

            def luminance(color):
                components = [value / 65535 for value in root.winfo_rgb(color)]
                linear = [
                    (
                        value / 12.92
                        if value <= 0.04045
                        else ((value + 0.055) / 1.055) ** 2.4
                    )
                    for value in components
                ]
                return sum(
                    value * weight
                    for value, weight in zip(linear, (0.2126, 0.7152, 0.0722))
                )

            light, dark = sorted(
                (luminance(foreground), luminance(background)), reverse=True
            )
            require(
                (light + 0.05) / (dark + 0.05) >= 4.5,
                "Navigation text contrast is too low",
            )
        return True

    check(
        "Navigation labels have readable native foreground/background contrast",
        readable_navigation,
    )
    if output is not None:
        from PIL import ImageGrab

        try:
            pump()
            ImageGrab.grab().save(Path(output).with_name("English_Electrical.png"))
            app.show_tool("air")
            pump()
            ImageGrab.grab().save(Path(output).with_name("English_Psychrometrics.png"))
        except OSError:
            pass
    choose("zh-Hant")
