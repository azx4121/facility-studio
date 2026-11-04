"""Bounded synthetic checks executed inside the candidate, including frozen builds.

No pytest, test-tree fixtures, manufacturer files, network or user projects.
Headless checks are separate; run() always requires actual Tk widgets.
"""
import copy
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace


def build_commit():
    """Read the bundled identity, never infer it from the builder's checkout."""
    if not getattr(sys, "frozen", False):
        return None
    path = Path(sys._MEIPASS) / "Build_Manifest.json"
    value = json.loads(path.read_text(encoding="utf-8")).get("commit")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Missing or invalid bundled build commit")
    return value


def build_identity():
    """Report the source fingerprint embedded in this executable, never Git."""
    commit = build_commit()
    if commit is None:
        return dict(build_commit=None, build_provenance_sha256=None)
    path = Path(sys._MEIPASS) / "Build_Manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    fields = ("provenance_schema", "commit", "version", "source_platform",
              "build_channel", "source_clean", "build_inputs_sha256", "product_source_sha256")
    selected = {key: manifest[key] for key in fields}
    digest = hashlib.sha256(json.dumps(selected, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return dict(build_commit=commit, build_provenance_sha256=digest)


def synthetic_plan():
    from . import capacity_planning as model
    p = model.new_plan("Synthetic candidate acceptance")
    p.update(scope="Synthetic single electric service only", scope_confirmed=True,
             synthetic=True, additional_margin_pct=10, margin_reason="Synthetic 10% owner margin")
    for kind, ident, amount in (("demand", "current", 100), ("demand", "expansion", 60),
                                ("capacity", "supply", 100)):
        r = model.new_row(kind, ident)
        r.update(boundary="SYNTHETIC-SERVICE", values=dict(summer=amount, winter=amount),
                 conditions=dict(voltage_v=380, phases=3, frequency_hz=60),
                 source=dict(reference="Synthetic hand calculation", revision="R1", fingerprint=""))
        if kind == "demand":
            r.update(phase=ident, demand_complete=ident == "current")
            p["demands"].append(r)
        else:
            r.update(quantity=3, derating=.9)
            p["capacities"].append(r)
    return p


def synthetic_photometry(folder):
    ies = "\n".join(("IESNA:LM-63-2002", "[TEST]Synthetic candidate only", "[LUMINAIRE]Synthetic 100 cd",
                     "TILT=NONE", "1 -1 1 2 1 1 2 0.1 0.2 0.03 1 1 10", "0 90", "0", "100 100"))
    # Rotational LDT: 500 cd/klm * 2 klm * 0.5 factor = 500 cd.
    ldt = ["Synthetic maker", 3, 1, 4, 90, 3, 45, "synthetic", "Synthetic LDT", "none",
           "synthetic.ldt", "2026", 200, 100, 30, 180, 80, 0, 0, 0, 0,
           100, 100, .5, 0, 1, -1, "LED", 2000, "4000K", "80", 10]
    ldt += [0] * 10 + [0, 90, 180, 270] + [0, 45, 90] + [500, 500, 500]
    paths = (folder / "synthetic.ies", folder / "synthetic.ldt")
    paths[0].write_text(ies, encoding="utf-8")
    paths[1].write_text("\n".join(map(str, ldt)), encoding="utf-8")
    return paths


def run_headless(folder, check):
    from . import capacity_planning as capacity
    from .photometry import load_photometry, intensity_cd
    from .lighting_direct import calculate_direct, point_illuminance
    from .lighting_direct_report import direct_html, grid_csv
    from .air_chart import full_chart_data
    from .quick_tools import psychrometric
    from .utils import state_tw
    from .simple_engines import calculate_tool
    from .simple_schema import defaults

    p = synthetic_plan()
    group = capacity.evaluate_plan(p)["alternatives"][0]["groups"][0]
    case = group["cases"][0]
    check("candidate capacity incomplete demand preserves known subtotal", case["known_subtotal"] == 160)
    check("candidate capacity incomplete demand cannot show pass or zero deficit",
          group["normal_status"] == group["n_minus_one_status"] == "待資料／待覆核"
          and all(case[k] is None for k in ("combined", "design_demand", "normal_headroom",
                                           "n_minus_one_headroom", "normal_deficit", "n_minus_one_deficit")))
    p["demands"][1]["demand_complete"] = True
    result = capacity.evaluate_plan(p)
    case = result["alternatives"][0]["groups"][0]["cases"][0]
    check("candidate capacity confirmed arithmetic and largest-unit N-1",
          abs(case["design_demand"] - 176) < 1e-10 and case["normal_capacity"] == 270
          and case["n_minus_one_capacity"] == 180 and abs(case["n_minus_one_headroom"] - 4) < 1e-10)
    report = folder / "capacity.txt"
    report.write_text(capacity.capacity_report(result), encoding="utf-8")
    check("candidate capacity report exports synthetic limitation", "合成驗證案例，非真實專案驗證" in report.read_text(encoding="utf-8"))

    ies_path, ldt_path = synthetic_photometry(folder)
    ies, ldt = load_photometry(ies_path), load_photometry(ldt_path)
    check("candidate IES and LDT actual file import", intensity_cd(ies, 45, 45) == 100 and intensity_cd(ldt, 45, 45) == 500)
    fixture = dict(photometry="P1", x_m=2, y_m=2, z_m=3, yaw_deg=0, multiplier=1)
    scene = dict(length_m=4, width_m=4, workplane_m=1, edge_m=0, nx=4, ny=4,
                 maintenance=.8, fixtures=[fixture])
    check("candidate direct-lighting independent nadir equation", point_illuminance(ies, fixture, 2, 2, 1) == 25)
    result = calculate_direct({"P1": ies}, scene)
    expected = [100 * 2 / ((x - 2)**2 + (y - 2)**2 + 4)**1.5 * .8
                for y in result["grid"]["y_m"] for x in result["grid"]["x_m"]]
    check("candidate direct-lighting grid matches inverse-square cosine law",
          all(abs(a - b) < 1e-10 for a, b in zip(sum(result["grid"]["lux"], []), expected)))
    html = folder / "direct.html"
    html.write_text(direct_html(result), encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(grid_csv(result))))
    (folder / "direct.csv").write_text(grid_csv(result), encoding="utf-8")
    (folder / "direct.json").write_text(json.dumps(result, allow_nan=False), encoding="utf-8")
    check("candidate direct-lighting exports trace source and retain scope",
          len(rows) == 16 and ies.source_sha256 in html.read_text(encoding="utf-8")
          and result["reflected_lux"] is None and result["ugr"] is None)

    a = psychrometric("乾球＋RH", 35, 70, 101.325)
    b = psychrometric("乾球＋RH", 18, 90, 101.325)
    chart = full_chart_data(a, b)
    check("candidate full chart contains every line family", all(chart[key] for key in
          ("curves", "enthalpy_lines", "wetbulb_lines", "volume_lines", "drybulb_lines", "humidity_lines")))
    high = state_tw(75, .99, 60)
    inputs = dict(defaults("air"), temperature="75", rh=repr(high["rh"]), atmosphere="60", compare="0")
    high_result = calculate_tool("air", inputs)["state"]
    high_chart = full_chart_data(high_result)
    check("candidate high-humidity wet-bulb and full chart boundary",
          abs(high_result["w"] - .99) < 1e-12 and high_result["wetbulb_c"] < 75
          and high_chart["w_max_gkg"] == 1000)


def run(root, app, check):
    from .capacity_planning_ui import CapacityPlanningWindow
    from . import capacity_planning_ui
    from . import capacity_planning as capacity, lighting_layout_ui as lighting
    from .air_chart import FullAirChart

    with TemporaryDirectory(prefix="facility-candidate-") as temporary:
        folder = Path(temporary)
        run_headless(folder, check)
        # Real Tk editor, with a synthetic source owner. No production project is touched.
        from .contributions import empty_ledger
        workspace = dict(project_id="candidate-synthetic", main=dict(inputs={}), ahus=[],
                         demand_ledger=empty_ledger())
        owner = SimpleNamespace(children=[], session_snapshot=lambda: copy.deepcopy(workspace))
        window = CapacityPlanningWindow(root, owner)
        original_error = capacity_planning_ui.messagebox.showerror
        def fail_dialog(*args, **kwargs):
            raise AssertionError("Candidate editor displayed an error: " + str(args))
        capacity_planning_ui.messagebox.showerror = fail_dialog
        try:
            window.install(synthetic_plan())
            root.update()
            window.trees["demand"].selection_set("expansion")
            dialog = window.edit("demand")
            check("candidate Tk demand completeness begins unconfirmed",
                  dialog.variables["top", "demand_complete"].get() is False)
            dialog.variables["top", "demand_complete"].set(True)
            dialog.save()
            check("candidate Tk edit resets separate scope confirmation", not window.confirmed.get())
            window.confirmed.set(True)
            result = window.refresh()
            check("candidate Tk confirmed plan recalculates", abs(result["alternatives"][0]["groups"][0]["cases"][0]["design_demand"] - 176) < 1e-10)
            before = copy.deepcopy(window.plan)
            dialog = window.edit("demand")
            dialog.variables["values", "summer"].set("999")
            dialog.win.destroy()
            check("candidate Tk cancel retains saved demand", window.plan == before)
            saved = window.save(folder / "plan.json")
            exported = window.export(folder / "gui-capacity.txt")
            check("candidate Tk capacity save and report export", capacity.read_plan(saved) == window.plan and exported.is_file())
        finally:
            capacity_planning_ui.messagebox.showerror = original_error
            window.close(force=True)

        direct = lighting.DirectLightingWindow(root)
        original_open = lighting.filedialog.askopenfilename
        original_save = lighting.filedialog.asksaveasfilename
        try:
            for path in synthetic_photometry(folder):
                lighting.filedialog.askopenfilename = lambda path=path, **kwargs: str(path)
                direct.import_source()
            check("candidate Tk imports both photometry formats", len(direct.sources) == 2)
            for key, value in dict(length_m="4", width_m="4", workplane_m="1", edge_m="0", nx="4", ny="4", maintenance=".8").items():
                direct.variables[key].set(value)
            direct.schedule.insert("1.0", "P1,2,2,3,0,1")
            direct.calculate()
            root.update()
            for extension in ("html", "csv", "json"):
                path = folder / ("gui-direct." + extension)
                lighting.filedialog.asksaveasfilename = lambda path=path, **kwargs: str(path)
                direct.export(extension)
                check("candidate Tk direct-lighting exports " + extension, path.is_file() and path.stat().st_size > 0)
            direct.variables["maintenance"].set(".7")
            target = folder / "stale-direct.html"
            lighting.filedialog.asksaveasfilename = lambda **kwargs: str(target)
            try:
                direct.export("html")
            except ValueError:
                check("candidate Tk changed lighting blocks stale export", not target.exists() and direct.result is None)
            else:
                check("candidate Tk changed lighting blocks stale export", False)
        finally:
            lighting.filedialog.askopenfilename = original_open
            lighting.filedialog.asksaveasfilename = original_save
            direct.win.destroy()

        app.show_tool("air")
        page = app.active_page()
        page.reset()
        page.variables["compare"].set("1")
        page.calculate()
        opened = []
        try:
            opened.append(page.open_air_chart())
            root.update()
            chart = next(w for w in opened[0].winfo_children() if isinstance(w, FullAirChart))
            original = dict(chart.state)
            check("candidate Tk full chart renders extended families", all(chart.find_withtag(tag) for tag in
                  ("enthalpy_ruler", "volume", "wetbulb", "state_summary", "snapshot_label")))
            initial = chart.point_xy
            chart.zoom_at(1.5, *initial)
            check("candidate Tk chart preserves zoom anchor", chart.zoom == 1.5 and math.dist(chart.point_xy, initial) < 1e-7)
            chart.fit_view()
            page.variables["temperature"].set("30")
            page.calculate()
            opened.append(page.open_air_chart())
            root.update()
            fresh = next(w for w in opened[-1].winfo_children() if isinstance(w, FullAirChart))
            check("candidate Tk repeated chart opens independent snapshots", chart.state == original and fresh.state["t"] == 30)
        finally:
            for window in opened:
                if window is not None:
                    window.destroy()
