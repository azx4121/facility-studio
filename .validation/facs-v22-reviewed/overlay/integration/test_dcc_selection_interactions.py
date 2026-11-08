"""Independent DCC persistence, report and callback-boundary regression checks.

Run each source mirror in a fresh process. Real production functions are called;
recording widgets replace window-system boundaries only. This is not a GUI,
native binary, display, screenshot or as-built engineering acceptance test.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import re
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
RESOURCE = HERE / "dcc_interaction_resources"
KEY = "dcc_unit_airflow_cmh"
CJK = re.compile(r"[\u3400-\u9fff]")
ENVIRONMENT_KEYS = (
    "FACILITY_STUDIO_DATA",
    "FACILITY_STUDIO_PREFERENCES",
    "XDG_CACHE_HOME",
    "MPLCONFIGDIR",
    "PYTHONDONTWRITEBYTECODE",
)
_REQUESTED_CONFIGURATION = None


def restore_process_state(environment, search_path, dont_write_bytecode):
    """Restore only this suite's environment keys and interpreter settings."""
    for key, value in environment.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    sys.path[:] = search_path
    sys.dont_write_bytecode = dont_write_bytecode


class Var:
    def __init__(self, value="", **kw):
        self.value = value
        self.callbacks = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        for cb in self.callbacks:
            cb()

    def trace_add(self, mode, cb):
        self.callbacks.append(cb)


class Widget:
    """Record outputs; model only the documented after/Destroy boundary."""

    instances: ClassVar[list] = []
    next_job = 0

    def __init__(self, *args, **kw):
        self.options = dict(kw)
        self.grid_options = {}
        self.focused = False
        self.children = []
        self.idle_jobs = {}
        Widget.instances.append(self)
        if args and isinstance(args[0], Widget):
            args[0].children.append(self)
        self.destroyed = False
        self.selected = 0
        self.bindings = {}
        self.tabs = []
        self.tk = SimpleNamespace(call=lambda *a: None)

    def configure(self, **kw):
        self.options.update(kw)

    config = configure

    def cget(self, key):
        return self.options[key]

    def grid(self, **kw):
        self.grid_options.update(kw)

    def pack(self, **kw):
        pass

    def columnconfigure(self, *a, **kw):
        pass

    def rowconfigure(self, *a, **kw):
        pass

    def title(self, *a):
        pass

    def geometry(self, *a):
        pass

    def minsize(self, *a):
        pass

    def bind(self, name, cb, **kw):
        self.bindings[name] = cb
        return "binding-" + name

    def unbind(self, name, funcid=None):
        self.bindings.pop(name, None)

    def map_event(self, widget=None):
        if "<Map>" in self.bindings:
            self.bindings["<Map>"](SimpleNamespace(widget=widget or self))

    def focus_set(self):
        if self.destroyed:
            from tkinter import TclError

            raise TclError("bad window path name: destroyed recording widget")
        self.focused = True

    def winfo_exists(self):
        return not self.destroyed

    def destroy(self):
        if self.destroyed:
            return
        for child in list(self.children):
            child.destroy()
        if "<Destroy>" in self.bindings:
            self.bindings["<Destroy>"](SimpleNamespace(widget=self))
        self.destroyed = True

    def add(self, page, **kw):
        self.tabs.append((page, kw))

    def select(self, index=None):
        if index is not None:
            self.selected = index
        return self.selected

    def index(self, value):
        return value

    def after_idle(self, cb):
        Widget.next_job += 1
        job = "recording-after-" + str(Widget.next_job)
        self.idle_jobs[job] = cb
        return job

    def after(self, delay, cb):
        return self.after_idle(cb)

    def after_cancel(self, job):
        for owner in Widget.instances:
            owner.idle_jobs.pop(job, None)

    @staticmethod
    def drain_idle():
        for owner in list(Widget.instances):
            for job, callback in list(owner.idle_jobs.items()):
                owner.idle_jobs.pop(job, None)
                # Tk deletes the registered Tcl command on widget destruction,
                # but does not cancel its after event. A real Tcl control below
                # confirms this boundary without opening a display.
                if owner.destroyed:
                    from tkinter import TclError

                    raise TclError("invalid command name: destroyed timer owner")
                callback()

    def item(self, name, **kw):
        pass

    def selection_set(self, name):
        self.selection = name

    def reveal(self, widget):
        self.revealed = widget

    def yview_scroll(self, *a):
        pass

    def selection_range(self, *a):
        pass

    def icursor(self, *a):
        pass


