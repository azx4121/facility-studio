from .electrical_disclosures import export_result_copy
import copy
from .industrial_theme import Theme
from .platform_support import uses_ttk_navigation
from .version import BUILD_VERSION
from .tools_view import QuickToolsWindow
from .workspace_view import WorkspaceWindow
from .project_store import recovery_save
from .optional_inputs import check_input_keys, split_inputs
from .html_report import summary_html
import uuid
from .project_store import save_project_file
from .errors import InputError
from pathlib import Path
from .localized_tk import filedialog
import json
from .localized_tk import messagebox
import os
from .localized_tk import tk
from .localized_tk import ttk
from .ahu_desktop import AHUWindow
from .data import CLEANROOM_DB
from .engine import calculate, pv_to_torr, read_project, validate_project
from .main_view import HAS_PLOT, MainView, ScrollPage
from .flow_toolbar import FlowToolbar
from .reports import report
from .schema import (
    DEFAULTS,
    FIELDS,
    PAGES,
    PD_KEYS,
    QUALITY_PRESETS,
    REFERENCE_KEYS,
    SCHEMA_VERSION,
    VERSION,
    default_project,
)
from .services import UNIT_VALUES, converted_units, independent_domains
from .localized_tk import LanguagePicker
from . import i18n
from .ui_common import app_icon, quality_style, quality_text
from .tutorial_help import open_tutorial
from .utils import G, atomic_text, number, project_hash
from .session_controller import SessionController
from . import workspace_transition as transition
from .field_state import main_inactive, error_text
from .project_store import provenance_record


