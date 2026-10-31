"""Real Tk acceptance tests for the 18 reviewed interaction issues."""
from pathlib import Path
import sys, json, copy, tempfile, os, math
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageGrab
from facility_studio.desktop import DesktopApp
from facility_studio.ahu_desktop import AHUWindow
from facility_studio.workspace_view import WorkspaceWindow, apply_updates
from facility_studio.tools_view import QuickToolsWindow
from facility_studio.schema import FIELDS, default_project
from facility_studio.workspace_store import read_workspace
from facility_studio.project_store import provenance_record
from facility_studio.reports import report
checks=[];dialogs=[];errors=[]
def check(name,value):
    checks.append(dict(name=name,passed=bool(value)))
    assert value,name
messagebox.showerror=lambda *a,**k: errors.append(str(a))
messagebox.showinfo=lambda *a,**k: None
messagebox.askokcancel=lambda *a,**k: dialogs.append(str(a)) or True
messagebox.askyesno=lambda *a,**k: True
messagebox.askyesnocancel=lambda *a,**k: False

def input_set(a,**values):
    a.suspended=True
    for k,v in values.items():a.variables[k].set(str(v))
    a.suspended=False;a.changed();a.recalculate()

with tempfile.TemporaryDirectory(prefix='facility552_') as td:
    os.environ['LOCALAPPDATA']=td
    root=tk.Tk();a=DesktopApp(root);root.update()
    check('01_default_valid',a.result is not None)
    # Disabled values may be unfinished drafts without invalidating adopted inputs.
    a.variables['en_dcc_rt'].set('');a.recalculate()
    check('02_inactive_blank_ignored',a.result is not None and str(a.widgets['en_dcc_rt'].cget('state'))=='disabled')
    a.variables['sys_type'].set(FIELDS['sys_type']['options'][0]);a.recalculate()
    check('03_reactivated_draft_located',a.result is None and a.bad_key=='en_dcc_rt')
    a.variables['en_dcc_rt'].set('3.4');a.recalculate()
    # Switching the pressure boundary retains the open draft but never adds building height to closed loops.
    p=a.pd['CHW'];p['boundary'].set('開式系統');p['static_m'].set('8');a.recalculate()
    open_pressure=a.result['pressure']['CHW']['total_pa']
    p['boundary'].set('閉式循環');a.recalculate()
    check('04_closed_adopts_zero_keeps_draft',a.result['pressure']['CHW']['static_pa']==0 and p['static_m'].get()=='8')
    p['boundary'].set('開式系統');a.recalculate()
    check('05_reopen_restores_pressure',math.isclose(a.result['pressure']['CHW']['total_pa'],open_pressure))
    p['boundary'].set('閉式循環');a.recalculate()
    # Latent inputs preserve the physical moisture load across unit switches.
    a.variables['latent_mode'].set('已知潛熱 kW');a.variables['process_latent_kw'].set('1');a.recalculate()
    moisture=a.result['moisture']
    for _ in range(3):
        a.variables['latent_mode'].set('已知產濕量 kg/h');a.recalculate()
        check('06_kg_h_equivalent_'+str(_),math.isclose(a.result['moisture'],moisture,rel_tol=1e-10))
        a.variables['latent_mode'].set('已知潛熱 kW');a.recalculate()
    check('07_latent_roundtrip',math.isclose(float(a.variables['process_latent_kw'].get()),1,rel_tol=1e-10))
    # Auto water specifications must detach prior OEM attribution and restore it when returning to custom.
    a.variables['upw_quality_mode'].set('自訂規格');a.variables['upw_res'].set('17.5 MΩ·cm')
    a.provenance['upw_res']=provenance_record('原廠資料','OEM-WATER-01','17.5 MΩ·cm')
    a.variables['upw_quality_mode'].set('自動參考值');a.variables['upw_type'].set('RO (逆滲透水)')
    check('08_auto_spec_resets_provenance',a.provenance['upw_res']['source']=='系統預設' and '0.05' in a.variables['upw_res'].get())
    a.variables['upw_quality_mode'].set('自訂規格')
    check('09_custom_spec_and_source_restored',a.variables['upw_res'].get()=='17.5 MΩ·cm' and a.provenance['upw_res']['source']=='原廠資料')
    a.recalculate();work=WorkspaceWindow(root,a);root.update()
    work.tree.selection_set('oa_t');root.update();work.origin.set('原廠資料');work.note.set('OEM-OLD')
    a.variables['oa_t'].set('34');root.update();work.mark()
    check('10_source_editor_rejects_stale_value',a.provenance['oa_t']['source']=='使用者輸入' and errors)
    errors.clear();work.tree.selection_set('oa_rh');root.update();work.tree.selection_set('oa_t');root.update()
    work.origin.set('原廠資料');work.note.set('OEM-NEW');work.mark()
    check('11_source_captures_current_value',a.provenance['oa_t']['value']=='34' and bool(a.provenance['oa_t']['recorded_at']))
    a.recalculate();work.capture('A');a.variables['light_lux'].set('650');a.recalculate();work.capture('B')
    check('12_AB_frozen_and_named','A：' in work.comparison_string() and a.comparisons['A']['hash']!=a.comparisons['B']['hash'])
    work.win.destroy();a.children.remove(work)
    ahu=AHUWindow(root,a);root.update();ahu.link_requirements();root.update()
    check('13_linked_basis_fixed',str(ahu.widgets['flow_basis'].cget('state'))=='disabled' and '固定' in ahu.widgets['flow_basis'].get())
    ahu.vars['summer_c1_mode'].set('指定出口乾球');ahu.vars['summer_c1_t'].set('30');root.update()
    check('14_seasonal_override_interlock',str(ahu.widgets['c1_t'].cget('state'))=='disabled' and ahu.rows['summer_c1_t'].winfo_manager())
    ahu.vars['humidifier'].set('電極式蒸汽');root.update()
    check('15_electrode_requirements_in_basic',all(ahu.rows[k].winfo_manager() for k in ['steam_conductivity','steam_cond_min','steam_cond_max']))
    ahu.vars['humidifier'].set('循環水洗濕膜');ahu.vars['summer_c1_mode'].set('自動需求');ahu.vars['steam_kw'].set('');ahu.calculate()
    check('16_inactive_steam_draft_valid',ahu.result is not None)
    ahu.vars['fan_qty'].set('4');ahu.calculate()
    check('17_control_note_tracks_fans','4 台 EC' in ahu.control_notes.cget('text') and '8 台 EC' not in ahu.control_notes.cget('text'))
    ahu.return_utilities();root.update();a.recalculate()
    check('18_receipt_created',bool(a.transfer_receipts) and a.variables['e_np_fan'].get()=='31.2')
    ahu.vars['fan_unit_kw'].set('6');root.update()
    check('19_changed_source_flagged_in_report','過期' in a.receipt_status.get() and '來源快照' in report(a.result) and '快照過期' in report(a.result))
    ahu.calculate();ahu.return_utilities();a.recalculate()
    check('20_refreshed_source_applied',a.variables['e_np_fan'].get()=='24.0' and all('過期' not in x['status'] for x in a.transfer_receipts))
    # Relink the changed main boundary once, then renaming must not invalidate engineering conditions.
    ahu.link_requirements();a.variables['project_name'].set('通用廠房驗收');a.recalculate();ahu.ensure()
    check('21_rename_preserves_boundary','工程邊界一致' in ahu.result['link_status'])
    # All windows, A/B, source receipts, and unfinished input must survive an entire-project save.
    ahu.vars['steam_kw'].set('');path=Path(td)/'workspace.json'
    check('22_save_all',a.save_workspace(path))
    saved=read_workspace(path)
    check('23_saved_complete_graph',len(saved['ahus'])==1 and set(saved['comparisons'])=={'A','B'} and bool(saved['receipts']))
    ident=a.project_id;old_ahu=ahu
    a.new();root.update()
    check('24_new_clears_owned_windows_and_AB',a.project_id!=ident and not a.comparisons and not old_ahu.win.winfo_exists())
    a.apply_workspace(saved,path);root.update()
    check('25_load_restores_identity_and_all_drafts',a.project_id==ident and len(a.ahu_documents)==1 and len(a.comparisons)==2)
    ahu=AHUWindow(root,a,document=next(iter(a.ahu_documents.values())));root.update()
    check('26_reopen_saved_AHU_draft',ahu.vars['steam_kw'].get()=='' and ahu.result is not None)
    # Boundary-invalid quick results are rejected before touching the receiving project.
    quick=QuickToolsWindow(root,a);quick.tool.set('濕空氣計算');quick.build();quick.values['first'].set('70');quick.values['second'].set('10');quick.calculate()
    check('27_quick_outside_main_range_computable',quick.result is not None)
    before=a.snapshot();quick.send_to_project()
    check('28_preflight_rolls_back',a.snapshot()==before and bool(errors));errors.clear()
    quick.values['first'].set('33');quick.values['second'].set('60');quick.calculate();state=quick.result
    quick.values['mode'].set('乾球＋濕球');quick.calculate()
    check('29_named_fields_and_equivalent_mode',quick.field_labels['second'].cget('text')=='濕球 °C' and math.isclose(quick.result['rh'],state['rh'],rel_tol=1e-6))
    quick.target.set('冬季外氣');quick.send_to_project()
    check('30_quick_target_choice',math.isclose(float(a.variables['ow_t'].get()),33))
    quick.tool.set('水量與熱量');quick.build();quick.values['first'].set('275');quick.values['second'].set('5');quick.calculate()
    quick.tool.set('單位轉換');quick.build();quick.tool.set('水量與熱量');quick.build()
    check('31_tool_draft_retained',quick.values['first'].get()=='275')
    quick.calculate();quick.target.set('PCW');quick.send_to_project()
    check('32_water_scope_and_full_properties',all(key in dialogs[-1] for key in ['ρ=', 'cp=', 'μ=']))
    check('33_water_target_and_scope','PCW' in dialogs[-1] and 'MCHW、CHW、DCCW、PCW、HW' in dialogs[-1] and a.variables['pcw_tot'].get()=='275.0' and a.variables['water_mu'].get()=='0.001')
    quick.tool.set('風管定寸');quick.build();quick.target.set('GEX');quick.calculate();quick.send_to_project()
    check('34_duct_preview_scope_and_margin','GEX、SEX、AEX、VEX、HEX' in dialogs[-1] and '名目' in dialogs[-1] and '→' in a.result_labels[5].cget('text'))
    check('35_duct_dimensions_visible','×' in a.result_labels[5].cget('text') and 'mm' in a.result_labels[5].cget('text'))
    a.pd['CHW']['manual_id_mm'].set('120');a.recalculate();a.selected_pd='CHW';a.update_visibility()
    check('36_pressure_adopted_id_visible','120.0' in a.pd_quick.cget('text') and '手填' in a.pd_quick.cget('text'))
    a.variables['e_eff'].set('0');a.recalculate();check('37_error_label',FIELDS['e_eff']['label'] in a.status.cget('text'))
    a.variables['e_eff'].set('.9');a.recalculate();a.variables['exhaust_margin_pct'].set('7');a.update_visibility()
    check('38_hidden_modified_assumptions','7' in a.assumption_labels[5].cget('text'))
    check('39_plain_boolean_control',isinstance(a.widgets['allow_reheat'],ttk.Checkbutton))
    a.recalculate();check('40_summer_summary_and_design_DCC','夏季' in a.summary.cget('text') and '夏冬較大' in a.summary.cget('text'))
    # Actual screenshots at standard and compact sizes, including independent tools and stage inputs.
    quick.win.geometry('1100x800+30+30');quick.tool.set('濕空氣計算');quick.build();quick.calculate();quick.win.lift();root.update()
    ImageGrab.grab().save(ROOT/'evidence/V552_QuickTools.png');quick.close(force=True)
    ahu.win.geometry('1120x850+20+20');ahu.win.lift();ahu.nb.select(0);ahu.reveal('summer_h1_mode');root.update()
    ImageGrab.grab().save(ROOT/'evidence/V552_AHU_Conditions.png')
    ahu.nb.select(1);ahu.calculate();ahu.output_canvas.yview_moveto(.38);root.update()
    ImageGrab.grab().save(ROOT/'evidence/V552_AHU_Chart.png');ahu.close(force=True)
    root.geometry('1280x940+0+0');a.show_page(0);a.season.set('冬季');a.draw();root.update()
    ImageGrab.grab().save(ROOT/'evidence/V552_Overview.png')
    root.geometry('880x600');root.update()
    check('41_compact_actions_visible',a.calc_button.winfo_rootx()+a.calc_button.winfo_width()<=root.winfo_rootx()+root.winfo_width() and a.calc_button.winfo_rooty()+a.calc_button.winfo_height()<=root.winfo_rooty()+root.winfo_height())
    ImageGrab.grab().save(ROOT/'evidence/V552_Compact.png')
    check('42_no_unexpected_modals',not errors)
    (ROOT/'evidence/V552_Interaction_Checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(checks)} V5.5.2 real Tk checks passed')
    root.destroy()