class Scroll(Widget):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.body = Widget(self)
        self.canvas = Widget(self)


def numerals(text):
    # Established localization writes Chinese section ordinals as English digits
    # and 全外氣 as 100% OA. Remove only those named, non-engineering labels.
    text = text.replace("100% OA / cleanroom", "OA / cleanroom")
    text = re.sub(
        r"(?m)^[1-5]\.(?= (?:Design conditions|HVAC duties and states|Piping / velocity / pressure drop|Electrical candidates|Key formulas and explanation))",
        "",
        text,
    )
    return Counter(re.findall(r"\d+(?:[.,]\d+)*", text))


class Interactions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Register before any setup side effect. unittest and pytest execute
        # class cleanups even when setUpClass itself raises.
        cls.addClassCleanup(
            restore_process_state,
            {key: os.environ.get(key) for key in ENVIRONMENT_KEYS},
            list(sys.path),
            sys.dont_write_bytecode,
        )
        configuration = _REQUESTED_CONFIGURATION or (
            Path(os.environ.get("FACILITY_SOURCE_TREE", HERE.parent)),
            os.environ.get("FACILITY_TEST_PLATFORM", "windows"),
            None,
        )
        configure(*configuration)
        loaded = sys.modules.get("facility_studio")
        if (
            loaded
            and Path(loaded.__file__).resolve().parent
            != SOURCE / MIRROR / "facility_studio"
        ):
            raise RuntimeError(
                "Each mirror requires a fresh process; another source was already imported"
            )
        from facility_studio import (
            dcc_sizing,
            engine,
            fusion_settings,
            html_report,
            i18n,
            project_store,
            reports,
            schema,
            workspace_store,
        )
        from facility_studio.contributions import empty_ledger
        from facility_studio.desktop import DesktopApp
        from facility_studio.main_view import MainView

        cls.engine, cls.schema, cls.reports, cls.html, cls.i18n = (
            engine,
            schema,
            reports,
            html_report,
            i18n,
        )
        cls.DesktopApp, cls.MainView, cls.ws, cls.store = (
            DesktopApp,
            MainView,
            workspace_store,
            project_store,
        )
        cls.settings, cls.dcc, cls.empty_ledger = (
            fusion_settings,
            dcc_sizing,
            staticmethod(empty_ledger),
        )
        cls.MAU = next(
            x for x in schema.FIELDS["sys_type"]["options"] if x.startswith("MAU")
        )
        cls.AHU = next(
            x for x in schema.FIELDS["sys_type"]["options"] if x.startswith("AHU")
        )

    def project(self, value=None, system=None):
        p = self.schema.default_project()
        p["inputs"]["sys_type"] = system or self.MAU
        if value is not None:
            p["inputs"][KEY] = value
        return p

    def shell(self, p=None):
        p = copy.deepcopy(p or self.project())
        s = self.DesktopApp.__new__(self.DesktopApp)
        s.variables = {
            k: Var(v) for k, v in p["inputs"].items() if k in self.schema.FIELDS
        }
        s.extra_inputs = {
            k: v for k, v in p["inputs"].items() if k not in self.schema.FIELDS
        }
        s.pd = {
            k: {f: Var(v) for f, v in row.items()}
            for k, row in p["pressure_drop"].items()
        }
        s.provenance = copy.deepcopy(p["provenance"])
        s.field_drafts = {}
        s.transfer_receipts = []
        s.demand_ledger = self.empty_ledger()
        s.ahu_documents = {}
        s.comparisons = {}
        s.children = []
        s.unit_previous = {}
        s.suspended = False
        s.after_id = None
        s.root = Widget()
        s.project_id = "independent-dcc-owner"
        s.saved_workspace_hash = "unsaved"
        s.recovery_token = "dcc-interaction"
        s.recovery_job = None
        s.bad_key = None
        s.bad_pd = None
        s.undo_project = None
        s.undo_aux = None
        s.result = None
        s.last_good_result = None
        s.events = []
        for name in (
            "interlocks",
            "normalize_auto_values",
            "update_visibility",
            "notify_children",
            "refresh_demand_views",
            "refresh_session_status",
            "schedule_recovery",
            "changed",
        ):
            setattr(s, name, lambda *a, _name=name, **kw: s.events.append(_name))

        def recalculate(*a, **kw):
            s.events.append("recalculate")
            try:
                s.result = self.engine.calculate(s.snapshot())
                s.bad_key = None
            except ValueError as exc:
                s.result = None
                s.bad_key = getattr(exc, "field_name", None)

        s.recalculate = recalculate
        s.summary, s.psy_label, s.topology, s.grid = (
            Widget(),
            Widget(),
            Widget(),
            Widget(),
        )
        s.result_labels = {n: Widget() for n in range(1, 7)}
        s.latent_text = Var()
        s.widgets = {k: Widget() for k in self.schema.FIELDS}
        s.pages = {i: Widget() for i in range(10)}
        s.view_mode = Var()
        s.current = 0

        def show_page(n):
            s.current = n
            s.events.append(("show_page", n))

        s.show_page = show_page
        return s

    def settings_boundary(self):
        Widget.instances = []
        from facility_studio import localized_tk, main_view, platform_support, window_geometry

        stack = ExitStack()
        # Recording widgets have no display/HWND. Keep real sizing arithmetic
        # with a fixed work area only inside this headless settings boundary.
        stack.enter_context(
            patch.object(window_geometry, "_windows_work_area", return_value=(1024, 728))
        )
        stack.enter_context(
            patch.object(
                localized_tk, "tk", SimpleNamespace(Toplevel=Widget, StringVar=Var)
            )
        )
        stack.enter_context(
            patch.object(
                localized_tk,
                "ttk",
                SimpleNamespace(
                    **{
                        k: Widget
                        for k in (
                            "Label",
                            "Notebook",
                            "Combobox",
                            "Entry",
                            "Frame",
                            "Button",
                        )
                    }
                ),
            )
        )
        self.dialogs = []
        stack.enter_context(
            patch.object(
                localized_tk,
                "messagebox",
                SimpleNamespace(
                    showerror=lambda *a, **kw: self.dialogs.append((a, kw))
                ),
            )
        )
        stack.enter_context(
            patch.object(localized_tk, "attach_window", lambda *a: None)
        )
        stack.enter_context(patch.object(main_view, "ScrollPage", Scroll))
        stack.enter_context(
            patch.object(platform_support, "wheel_sequences", lambda *a: ())
        )
        return stack

    def test_00_fixture_and_source_identity(self):
        manifest = json.loads(
            (RESOURCE / "fixture_manifest.json").read_text(encoding="utf8")
        )
        fixture = RESOURCE / manifest["file"]
        self.assertEqual(
            hashlib.sha256(fixture.read_bytes()).hexdigest(), manifest["sha256"]
        )
        for module in (
            self.engine,
            self.schema,
            self.reports,
            self.html,
            self.settings,
            self.dcc,
        ):
            self.assertTrue(
                Path(module.__file__).resolve().is_relative_to(SOURCE / MIRROR)
            )
        self.assertNotEqual(RUN, SOURCE)
        self.assertFalse(RUN.is_relative_to(SOURCE))

    def test_01_optional_draft_project_autosave_history_roundtrip(self):
        from facility_studio.errors import ValidationError

        cases = [
            ("absent", None, self.MAU, True),
            ("blank", "", self.MAU, True),
            ("zero", "0", self.MAU, True),
            ("known", "12000", self.MAU, True),
            ("active_bad", "bad", self.MAU, False),
            ("active_nan", "nan", self.MAU, False),
            ("inactive_bad", "bad", self.AHU, True),
            ("inactive_negative", "-1", self.AHU, True),
        ]
        for name, value, system, valid in cases:
            with self.subTest(case=name):
                p = self.project(value, system)
                original = copy.deepcopy(p)
                ws = self.ws.new_workspace(p)
                if value is not None:
                    ws["drafts"][KEY] = {
                        "source": "使用者輸入",
                        "note": "DCC test draft",
                        "value": value,
                    }
                path = RUN / "projects" / f"{name}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                self.store.save_project_file(path, ws)
                self.assertEqual(self.ws.read_workspace(path), ws)
                s = self.shell()
                s.restore_snapshot(p)
                self.assertEqual(s.snapshot()["inputs"], p["inputs"])
                s.field_drafts = copy.deepcopy(ws["drafts"])
                s.remember_main_undo()
                s.extra_inputs[KEY] = "9876"
                s.undo_preset()
                self.assertEqual(s.snapshot()["inputs"], p["inputs"])
                self.assertEqual(s.field_drafts, ws["drafts"])
                s.recovery_token = "dcc-" + name
                s.autosave_workspace()
                recovered = self.store.read_recovery(
                    self.store.app_data() / "Recovery" / ("dcc-" + name + ".json")
                )
                self.assertEqual(recovered["main"]["inputs"], p["inputs"])
                self.assertEqual(recovered["drafts"], ws["drafts"])
                self.assertIsNone(getattr(s, "autosave_error", None))
                self.assertIn("schedule_recovery", s.events)
                if valid:
                    r = self.engine.calculate(p)
                    self.assertEqual(r["project"]["inputs"], p["inputs"])
                    if system == self.MAU:
                        self.assertEqual(
                            r["dcc_selection"]["status"],
                            "estimated" if value == "12000" else "pending",
                        )
                    else:
                        self.assertEqual(r["dcc_selection"]["status"], "not_applicable")
                    loaded = self.shell()
                    loaded._load_validated_project(p)
                    self.assertEqual(loaded.snapshot()["inputs"], p["inputs"])
                else:
                    with self.assertRaises(ValidationError) as error:
                        self.engine.calculate(p)
                    self.assertEqual(error.exception.field_name, KEY)
                self.assertEqual(p, original)

    def test_02_inactive_reactivation_and_legacy_load(self):
        from facility_studio.errors import ValidationError

        p = self.project("not ready", self.AHU)
        r = self.engine.calculate(p)
        self.assertNotIn(KEY, r["effective_inputs"])
        p["inputs"]["sys_type"] = self.MAU
        with self.assertRaises(ValidationError) as error:
            self.engine.calculate(p)
        self.assertEqual(error.exception.field_name, KEY)
        s = self.shell(self.project("12000"))
        s._load_validated_project(self.project())
        self.assertNotIn(KEY, s.extra_inputs)
        self.assertNotIn(KEY, s.snapshot()["inputs"])
        self.assertEqual(s.result["dcc_selection"]["status"], "pending")

    def test_03_comparison_and_recovery_store_metadata_without_invention(self):
        p = self.project("12000")
        r = self.engine.calculate(p)
        old = json.loads((RESOURCE / "v15_mau_result.json").read_text(encoding="utf8"))
        self.assertNotIn("dcc_selection", old)
        ws = self.ws.new_workspace(p)
        ws["comparisons"] = {"A": r, "B": old}
        self.assertEqual(
            self.ws.validate_workspace(ws)["comparisons"], ws["comparisons"]
        )
        path = RUN / "comparison.json"
        self.store.save_project_file(path, ws)
        back = self.ws.read_workspace(path)
        self.assertEqual(back["comparisons"]["A"]["dcc_selection"], r["dcc_selection"])
        self.assertNotIn("dcc_selection", back["comparisons"]["B"])
        self.assertIn("舊結果", self.dcc.selection_text(back["comparisons"]["B"]))
        before = copy.deepcopy(back)
        self.store.recovery_save(back, "dcc-comparison")
        self.assertEqual(
            self.store.read_recovery(
                self.store.app_data() / "Recovery/dcc-comparison.json"
            ),
            before,
        )

    def test_04_every_count_consumer_bilingual_and_readonly(self):
        old = json.loads((RESOURCE / "v15_mau_result.json").read_text(encoding="utf8"))
        cases = {
            "pending": self.engine.calculate(self.project()),
            "estimated": self.engine.calculate(self.project("1200")),
            "not_applicable": self.engine.calculate(self.project("bad", self.AHU)),
            "legacy": old,
        }
        for name, r in cases.items():
            with self.subTest(case=name):
                before = copy.deepcopy(r)
                functions = {
                    "text": self.reports.report,
                    "overview": self.reports.executive_summary_text,
                    "overview_html": self.reports.executive_summary_html,
                    "summary_html": self.html.summary_html,
                    "html": self.html.html_report,
                }
                canonical = self.dcc.selection_text(r)
                # Independent semantic checks, not merely helper-to-helper equality.
                if name == "pending":
                    self.assertIn("聯合選型待資料", canonical)
                    self.assertIn(
                        f"DCC 熱量下限 {r['dcc_selection']['thermal_count']} 台",
                        canonical,
                    )
                    self.assertIsNone(r["dcc_selection"]["selected_count"])
                elif name == "estimated":
                    self.assertIn(
                        f"DCC 聯合初估 {r['dcc_selection']['selected_count']} 台",
                        canonical,
                    )
                    self.assertIn("熱量下限", canonical)
                    self.assertIn("風量下限", canonical)
                elif name == "legacy":
                    self.assertIn("舊結果未記錄", canonical)
                for consumer, fn in functions.items():
                    zh = str(
                        fn(r)
                        if consumer in ("overview", "overview_html")
                        else fn(r, language="zh-Hant")
                    )
                    en = str(
                        self.i18n.translate(fn(r), lang="en")
                        if consumer in ("overview", "overview_html")
                        else fn(r, language="en")
                    )
                    (ARTIFACTS / f"{name}-{consumer}-zh.txt").write_text(
                        zh, encoding="utf8"
                    )
                    (ARTIFACTS / f"{name}-{consumer}-en.txt").write_text(
                        en, encoding="utf8"
                    )
                    if name != "not_applicable":
                        self.assertIn(canonical, zh, consumer)
                        self.assertIn(
                            str(self.i18n.translate(canonical, lang="en")), en, consumer
                        )
                    if name in ("pending", "legacy"):
                        self.assertNotRegex(zh, r"DCC (?:需求 )?\d+ 台", consumer)
                    self.assertIsNone(CJK.search(en), consumer)
                    self.assertEqual(numerals(zh), numerals(en), consumer)
                s = self.shell(r["project"])
                s.result = r
                self.MainView.render_results(s)
                ui = s.result_labels[1].options["text"]
                if name != "not_applicable":
                    self.assertIn(canonical, ui)
                else:
                    self.assertNotRegex(ui, r"DCC\s+\d+\s*台")
                if name in ("pending", "legacy"):
                    self.assertNotRegex(ui, r"(?<!原台數記錄 )DCC\s+\d+\s*台")
                    row = next(
                        x
                        for x in self.reports.executive_summary(r)
                        if x["equipment"].startswith("DCC")
                    )
                    self.assertNotEqual(row["tone"], "success")
                    self.assertIn("待", row["status"])
                self.assertEqual(r, before)

    def test_05_stored_selection_not_later_project_or_effective_drafts(self):
        for value in (None, "1200"):
            with self.subTest(value=value):
                r = self.engine.calculate(self.project(value))
                metadata = copy.deepcopy(r["dcc_selection"])
                rendered = self.dcc.selection_text(r, True)
                for scope in ("project", "effective_inputs"):
                    changed = copy.deepcopy(r)
                    inputs = (
                        changed["project"]["inputs"]
                        if scope == "project"
                        else changed["effective_inputs"]
                    )
                    inputs.update(
                        {
                            KEY: "1",
                            "en_dcc_rt": "0.0001",
                            "dcc_airflow_cmh": "999999",
                            "dcc_airflow_mode": "獨立 DCC 循環",
                            "sf": "999",
                        }
                    )
                    self.assertEqual(self.dcc.selection_text(changed, True), rendered)
                    self.assertEqual(changed["dcc_selection"], metadata)
                    self.assertIn(
                        rendered, str(self.reports.report(changed, language="zh-Hant"))
                    )
                    self.assertIn(
                        self.dcc.selection_text(r),
                        str(self.reports.executive_summary_text(changed)),
                    )
                legacy = copy.deepcopy(r)
                legacy.pop("dcc_selection")
                legacy["project"]["inputs"][KEY] = "1"
                legacy["effective_inputs"][KEY] = "1"
                self.assertIn("舊結果", self.dcc.selection_text(legacy))
                self.assertNotIn(
                    "DCC 聯合初估", str(self.reports.report(legacy, language="zh-Hant"))
                )

    def test_06_quality_dispatch_reaches_settings_and_regular_field(self):
        s = self.shell()
        s.result = self.engine.calculate(s.snapshot())
        issues = [x for x in s.result["quality"]["items"] if x.get("field") == KEY]
        self.assertTrue(issues)
        self.assertTrue(any(x["status"] == "待資料" for x in issues))
        # Isolate routing from other unrelated failing engineering checks.
        s.result = {"quality": {"items": issues}}
        s.bad_key = None
        with patch.object(self.settings, "open_settings") as opened:
            s.focus_issue()
            opened.assert_called_once_with(s, focus_key=KEY)
        s.result = None
        s.bad_key = KEY
        with patch.object(self.settings, "open_settings") as opened:
            s.focus_issue()
            opened.assert_called_once_with(s, focus_key=KEY)
        s.result = None
        s.bad_key = "dcc_airflow_cmh"
        s.focus_issue()
        self.assertTrue(s.widgets["dcc_airflow_cmh"].focused)
        self.assertEqual(s.current, self.schema.FIELDS["dcc_airflow_cmh"]["page"])

    def test_07_settings_focus_adopt_blank_undo_and_cancel(self):
        self.assertIn(KEY, self.settings.SETTINGS)
        self.assertEqual(self.settings.SETTINGS[KEY][1], "")
        s = self.shell()
        with self.settings_boundary():
            win = self.settings.open_settings(s, focus_key=KEY)
            self.assertIn(KEY, win.fusion_widgets)
            win.map_event()
            Widget.drain_idle()
            self.assertTrue(win.fusion_widgets[KEY].focused)
            self.assertEqual(win.fusion_notebook.selected, 0)
            self.assertEqual(win.fusion_widgets[KEY].grid_options["row"], 0)
            self.assertEqual(win.fusion_values[KEY].get(), "")
            win.fusion_values[KEY].set("12000")
            win.apply_fusion_settings()
            self.assertTrue(win.destroyed)
            self.assertEqual(s.extra_inputs[KEY], "12000")
            self.assertEqual(s.result["dcc_selection"]["status"], "estimated")
            self.assertNotIn(KEY, s.undo_project["inputs"])
            s.undo_preset()
            self.assertNotIn(KEY, s.snapshot()["inputs"])
            self.assertEqual(s.result["dcc_selection"]["status"], "pending")
            win = self.settings.open_settings(s)
            win.fusion_values[KEY].set("99999")
            win.destroy()
            self.assertNotIn(KEY, s.snapshot()["inputs"])
            win = self.settings.open_settings(s)
            win.fusion_values[KEY].set("")
            win.apply_fusion_settings()
            self.assertEqual(s.result["dcc_selection"]["status"], "pending")
            self.assertFalse(self.dialogs)

    def test_08_settings_invalid_inactive_and_stale_owner_are_transactional(self):
        for kind in (
            "invalid",
            "inactive",
            "project_switch",
            "generation_switch",
            "locked",
        ):
            with self.subTest(kind=kind):
                s = self.shell(
                    self.project("12000", self.AHU if kind == "inactive" else self.MAU)
                )
                before = s.snapshot()
                s.recalculate()
                with self.settings_boundary():
                    win = self.settings.open_settings(s)
                    win.fusion_values[KEY].set(
                        "bad" if kind in ("invalid", "inactive") else "24000"
                    )
                    if kind == "project_switch":
                        s.project_id = "other-owner"
                    if kind == "generation_switch":
                        s._workspace_generation = 17
                    if kind == "locked":
                        s._workspace_main = copy.deepcopy(before)
                    win.apply_fusion_settings()
                    if kind == "inactive":
                        self.assertEqual(
                            win.fusion_widgets[KEY].options["state"], "disabled"
                        )
                        self.assertEqual(s.extra_inputs[KEY], "bad")
                        self.assertTrue(win.destroyed)
                        self.assertEqual(
                            s.result["dcc_selection"]["status"], "not_applicable"
                        )
                    else:
                        self.assertEqual(s.snapshot(), before)
                        self.assertFalse(win.destroyed)
                        self.assertTrue(self.dialogs)
                        self.assertIsNone(s.undo_project)
                        if kind == "invalid":
                            self.assertTrue(win.fusion_widgets[KEY].focused)

    def test_09_cached_count_and_later_system_draft_cannot_override_selection(self):
        r = self.engine.calculate(self.project("1200"))
        text = self.dcc.selection_text(r, True)
        changed = copy.deepcopy(r)
        changed["counts"]["DCC"] = 999999
        changed["project"]["inputs"].update(
            sys_type=self.AHU, **{KEY: "1", "en_dcc_rt": "1"}
        )
        self.assertEqual(self.dcc.selection_text(changed, True), text)
        for fn in (
            self.reports.executive_summary_text,
            self.reports.report,
            self.html.summary_html,
        ):
            rendered = str(fn(changed))
            self.assertIn(text, rendered)
            self.assertNotIn("999999", rendered)
        shell = self.shell(changed["project"])
        shell.result = changed
        self.MainView.render_results(shell)
        self.assertIn(
            self.dcc.selection_text(r), shell.result_labels[1].options["text"]
        )
        self.assertNotIn("999999", shell.result_labels[1].options["text"])

    def test_10_settings_reactivation_follows_current_owner_draft(self):
        s = self.shell(self.project("bad", self.AHU))
        with self.settings_boundary():
            win = self.settings.open_settings(s)
            self.assertEqual(win.fusion_widgets[KEY].options["state"], "disabled")
            s.variables["sys_type"].set(self.MAU)
            win.bindings["<FocusIn>"]()
            self.assertEqual(win.fusion_widgets[KEY].options["state"], "normal")
            self.assertEqual(win.fusion_values[KEY].get(), "bad")
            before = s.snapshot()
            win.apply_fusion_settings()
            self.assertEqual(s.snapshot(), before)
            self.assertFalse(win.destroyed)
            self.assertTrue(self.dialogs)
            self.assertTrue(win.fusion_widgets[KEY].focused)

    def test_11_unknown_keys_still_rejected_without_touching_recovery(self):
        from facility_studio.errors import ValidationError

        good = self.ws.new_workspace(self.project("12000"))
        path = self.store.recovery_save(good, "unknown-key-control")
        before = path.read_bytes()
        bad = copy.deepcopy(good)
        bad["main"]["inputs"]["unrecognized_dcc_field"] = "4"
        with self.assertRaises(ValidationError):
            self.store.recovery_save(bad, "unknown-key-control")
        self.assertEqual(path.read_bytes(), before)

    def test_12_queued_focus_retires_on_destroy_or_owner_change(self):
        for action in (
            "close",
            "project_switch",
            "generation_switch",
            "locked",
            "current",
        ):
            with self.subTest(action=action):
                s = self.shell()
                with self.settings_boundary():
                    win = self.settings.open_settings(s, focus_key=KEY)
                    target = win.fusion_widgets[KEY]
                    if action == "close":
                        win.destroy()
                    elif action == "project_switch":
                        s.project_id = "new-owner"
                    elif action == "generation_switch":
                        s._workspace_generation = 22
                    elif action == "locked":
                        s._workspace_main = s.snapshot()
                    # Child mapping is not the dialog's initial map event.
                    win.map_event(target)
                    self.assertFalse(target.focused)
                    win.map_event()
                    Widget.drain_idle()
                    self.assertEqual(target.focused, action == "current")
                    if action == "current":
                        target.focused = False
                        win.map_event()
                        Widget.drain_idle()
                        self.assertFalse(
                            target.focused, "initial focus must be one-shot"
                        )
                    self.assertFalse(any(w.idle_jobs for w in Widget.instances))

    def test_13_real_tcl_control_after_registration_needs_destroy_cancellation(self):
        import tkinter as tk

        interpreter = tk.Tcl()

        class TimerOwner(tk.Misc):
            def __init__(self):
                self.tk = interpreter.tk
                self._tclCommands = []
                self._w = "."

        interpreter.eval("proc bgerror {msg} {set ::dcc_background_error $msg}")
        owner = TimerOwner()
        fired = []
        owner.after_idle(lambda: fired.append(True))
        owner.destroy()
        interpreter.eval("update")
        self.assertEqual(fired, [])
        error = interpreter.eval("set ::dcc_background_error")
        self.assertIn("invalid command name", error)
        (RUN / "real-tcl-lifecycle-control.json").write_text(
            json.dumps(
                {
                    "tcl_version": interpreter.eval("info patchlevel"),
                    "real_display": False,
                    "control": "uncanceled Misc.after_idle registration then Misc.destroy",
                    "expected_background_error": error,
                    "callback_fired": fired,
                },
                indent=2,
            )
            + "\n"
        )
        interpreter.eval("unset ::dcc_background_error")
        owner = TimerOwner()
        job = owner.after_idle(lambda: fired.append(True))
        owner.after_cancel(job)
        owner.destroy()
        interpreter.eval("update")
        self.assertEqual(interpreter.eval("info exists ::dcc_background_error"), "0")
        self.assertEqual(fired, [])