class DesktopApp(SessionController, MainView):

    def remember_main_undo(self):
        transition.require_editable(self)
        self.undo_project = self.snapshot()
        self.undo_aux = (
            copy.deepcopy(self.transfer_receipts),
            copy.deepcopy(self.field_drafts),
            copy.deepcopy(self.demand_ledger),
        )

    def normalize_auto_values(self):
        if getattr(self, "_workspace_transition", False) or getattr(self, "_workspace_main", None) is not None:
            return
        if self.variables["upw_quality_mode"].get() != "自動參考值":
            return
        value = str(QUALITY_PRESETS[self.variables["upw_type"].get()])
        old = self.variables["upw_res"].get()
        source = self.provenance["upw_res"]
        if source["source"] != "系統預設" or old != value:
            if source["source"] != "系統預設":
                self.field_drafts["upw_res"] = {**source, "value": old}
            self.provenance["upw_res"] = provenance_record(
                "系統預設", "依水型帶入參考值，非原廠保證值", value
            )
            suspended = self.suspended
            self.suspended = True
            try:
                self.variables["upw_res"].set(value)
            finally:
                self.suspended = suspended

    def restore_references(self):
        keys = [k for k in REFERENCE_KEYS if FIELDS[k]["page"] == self.current]
        if not keys:
            return
        self.remember_main_undo()
        self.suspended = True
        try:
            for k in keys:
                self.variables[k].set(DEFAULTS[k])
                self.provenance[k] = {"source": "系統預設", "note": "套用本頁初估係數"}
        finally:
            self.suspended = False
        self.changed()
        self.recalculate()
        self.update_visibility()

    def undo_preset(self):
        if not self.undo_project or not transition.editable(self):
            return
        # Do not consume the only undo point until all restore steps succeed.
        self.restore_snapshot(self.undo_project, auxiliary=getattr(self, "undo_aux", None),
                              refresh_demand=True)
        self.undo_project = None
        self.undo_aux = None

    def restore_snapshot(self, project, *, auxiliary=None, refresh_demand=False, rollback_on_error=True):
        """Restore bounded raw strings, then expose invalid fields for correction."""
        transition.require_editable(self)
        from .engine import migrate_project
        from .project_store import validate_provenance

        p = migrate_project(copy.deepcopy(project))
        if (
            set(p) != {"schema_version", "inputs", "pressure_drop", "provenance"}
            or p["schema_version"] != SCHEMA_VERSION
        ):
            raise ValueError("不支援的復原格式")
        check_input_keys(p["inputs"], "復原欄位不完整")
        if set(p["pressure_drop"]) != set(self.pd):
            raise ValueError("復原欄位不完整")
        validate_provenance(p["provenance"], FIELDS)
        for k, v in p["inputs"].items():
            if not isinstance(v, str) or len(v) > 1000:
                raise ValueError("復原內容格式不合法")
        for k, row in p["pressure_drop"].items():
            if set(row) != set(self.pd[k]) or any(
                not isinstance(v, str) or len(v) > 1000 for v in row.values()
            ):
                raise ValueError("壓損復原內容格式不合法")
        form, extra = split_inputs(p["inputs"], self.variables)
        # Preparing/copying the target must not mutate any live state.
        target_aux = copy.deepcopy(auxiliary)
        if target_aux is not None:
            receipts, drafts, ledger = target_aux
        if getattr(self, "_restoring_snapshot", False):
            raise RuntimeError("復原作業仍在進行中")
        before = self.snapshot()  # May contain an unbounded live draft. Never validate rollback.
        state_keys = (
            "provenance", "extra_inputs", "transfer_receipts", "field_drafts", "demand_ledger",
            "unit_previous", "pv_unit_last", "pd_last_units", "latent_mode_previous", "upw_mode_previous",
        )
        cache_keys = ("result", "last_good_result", "partial_hvac", "domain_results",
                      "bad_key", "bad_pd", "last_error", "_boundary_cache", "_plot_key", "after_id")
        missing = object()
        state = {k: copy.deepcopy(getattr(self, k)) if hasattr(self, k) else missing for k in state_keys}
        caches = {k: getattr(self, k, missing) for k in cache_keys}
        suspended = self.suspended
        self._restoring_snapshot = True
        self.suspended = True
        try:
            for k, v in form.items():
                self.variables[k].set(v)
            for k, row in p["pressure_drop"].items():
                for f, v in row.items():
                    self.pd[k][f].set(v)
            self.provenance = p["provenance"]
            self.extra_inputs = extra
            if target_aux is not None:
                self.transfer_receipts, self.field_drafts, self.demand_ledger = receipts, drafts, ledger
            self.unit_previous = {k: self.variables[k].get() for k in self.unit_previous}
            self.pv_unit_last = self.variables["pv_pressure_unit"].get()
            self.pd_last_units = {k: row["unit"].get() for k, row in self.pd.items()}
            self.latent_mode_previous = self.variables["latent_mode"].get()
            self.upw_mode_previous = self.variables["upw_quality_mode"].get()
            self.normalize_auto_values()
            self.interlocks()
            # Keep the pre-existing timer alive until commit; recalculation must
            # not cancel it if a later render/notification fails and we roll back.
            self.after_id = None
            self.recalculate()
            self.update_visibility()
            self.notify_children()
            if refresh_demand:
                self.refresh_demand_views()
            previous_job = caches["after_id"]
            if previous_job is not missing and previous_job:
                self.root.after_cancel(previous_job)
        except Exception:
            if not rollback_on_error:
                # apply_workspace owns a wider, historically non-atomic switch.
                # Do not create old-main/new-workspace hybrids on its late errors.
                self.restore_recalculation_job(caches["after_id"] if caches["after_id"] is not missing else None)
                raise
            # Restore raw state directly, not by recursively calling this method.
            # A destroyed Tcl interpreter cannot be recovered, but try every field
            # and always restore Python-owned metadata and the suspension flag.
            rollback_errors = []
            for k, var in self.variables.items():
                try:
                    var.set(before["inputs"][k])
                except Exception as exc:
                    rollback_errors.append(exc)
            for k, row in self.pd.items():
                for f, var in row.items():
                    try:
                        var.set(before["pressure_drop"][k][f])
                    except Exception as exc:
                        rollback_errors.append(exc)
            for k, value in {**state, **caches}.items():
                if value is missing:
                    self.__dict__.pop(k, None)
                else:
                    setattr(self, k, value)
            self.restore_recalculation_job(caches["after_id"] if caches["after_id"] is not missing else None)
            if rollback_errors:
                raise RuntimeError("復原失敗且部分畫面欄位無法還原；復原資料仍保留") from rollback_errors[0]
            raise
        finally:
            self.suspended = suspended
            del self._restoring_snapshot

    def restore_recalculation_job(self, job):
        """Keep a live job reference; a nested event loop may have consumed it."""
        self.after_id = job
        if job:
            try:
                self.root.tk.call("after", "info", job)
            except tk.TclError:
                self.after_id = self.schedule_recalculation()

    def snapshot(self):
        if getattr(self, "_workspace_main", None) is not None:
            return copy.deepcopy(self._workspace_main)
        return self.widget_snapshot()

    def widget_snapshot(self):
        inputs = {k: v.get() for k, v in self.variables.items()}
        inputs.update(getattr(self, "extra_inputs", {}))
        return {
            "schema_version": SCHEMA_VERSION,
            "inputs": inputs,
            "pressure_drop": {
                k: {f: v.get() for f, v in c.items()} for k, c in self.pd.items()
            },
            "provenance": copy.deepcopy(self.provenance),
        }

    def pd_changed(self, sys_name, key):
        if transition.reject_main_edit(self, key, sys_name):
            return
        if self.suspended or not transition.editable(self):
            return
        row = self.pd[sys_name]
        if key == "unit":
            old = self.pd_last_units[sys_name]
            new = row[key].get()
            scale = {"Pa": 1.0, "kPa": 1000.0, "mmAq": G, "mH2O": 1000 * G}
            try:
                values = {
                    k: number(row[k].get(), k, 0, 100000000.0) * scale[old] / scale[new]
                    for k in ["equipment_drop", "rate"]
                }
                self.suspended = True
                for k, v in values.items():
                    row[k].set(format(v, ".15g"))
                self.pd_last_units[sys_name] = new
            except (ValueError, KeyError):
                self.suspended = True
                row["unit"].set(old)
            finally:
                self.suspended = False
        self.changed()

    def select_pd(self, event=None):
        sel = self.grid.selection()
        if not sel:
            return
        self.selected_pd = sel[0]
        self.pd_choice.set(self.selected_pd)
        self.pd_box.config(
            text=self.selected_pd
            + " 最不利路徑（流量："
            + ("LPM" if self.selected_pd in PD_KEYS[:5] else "CMH")
            + "）"
        )
        for k, w in self.pd_widgets.items():
            w.configure(textvariable=self.pd[self.selected_pd][k])
        self.interlocks()

    def focus_issue(self):
        from .fusion_settings import SETTINGS, open_settings
        if self.bad_pd:
            self.show_page(7)
            self.grid.selection_set(self.bad_pd)
            self.select_pd()
            self.pages[7].reveal(self.pd_box)
            return
        if getattr(self, "result", None):
            self.bad_key = next((item["field"] for state in ("未達", "待資料")
                                 for item in self.result["quality"]["items"]
                                 if item["status"] == state and (item["field"] in self.widgets or item["field"] in SETTINGS)), None)
        if self.bad_key in SETTINGS:
            open_settings(self, focus_key=self.bad_key)
            return
        if self.bad_key:
            self.view_mode.set("進階模式")
            self.show_page(FIELDS[self.bad_key]["page"])
            w = self.widgets[self.bad_key]
            self.pages[self.current].reveal(w)
            w.focus_set()

    def preset(self, z):
        self.remember_main_undo()
        vals = CLEANROOM_DB[self.variables["c_" + z.lower()].get()]
        self.suspended = True
        try:
            for k, v in [
                ("en_ach_" + z, vals["ach"]),
                ("en_p_" + z, vals["pressure"]),
                ("mode_" + z, "ACH"),
            ]:
                self.variables[k].set(str(v))
                self.provenance[k] = {
                    "source": "系統預設",
                    "note": "依潔淨等級套用初估係數，仍需確認設計條件",
                }
        finally:
            self.suspended = False
        self.changed()
        self.recalculate()

    def confirm_discard(self):
        return self.confirm_session_discard()

    def new(self):
        return self.create_workspace()

    def load(self):
        return self.open_workspace()

    def save(self):
        return self.save_workspace()

    def ensure_result(self):
        if not transition.editable(self):
            return False
        self.refresh_receipts()
        if not self.result or self.result["hash"] != project_hash(self.snapshot()):
            self.recalculate(True)
        return self.result is not None and self.result["hash"] == project_hash(
            self.snapshot()
        )

    def export(self):
        if not self.ensure_result():
            return
        result = self.result
        snapshot_hash = project_hash(self.snapshot())
        generation = transition.token(self)
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="Design_Report.txt",
            filetypes=[("文字報告", "*.txt")],
        )
        if path:
            if not transition.editable(self) or transition.token(self) != generation or self.result is not result or snapshot_hash != project_hash(self.snapshot()):
                messagebox.showwarning(
                    "匯出已停止", "匯出期間條件已變更，請重新計算後再匯出。", parent=self.root)
                return False
            try:
                atomic_text(path, report(self.result))
                self.status.config(text="設計報告已匯出" + "\n" + quality_text(self.result["quality"]), style=quality_style(self.result["quality"]))
            except Exception as e:
                messagebox.showerror("匯出失敗", str(e), parent=self.root)

    def export_audit(self):
        if not self.ensure_result():
            return
        result = self.result
        snapshot_hash = project_hash(self.snapshot())
        generation = transition.token(self)
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="Calculation_Audit.json"
        )
        if path:
            if not transition.editable(self) or transition.token(self) != generation or self.result is not result or snapshot_hash != project_hash(self.snapshot()):
                messagebox.showwarning(
                    "匯出已停止", "匯出期間條件已變更，請重新計算後再匯出。", parent=self.root)
                return False
            try:
                atomic_text(
                    path,
                    json.dumps(
                        export_result_copy(self.result), ensure_ascii=False, indent=2, allow_nan=False
                    ),
                )
            except Exception as e:
                messagebox.showerror("另存失敗", str(e), parent=self.root)

    def copy_report(self):
        if not transition.editable(self):
            return
        if self.ensure_result():
            self.root.clipboard_clear()
            self.root.clipboard_append(report(self.result))
            self.status.config(text="報告已複製" + "\n" + quality_text(self.result["quality"]), style=quality_style(self.result["quality"]))

    def save_plot(self):
        if not transition.editable(self):
            return
        if not HAS_PLOT:
            return messagebox.showinfo("圖形功能", "請先安裝 matplotlib。")
        if not self.ensure_result():
            return
        result = self.result
        snapshot_hash = project_hash(self.snapshot())
        generation = transition.token(self)
        path = filedialog.asksaveasfilename(
            defaultextension=".png", initialfile="Air_Process.png"
        )
        if path:
            if not transition.editable(self) or transition.token(self) != generation or self.result is not result or snapshot_hash != project_hash(self.snapshot()):
                messagebox.showwarning(
                    "匯出已停止", "匯出期間條件已變更，請重新計算後再匯出。", parent=self.root)
                return False
            try:
                self.draw(force=True)
                self.fig.savefig(path, dpi=180)
            except Exception as e:
                messagebox.showerror("圖形匯出失敗", str(e), parent=self.root)

    def callback_error(self, exc_type, exc_value, tb):
        if isinstance(exc_value, transition.WorkspacePresentationError):
            # Do not call the failed renderer again and hide the commit warning.
            messagebox.showerror("操作未完成", str(exc_value), parent=self.root)
            return
        import traceback

        self.result = None
        self.export_button.state(["disabled"])
        self.set_report("操作未完成，請修正條件後重新計算。")
        self.status.config(text="操作未完成；請查看錯誤訊息。", style="Error.TLabel")
        details = "".join(traceback.format_exception(exc_type, exc_value, tb))
        try:
            from .project_store import app_data

            logdir = app_data()
            logdir.mkdir(parents=True, exist_ok=True)
            atomic_text(logdir / "error.log", details)
        except OSError:
            pass
        messagebox.showerror("操作未完成", str(exc_value), parent=self.root)

    def winfo_exists(self):
        """Expose the owned window lifetime to the language subscriber registry."""
        return self.root.winfo_exists()

    def refresh_language(self):
        if self.root.winfo_exists() and self.result:
            self.set_report(report(self.result))
            self.draw()

    def _build_window(self, root):
        self.root = root
        root.title("廠務工程工作台 V" + BUILD_VERSION)
        self.project = default_project()
        self.provenance = self.project["provenance"]
        self.extra_inputs = {}
        self.variables = {
            k: tk.StringVar(value=v) for k, v in self.project["inputs"].items()
        }
        self.pd = {
            k: {f: tk.StringVar(value=v) for f, v in c.items()}
            for k, c in self.project["pressure_drop"].items()
        }
        self.result = None
        self.current = 0
        self.after_id = None
        self.suspended = True
        self.path = None
        self.saved_hash = project_hash(self.project)
        self.widgets = {}
        self.pages = {}
        self.nav = []
        self.result_labels = {}
        self.bad_key = None
        self.bad_pd = None
        self.pd_widgets = {}
        self.view_mode = tk.StringVar(value="基本模式")
        self.task_scope = tk.StringVar(value="空調與熱負荷")
        self.form_rows = {}
        self.form_boxes = []
        self.pd_rows = {}
        self.undo_project = None
        self.pv_unit_last = self.variables["pv_pressure_unit"].get()
        self.latent_text = tk.StringVar(value="等待計算")
        self.configure_style()
        from .window_geometry import initialize_main_window
        initialize_main_window(root, Theme.scale)
        # Attach the native menu before any layout flush can map this root.
        # First-Map placement must measure the final non-client frame.
        from .sandbox_ui import install_menus
        install_menus(root)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)
        side = tk.Frame(root, bg=Theme.NAV, width=184)
        side.grid(row=0, column=0, rowspan=3, sticky="ns")
        side.pack_propagate(False)
        tk.Label(
            side,
            text="FACILITY\nSTUDIO",
            bg=Theme.NAV,
            fg=Theme.TEXT,
            font=(self.ui_font, 15, "bold"),
            justify="left",
        ).pack(anchor="w", padx=18, pady=(25, 6))
        self.side_subtitle = tk.Label(
            side,
            text="廠務工程工作台  V" + VERSION,
            bg=Theme.NAV,
            fg=Theme.MUTED,
            font=(self.ui_font, 10),
            justify="left",
            wraplength=148,  # sidebar 184 px less its 18 px side margins: long translations wrap, never clip
        )
        self.side_subtitle.pack(anchor="w", padx=18, pady=(0, 24))
        for j, name in enumerate(PAGES):
            if uses_ttk_navigation():
                b = ttk.Button(
                    side,
                    text=f"{j + 1:02d}   {name}",
                    command=lambda n=j: self.show_page(n),
                    style="Workbench.Nav.TButton",
                    cursor="hand2",
                )
            else:
                b = tk.Button(
                    side,
                    text=f"{j + 1:02d}   {name}",
                    command=lambda n=j: self.show_page(n),
                    bg=Theme.NAV,
                    fg=Theme.TEXT,
                    activebackground="#E0E6EF",
                    activeforeground=Theme.TEXT,
                    relief="flat",
                    anchor="w",
                    padx=14,
                    pady=7,
                    font=(self.ui_font, 10),
                    cursor="hand2",
                    justify="left",
                    wraplength=140,  # sidebar 184 px less button margins and padding
                )
            b.pack(fill="x", padx=8, pady=2)
            self.nav.append(b)
        tk.Label(
            side,
            text="設計：\nANDY HUANG ©",
            bg=Theme.NAV,
            fg=Theme.MUTED,
            justify="left",
            font=(self.ui_font, 9),
        ).pack(side="bottom", anchor="w", padx=18, pady=18)
        head = ttk.Frame(root, padding=(20, 14))
        head.grid(row=0, column=1, sticky="ew")
        head.columnconfigure(0, weight=1)
        self.title = ttk.Label(head, text=PAGES[0], style="Title.TLabel")
        self.title.grid(row=0, column=0, sticky="w")
        self.subtitle = ttk.Label(
            head, text="共同條件 → 工程檢核 → 設計摘要", style="Muted.TLabel"
        )
        self.subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.document_status = tk.StringVar()
        self.receipt_status = tk.StringVar()
        self.document_status_label = ttk.Label(
            head, textvariable=self.document_status, wraplength=600, style="Muted.TLabel"
        )
        self.document_status_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.receipt_status_label = ttk.Label(
            head, textvariable=self.receipt_status, wraplength=600, style="Muted.TLabel"
        )
        self.receipt_status_label.grid(row=7, column=0, columnspan=2, sticky="w")
        language_bar = ttk.Frame(head)
        language_bar.grid(row=0, column=1, sticky="e", pady=(6, 0))
        ttk.Label(language_bar, text="介面語言").pack(side="left", padx=(0, 6))
        self.language_picker = LanguagePicker(language_bar)
        self.language_picker.pack(side="right")
        # Keep review/settings in their own wrapping row. Direct grid buttons
        # here would be covered by a later toolbar spanning the same two cells.
        reviews = FlowToolbar(head)
        reviews.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        from .feed_review_preview import open_preview
        ttk.Button(reviews, text="設計檢核中心", command=lambda: open_preview(self.root)).pack(
            side="left", padx=(0, 8)
        )
        from .fusion_settings import open_settings
        ttk.Button(reviews, text="工程模型設定｜五庫融合", command=lambda: open_settings(self)).pack(
            side="left", padx=(0, 8)
        )
        header_widths = [None]

        def wrap_header(event):
            if event.widget is not head:
                return
            width = max(120, event.width - 40)
            widths = (width, max(120, width - language_bar.winfo_reqwidth() - 12))
            if widths == header_widths[0]:
                return
            header_widths[0] = widths
            self.title.configure(wraplength=widths[1])
            for label in (self.subtitle, self.document_status_label, self.receipt_status_label):
                label.configure(wraplength=width)

        head.bind("<Configure>", wrap_header, add="+")
        bar = FlowToolbar(head)
        bar.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        for txt, cmd in [
            ("新專案", self.new),
            ("開啟", self.load),
            ("儲存整案", self.save),
            ("另存新檔", self.save_workspace_as),
        ]:
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=3)
        modebar = FlowToolbar(head)
        modebar.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Combobox(
            modebar,
            textvariable=self.view_mode,
            values=["基本模式", "進階模式"],
            width=16,
            state="readonly",
        ).pack(side="left")
        self.ref_button = ttk.Button(
            modebar, text="套用本頁初估係數", command=self.restore_references
        )
        self.ref_button.pack(side="left", padx=8)
        self.undo_button = ttk.Button(
            modebar, text="復原帶入", command=self.undo_preset
        )
        self.undo_button.pack(side="left")
        # Reserve room for both translated choices; FlowToolbar wraps locally
        # on narrow displays without changing the main-window geometry.
        scope = ttk.Combobox(modebar, textvariable=self.task_scope, values=("空調與熱負荷", "全部工程分頁"), state="readonly", width=26)
        scope.pack(side="left", padx=8)
        scope.bind("<<ComboboxSelected>>", lambda event: self.update_visibility())
        ttk.Button(modebar, text="空調箱管理", command=self.open_ahu_manager).pack(
            side="left", padx=8
        )
        utilities = FlowToolbar(head)
        utilities.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.pv_button = self.nav[3]
        self.pv_button.configure(text="04   PV 真空／特氣", command=self.show_pv)
        for label, command in [
            ("返回簡易工具", self.show_simple_tools),
            ("來源／比較／復原", lambda: WorkspaceWindow(root, self)),
            ("匯出可列印摘要", self.export_html),
        ]:
            ttk.Button(utilities, text=label, command=command).pack(
                side="left", padx=(0, 8)
            )
        self.tutorial_button = ttk.Button(
            utilities, text="新手教學", command=lambda: open_tutorial(root, "first-case")
        )
        self.tutorial_button.pack(side="left", padx=(0, 8))
        actions = FlowToolbar(head)
        actions.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        for label, command in [("複製為新方案", self.duplicate_workspace), ("設備表匯入", self.open_equipment), ("需求彙整", self.open_demand_ledger), ("容量／擴建規劃", self.open_capacity_planning), ("開啟練習新案", self.open_practice)]:
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 8))
        self.action_toolbars = (reviews, bar, modebar, utilities, actions)
        self.host = ttk.Frame(root)
        self.host.grid(row=1, column=1, sticky="nsew")
        self.host.columnconfigure(0, weight=1)
        self.host.rowconfigure(0, weight=1)
        for j in range(8):
            page = ScrollPage(self.host)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[j] = page
        self.build_forms()
        self.build_overview()
        self.build_pd()
        self.build_report()
        self.pack_order = {j: list(self.pages[j].body.pack_slaves()) for j in range(8)}
        foot = ttk.Frame(root, padding=(14, 9))
        foot.grid(row=2, column=1, sticky="ew")
        foot.columnconfigure(0, weight=1)
        self.status = ttk.Label(
            foot, text="啟動檢核中…", wraplength=470, style="Muted.TLabel"
        )
        self.status.grid(row=0, column=0, sticky="w")
        def wrap_status(event=None):
            # The status text gets what the three buttons leave over, in any language.
            buttons = sum(w.winfo_reqwidth() + 8 for w in (locate, self.calc_button, self.export_button))
            width = max(120, foot.winfo_width() - buttons - 24)
            if str(self.status.cget("wraplength")) != str(width):
                self.status.configure(wraplength=width)

        foot.bind("<Configure>", wrap_status)

        locate = ttk.Button(foot, text="定位問題", command=self.focus_issue)
        locate.grid(row=0, column=1, padx=4)
        self.calc_button = ttk.Button(
            foot,
            text="重新計算",
            command=lambda: self.recalculate(True),
            style="Accent.TButton",
        )
        self.calc_button.grid(row=0, column=2, padx=4)
        self.export_button = ttk.Button(foot, text="匯出設計報告", command=self.export)
        self.export_button.grid(row=0, column=3, padx=4)
        for button in (locate, self.calc_button, self.export_button):
            button.bind("<Configure>", wrap_status, add="+")
        for key, var in self.variables.items():
            var.trace_add("write", lambda *a, k=key: self.changed(k))
        self.pd_last_units = {k: row["unit"].get() for k, row in self.pd.items()}
        for sys_name, row in self.pd.items():
            for key, var in row.items():
                var.trace_add(
                    "write", lambda *a, sn=sys_name, k=key: self.pd_changed(sn, k)
                )
        from .platform_support import wheel_sequences
        for sequence in wheel_sequences(root.tk):
            root.bind_all(sequence, self.wheel, add="+")
        root.report_callback_exception = self.callback_error
        root.bind("<Control-s>", lambda e: self.save())
        root.bind("<Control-o>", lambda e: self.load())
        root.bind("<F5>", lambda e: self.recalculate(True))
        from .platform_support import bind_mac_shortcuts

        bind_mac_shortcuts(
            root,
            save=self.save,
            open=self.load,
            calculate=lambda: self.recalculate(True),
        )
        root.protocol("WM_DELETE_WINDOW", self.close)
        from .platform_support import install_mac_quit

        install_mac_quit(root, self.close)
        self.view_mode.trace_add("write", lambda *a: self.update_visibility())
        self.suspended = False
        self.show_page(0)
        self.interlocks()
        self.recalculate()

    def __init__(self, root):
        self.children = []
        self.project_id = uuid.uuid4().hex
        self.ahu_documents = {}
        self.comparisons = {}
        self.transfer_receipts = []
        self.field_drafts = {}
        from .contributions import empty_ledger
        self.demand_ledger = empty_ledger()
        self.saved_workspace_hash = ""
        self.unit_previous = {}
        self.partial_hvac = None
        from .localized_tk import attach_window

        attach_window(root)
        self._build_window(root)
        root.title("廠務工程工作台 V" + BUILD_VERSION)
        app_icon(root)
        i18n.subscribe(self)
        self.unit_previous = {
            k: self.variables[k].get() for k in list(UNIT_VALUES) + ["u_unit"]
        }
        side = self.nav[0].master
        if hasattr(root, "_app_icon"):
            self.brand_icon = root._app_icon.subsample(4, 4)
            label = tk.Label(side, image=self.brand_icon, bg=Theme.NAV)
            label.pack(before=side.pack_slaves()[0], anchor="w", padx=18, pady=(14, 0))
        self._side_order = list(side.pack_slaves())
        self._side_pack = {w: w.pack_info() for w in self._side_order}
        self._compact = None
        root.bind("<Configure>", self.sidebar_layout, add="+")
        root.bind("<Configure>", self.fit_min_height, add="+")
        self.sidebar_layout()
        self.fit_min_height()
        self.recovery_token = uuid.uuid4().hex
        self.schedule_recovery()
        self.latent_mode_previous = self.variables["latent_mode"].get()
        self.upw_mode_previous = self.variables["upw_quality_mode"].get()
        self.saved_workspace_hash = project_hash(self.session_snapshot())
        self.refresh_session_status()

    def _invalidate_and_schedule(self, key=None):
        if self.suspended:
            return
        if key == "upw_quality_mode" and self.upw_mode_previous == "自訂規格":
            self.field_drafts["upw_res"] = dict(
                self.provenance["upw_res"], value=self.variables["upw_res"].get()
            )
        if (
            key == "upw_quality_mode"
            and self.variables[key].get() == "自訂規格"
            and "upw_res" in self.field_drafts
        ):
            self.suspended = True
            self.variables["upw_res"].set(self.field_drafts["upw_res"]["value"])
            self.provenance["upw_res"] = copy.deepcopy(self.field_drafts["upw_res"])
            self.suspended = False
        if (
            key in ("upw_type", "upw_quality_mode")
            and self.variables["upw_quality_mode"].get() == "自動參考值"
        ):
            self.suspended = True
            self.variables["upw_res"].set(
                QUALITY_PRESETS[self.variables["upw_type"].get()]
            )
            self.provenance["upw_res"] = provenance_record(
                "系統預設",
                self.variables["upw_type"].get() + " 的 25°C 初估參考；非原廠保證",
                self.variables["upw_res"].get(),
            )
            self.suspended = False
        self.upw_mode_previous = self.variables["upw_quality_mode"].get()
        self.latent_text.set("輸入更新中，等待產濕檢核…")
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.last_good_result = self.result or getattr(self, "last_good_result", None)
        self.result = None
        self.status.config(text="輸入已變更，等待檢核…", style="Muted.TLabel")
        self.export_button.state(["disabled"])
        if self.last_good_result:
            self.summary.config(text="上次有效結果｜輸入更新中，尚不可匯出", style="Warn.TLabel")
            self.set_report("【上次有效結果／待重算，不能作為目前輸入結果】\n\n" + report(self.last_good_result))
            if HAS_PLOT:
                old = getattr(self, "stale_plot_label", None)
                if old is not None and old in self.ax.texts:
                    old.remove()
                self.stale_plot_label = self.ax.text(.5, .5, "上次有效結果｜待重算", transform=self.ax.transAxes, ha="center", va="center", fontsize=15, color="#b45309", bbox=dict(facecolor="white", alpha=.9))
                self.queue_plot()
            self.interlocks()
            self.after_id = self.schedule_recalculation()
            return
        self.set_report("輸入已變更；檢核完成後更新報告。")
        self.summary.config(text="輸入更新中…")
        self.psy_label.config(text="")
        self.topology.config(text="")
        for label in self.result_labels.values():
            label.config(text="輸入已變更，待重新計算")
        for k in PD_KEYS:
            self.grid.item(k, values=("—", "—", "—", "—"))
        if HAS_PLOT:
            self._plot_key = None
            self.ax.clear()
            self.ax.text(
                0.5,
                0.5,
                "輸入已變更，等待檢核",
                ha="center",
                transform=self.ax.transAxes,
            )
            self.queue_plot()
        self.interlocks()
        self.after_id = self.schedule_recalculation()

    def changed(self, key=None):
        if transition.reject_main_edit(self, key):
            return
        if self.suspended or not transition.editable(self):
            return
        if key == "pv_pressure_unit" or key in self.unit_previous:
            old = self.pv_unit_last if key == "pv_pressure_unit" else self.unit_previous[key]
            new = self.variables[key].get()
            if new == old:
                return
            try:
                if key == "pv_pressure_unit":
                    torr = pv_to_torr(self.variables["pv_torr"].get(), old)
                    factor = {
                        "Torr(abs)": 1.0,
                        "kPa(abs)": 101.325 / 760,
                        "mbar(abs)": 1013.25 / 760,
                    }[new]
                    updates = {"pv_torr": torr * factor}
                else:
                    updates = converted_units(self.snapshot()["inputs"], key, old, new)
            except (ValueError, KeyError):
                # Reject the selection before committing any value or provenance.
                self.suspended = True
                try:
                    self.variables[key].set(old)
                finally:
                    self.suspended = False
                return
            self.suspended = True
            try:
                for k, v in updates.items():
                    self.variables[k].set(format(v, ".15g"))
                    self.provenance[k] = provenance_record(
                        "單位等值換算", old + " → " + new, self.variables[k].get()
                    )
                if key == "pv_pressure_unit":
                    self.pv_unit_last = new
                else:
                    self.unit_previous[key] = new
            finally:
                self.suspended = False
        if not self.sync_latent_input(key):
            return
        self.partial_hvac = None
        if key in self.variables:
            self.provenance[key] = provenance_record(
                "使用者輸入", "介面修改", self.variables[key].get()
            )
        if hasattr(self, "quality_label"):
            self.quality_label.config(text="等待目前條件檢核")
        self._invalidate_and_schedule(key)
        self.notify_children()

    def sync_latent_input(self, key):
        """Return False for a rejected/no-op mode change before invalidation.

        Inactive-mode entry exposes the retained draft without converting it.
        Numeric-mode switches preserve an unchanged conversion's original input
        and evidence; an actual value edit remains the authoritative source.
        """
        modes = {
            "已知潛熱 kW": ("process_latent_kw", 3600 / 2501),
            "已知產濕量 kg/h": ("process_moisture_kg_h", 2501 / 3600),
        }
        current = self.variables["latent_mode"].get()
        previous = getattr(self, "latent_mode_previous", current)

        def restore_mode():
            suspended = self.suspended
            self.suspended = True
            try:
                self.variables["latent_mode"].set(previous)
            finally:
                self.suspended = suspended

        if key == "latent_mode":
            if current == previous:
                return False
            if current not in FIELDS["latent_mode"]["options"]:
                restore_mode()
                return False
        # NONE/UNKNOWN have no numeric source. Entering a numeric mode must
        # expose its draft for correction, not validate it or consume old data.
        source_mode = previous if key == "latent_mode" else current
        if current in modes and source_mode in modes and key in ("latent_mode", modes[source_mode][0]):
            source, factor = modes[source_mode]
            other = "process_moisture_kg_h" if source == "process_latent_kw" else "process_latent_kw"
            try:
                value = number(self.variables[source].get(), source, 0) * factor
                # A finite source can overflow during conversion. Never commit inf.
                rendered = format(number(value, other, 0), ".15g")
                # Rounding near FLOAT_MAX can itself produce an infinite string.
                number(rendered, other, 0)
            except ValueError:
                if key == "latent_mode":
                    restore_mode()
                    return False
                return True
            note = "與同一筆製程產濕量同步（2501 kJ/kg 初估）"
            source_record = self.provenance.get(source, {})
            other_value = self.variables[other].get()
            # Recognize this app's unchanged forward conversion, not merely
            # approximately equal numbers. Never round-trip the rounded display
            # back over its original string, source note or timestamp. Checking
            # the saved record also works after reload, without hidden state.
            if (
                key == "latent_mode"
                and source_record.get("source") == "單位等值換算"
                and source_record.get("note") == note
                and source_record.get("value") == self.variables[source].get()
                and self.provenance.get(other, {}).get("value", other_value) == other_value
            ):
                reverse_factor = modes[current][1]
                try:
                    forward = number(other_value, other, 0) * reverse_factor
                    unchanged = format(number(forward, source, 0), ".15g") == self.variables[source].get()
                except ValueError:
                    unchanged = False
                if unchanged:
                    self.latent_mode_previous = current
                    return True
            record = provenance_record("單位等值換算", note, rendered)
            suspended = self.suspended
            self.suspended = True
            try:
                self.variables[other].set(rendered)
                self.provenance[other] = record
            finally:
                self.suspended = suspended
        self.latent_mode_previous = self.variables["latent_mode"].get()
        return True

    def _load_validated_project(self, p):
        p = validate_project(p)
        self.provenance = p["provenance"]
        form, self.extra_inputs = split_inputs(p["inputs"], self.variables)
        self.suspended = True
        try:
            for k, v in form.items():
                self.variables[k].set(v)
            for k, row in p["pressure_drop"].items():
                for f, v in row.items():
                    self.pd[k][f].set(v)
        finally:
            self.suspended = False
        self.pv_unit_last = self.variables["pv_pressure_unit"].get()
        self.pd_last_units = {k: row["unit"].get() for k, row in self.pd.items()}
        if self.variables["upw_quality_mode"].get() == "自動參考值":
            self.suspended = True
            self.variables["upw_res"].set(
                QUALITY_PRESETS[self.variables["upw_type"].get()]
            )
            if self.provenance["upw_res"]["source"] == "原廠資料":
                self.field_drafts["upw_res"] = copy.deepcopy(self.provenance["upw_res"])
                self.field_drafts["upw_res"].setdefault("value", p["inputs"]["upw_res"])
                self.provenance["upw_res"] = provenance_record(
                    "系統預設",
                    "目前為自動水型參考；原自訂證據已保留",
                    self.variables["upw_res"].get(),
                )
            self.suspended = False
        self.latent_mode_previous = self.variables["latent_mode"].get()
        self.upw_mode_previous = self.variables["upw_quality_mode"].get()
        self.interlocks()
        self.recalculate()
        self.notify_children()

    def apply_project(self, p):
        transition.require_editable(self)
        self._load_validated_project(p)
        self.unit_previous = {
            k: self.variables[k].get() for k in list(UNIT_VALUES) + ["u_unit"]
        }

    def _apply_common_interlocks(self):

        def enable(key, on):
            w = self.widgets[key]
            w.configure(
                state=(
                    ("readonly" if FIELDS[key]["options"] else "normal")
                    if on
                    else "disabled"
                )
            )

        self.form_rows["upw_v"].winfo_children()[0].configure(
            text=self.variables["upw_v_mode"].get()
        )
        inactive = main_inactive({k: v.get() for k, v in self.variables.items()})
        for key in self.widgets:
            enable(key, key not in inactive)
        if not self.pd_widgets:
            return
        row = self.pd[self.selected_pd]
        states = {
            "rate": row["mode"].get() == "手動阻力率",
            "sum_k": row["fitting_mode"].get() == "直接 K 值",
            "static_m": row["boundary"].get() == "開式系統"
            and self.selected_pd in PD_KEYS[:5],
        }
        for k in [
            "elbow_ld",
            "tee_ld",
            "reducer_ld",
            "valve_ld",
            "elbows",
            "tees",
            "reducers",
            "valves",
        ]:
            states[k] = row["fitting_mode"].get() == "等效長 L/D"
        states["equipment_drop"] = row["equipment_known"].get() == "已知設備壓差"
        for k, on in states.items():
            self.pd_widgets[k].configure(state="normal" if on else "disabled")
        self.update_visibility()

    def interlocks(self):
        self._apply_common_interlocks()
        mau = self.variables["sys_type"].get().startswith("MAU")
        for k in ["dcc_airflow_mode", "dcc_airflow_cmh", "dcc_air_approach"]:
            on = mau and (
                k != "dcc_airflow_cmh"
                or self.variables["dcc_airflow_mode"].get() == "獨立 DCC 循環"
            )
            self.widgets[k].configure(
                state=(
                    (
                        "readonly"
                        if FIELDS[k]["options"]
                        and not isinstance(self.widgets[k], ttk.Checkbutton)
                        else "normal"
                    )
                    if on
                    else "disabled"
                )
            )
        self.update_visibility()

    def _calculate_project(self, explicit=False):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.bad_key = None
        self.bad_pd = None
        for k, w in self.widgets.items():
            if not FIELDS[k]["options"]:
                w.configure(style="TEntry")
        try:
            r = calculate(self.snapshot())
        except (InputError, ValueError, KeyError, TypeError) as e:
            self.result = None
            msg = error_text(e)
            self.last_error = msg
            self.latent_text.set("條件未通過，請修正輸入。")
            self.psy_label.config(text="")
            self.topology.config(text="")
            for label in self.result_labels.values():
                label.config(text="條件未通過檢核")
            for key in PD_KEYS:
                self.grid.item(key, values=("—", "—", "—", "—"))
            if HAS_PLOT and not getattr(self, "last_good_result", None):
                self._plot_key = None
                self.ax.clear()
                self.ax.text(
                    0.5,
                    0.5,
                    "條件未通過檢核，流程圖暫停",
                    ha="center",
                    transform=self.ax.transAxes,
                )
                self.queue_plot()
            field = getattr(e, "field_name", None)
            from .fusion_settings import SETTINGS
            self.bad_key = field if field in self.widgets or field in SETTINGS else None
            self.bad_pd = field[3:] if field and field.startswith("PD:") else None
            if self.bad_key in self.widgets and (not FIELDS[self.bad_key]["options"]):
                self.widgets[self.bad_key].configure(style="Invalid.TEntry")
            self.status.config(text=msg[:160], style="Error.TLabel")
            self.summary.config(text="待修正：" + msg)
            self.export_button.state(["disabled"])
            self.set_report("目前條件未通過檢核，不能匯出。\n" + msg + ("\n\n【上次有效結果／待重算】\n" + report(self.last_good_result) if getattr(self, "last_good_result", None) else ""))
            if explicit:
                self.focus_issue()
            return
        self.decorate_receipts(r)
        self.result = r
        self.last_good_result = r
        self.update_visibility()
        self.status.config(
            text="檢核完成｜"
            + str(len(r["warnings"]))
            + " 項待確認｜"
            + (
                "未儲存變更"
                if r["hash"] != self.saved_hash
                else "未另存預設專案" if not self.path else "專案已儲存"
            ),
            style="Good.TLabel",
        )
        self.export_button.state(["!disabled"])
        self.set_report(report(r))
        self.render_results()
        self.draw()

    def schedule_recalculation(self):
        generation = getattr(self, "_workspace_generation", 0)
        def run():
            if generation == getattr(self, "_workspace_generation", 0) and transition.editable(self):
                self.recalculate()
        return self.root.after(650, run)

    def recalculate(self, explicit=False, *, _workspace_owner=None):
        owner = getattr(self, "_workspace_transition", None)
        if owner and _workspace_owner is not owner:
            return
        if getattr(self, "_workspace_main", None) is not None and not (owner and _workspace_owner is owner):
            if explicit:
                return self.retry_workspace_presentation()
            return
        return self.recalculate_workspace_view(explicit)

    def recalculate_workspace_view(self, explicit=False):
        self.partial_hvac = None
        self._calculate_project(explicit)
        if self.result:
            for label in self.result_labels.values():
                label.config(style="Muted.TLabel")
            gas = self.result["gas"].values()
            self.result_labels[3].config(
                style="Error.TLabel" if any(v.get("liquefaction_risk") is True for v in gas)
                else "Warn.TLabel" if any(v.get("warnings") for v in self.result["gas"].values()) else "Muted.TLabel")
            q = self.result["quality"]
            self.quality_label.config(text=quality_text(q), style=quality_style(q))
            self.status.config(
                text="計算完成｜工程評估：" + q["status"] + "｜待資料請補依據；未達請調整設備／條件", style=quality_style(q)
            )
            first = next(
                (
                    x
                    for state in ["未達", "待資料"]
                    for x in q["items"]
                    if x["status"] == state and x["field"]
                ),
                None,
            )
            if first:
                from .fusion_settings import SETTINGS
                self.bad_key = (
                    first["field"] if first["field"] in self.widgets or first["field"] in SETTINGS else None
                )
                self.bad_pd = (
                    first["field"][3:] if first["field"].startswith("PD:") else None
                )
            return
        domains = independent_domains(self.snapshot())
        self.domain_results = domains
        r = domains["hvac"]["result"]
        if r:
            self.result = r
            self.render_results()
            self.draw()
            self.update_visibility()
            self.result = None
            self.partial_hvac = r
        for name, page in [("gas", 3), ("electric", 4)]:
            d = domains[name]
            if d["error"]:
                self.result_labels[page].config(
                    text="本頁待修正：" + d["error"], style="Error.TLabel"
                )
            elif name == "gas":
                self.result_labels[page].config(
                    text="\n".join(
                        (
                            f"{v['type']}：{v['size']}／{v['actual_lpm']:.2f} ALPM"
                            + ("｜" + "；".join(v.get("warnings", [])) if v.get("warnings") else "")
                            for v in d["result"].values()
                        )
                    )
                    + ("\n" + "\n".join(w for w in d.get("warnings", []) if not w.startswith("特氣 "))
                       if d.get("warnings") else ""),
                    style="Error.TLabel" if any(v.get("liquefaction_risk") is True for v in d["result"].values())
                    else "Warn.TLabel" if d.get("warnings") or any(v.get("warnings") for v in d["result"].values()) else "Muted.TLabel",
                )
            else:
                self.result_labels[page].config(
                    text="\n".join(
                        (
                            f"{k}：運轉 {v['current_a']:.2f} A／設計 {v['design_current_a']:.2f} A（初估）"
                            for k, v in d["result"].items()
                        )
                    ),
                    style="Muted.TLabel",
                )
        valid = "、".join((k for k, v in domains.items() if v["result"] is not None))
        self.quality_label.config(
            text="整體尚未完成；保留有效分頁：" + valid, style="Error.TLabel"
        )
        self.status.config(
            text="部分結果可用；" + getattr(self, "last_error", "請修正輸入"),
            style="Error.TLabel",
        )

    def _legacy_close(self):
        if self.confirm_discard():
            self.root.destroy()

    def close(self):
        return self.close_workspace()

    def show_simple_tools(self):
        if getattr(self, "simple_app", None) is not None:
            return self.simple_app.show_simple_tools()
        # Direct developer/legacy entry also reuses this same top-level window.
        from .simple_desktop import SimpleToolsApp
        widgets = [w for w in self.root.winfo_children() if w.winfo_manager() == "grid"]
        for widget in widgets:
            widget.grid_remove()
        simple = SimpleToolsApp(self.root)
        simple.workbench = self
        simple.workbench_widgets = widgets
        simple.simple_widgets = [w for w in self.root.winfo_children() if w not in widgets and w.winfo_manager() == "grid"]
        self.simple_app = simple
        return simple

    def autosave(self):
        return self.autosave_workspace()

    def export_html(self):
        if not self.ensure_result():
            return
        result = self.result
        snapshot_hash = project_hash(self.snapshot())
        generation = transition.token(self)
        path = filedialog.asksaveasfilename(
            defaultextension=".html", filetypes=[("可列印設計摘要", "*.html")]
        )
        if path:
            if not transition.editable(self) or transition.token(self) != generation or self.result is not result or snapshot_hash != project_hash(self.snapshot()):
                messagebox.showwarning(
                    "匯出已停止", "匯出期間條件已變更，請重新計算後再匯出。", parent=self.root)
                return False
            try:
                atomic_text(path, summary_html(self.result))
                messagebox.showinfo("已匯出", "使用瀏覽器開啟，可列印或另存 PDF。")
            except OSError as exc:
                messagebox.showerror("匯出失敗", str(exc), parent=self.root)