def configure(source, mirror, runtime):
    global RUN, ARTIFACTS, SOURCE, MIRROR
    if mirror not in ("windows", "macos"):
        raise ValueError("Unknown source mirror")
    SOURCE, MIRROR = Path(source).resolve(), mirror
    RUN = (runtime or Path(tempfile.mkdtemp(prefix="dcc-interactions-"))).resolve()
    RUN.mkdir(parents=True, exist_ok=True)
    ARTIFACTS = RUN / "rendered"
    ARTIFACTS.mkdir(exist_ok=True)
    sys.dont_write_bytecode = True
    os.environ.update(
        FACILITY_STUDIO_DATA=str(RUN / "data"),
        FACILITY_STUDIO_PREFERENCES=str(RUN / "preferences.json"),
        XDG_CACHE_HOME=str(RUN / "cache"),
        MPLCONFIGDIR=str(RUN / "mpl"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    sys.path.insert(0, str(SOURCE / mirror))


def main():
    global _REQUESTED_CONFIGURATION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE.parent)
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runtime-dir", type=Path)
    args = parser.parse_args()
    _REQUESTED_CONFIGURATION = (args.source, args.platform, args.runtime_dir)
    source = args.source.resolve()

    class Recorded(unittest.TextTestResult):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.outcomes = []

        def addSuccess(self, test):
            super().addSuccess(test)
            self.outcomes.append({"test": test.id(), "passed": True})

        def addFailure(self, test, error):
            super().addFailure(test, error)
            self.outcomes.append(
                {
                    "test": test.id(),
                    "passed": False,
                    "detail": self._exc_info_to_string(error, test),
                }
            )

        def addError(self, test, error):
            super().addError(test, error)
            self.outcomes.append(
                {
                    "test": test.id(),
                    "passed": False,
                    "detail": self._exc_info_to_string(error, test),
                }
            )

        def addSubTest(self, test, subtest, error):
            super().addSubTest(test, subtest, error)
            self.outcomes.append(
                {
                    "test": str(subtest),
                    "passed": error is None,
                    **(
                        {"detail": self._exc_info_to_string(error, test)}
                        if error
                        else {}
                    ),
                }
            )

    runner = unittest.TextTestRunner(verbosity=2, resultclass=Recorded)
    result = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(Interactions))
    record = {
        "kind": "independent-dcc-interaction-boundaries",
        "source_platform": args.platform,
        "host_os": platform.system(),
        "python": platform.python_version(),
        "source": str(source),
        "passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "native_binary_acceptance": False,
        "real_gui": False,
        "widget_boundary": "recording stand-ins; real production callbacks",
        "outcomes": result.outcomes,
        "resources": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in RESOURCE.glob("*")
            if p.is_file()
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )
    print(
        json.dumps(
            {k: v for k, v in record.items() if k not in ("outcomes", "resources")},
            ensure_ascii=False,
        )
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
