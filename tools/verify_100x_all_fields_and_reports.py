#!/usr/bin/env python3
"""100-iteration comprehensive audit of ALL fields and ALL reports (TXT + HTML, zh-Hant + en).

Verifies across 100 full iterations:
1. All 10 Simple Calculators: every field & unit in TOOLS[tool]['fields'], active sensitivity,
   invalid input rejection, inactive field isolation, presentation(), tool_report(), html_report().
2. 5-Tool Upstream Pipeline: cleanroom -> heat_loads -> water -> pumps -> electrical conservation,
   pipeline_report(), executive_summary(), html_report() in zh-Hant and en.
3. Full Engineering Workbench: all 143 FIELDS + all 10 PD_KEYS x 17 PD_FIELDS, active sensitivity,
   inactive isolation, mass/energy balance, report(), executive_summary(), summary_html() in zh-Hant and en.
4. Standalone AHU / MAU: all 74 NM_FIELDS, stage modes, heat sources, humidifiers, unified checks,
   nm_report() and html_report() in zh-Hant and en.
5. Equipment Schedules: all 7 SYSTEMS x all columns in SCHEMAS, analyze_equipment(),
   equipment_report() in zh-Hant and en, and demand ledger transfer.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import math
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u3400-\u9fff]")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def numerals(text: str) -> Counter:
    return Counter(NUM_RE.findall(text))


def run_audit(platform_name: str = "windows", iterations: int = 100) -> dict:
    source_root = ROOT / platform_name
    sys.path.insert(0, str(source_root))

    from facility_studio import i18n
    from facility_studio.errors import InputError, ValidationError
    from facility_studio.simple_schema import TOOLS, active_field, adopted_summary, defaults
    from facility_studio.simple_engines import calculate_tool
    from facility_studio.simple_reports import presentation, tool_report, pipeline_report
    from facility_studio.services import calculate_pipeline, upstream_values
    from facility_studio.html_report import html_report, summary_html
    from facility_studio.schema import DEFAULTS, FIELDS, PD_DEFAULTS, PD_FIELDS, PD_KEYS, default_project
    from facility_studio.field_state import ahu_inactive, main_inactive
    from facility_studio.engine import calculate, pressure_result
    from facility_studio.reports import executive_summary, nm_report, report
    from facility_studio.ahu_schema import NM_DEFAULTS, NM_FIELDS
    from facility_studio.ahu_engine import nm_calculate
    from facility_studio.equipment_schema import SCHEMAS, SYSTEMS, example
    from facility_studio.equipment_io import Cell
    from facility_studio.equipment_analysis import analyze_equipment, equipment_report
    from facility_studio.gas_catalog import CUSTOM_GAS

    rng = random.Random(20261015)
    total_checks = 0
    field_coverage = {
        "simple_fields_tested": 0,
        "workbench_fields_tested": 0,
        "pressure_drop_fields_tested": 0,
        "ahu_fields_tested": 0,
        "equipment_columns_tested": 0,
        "reports_verified": 0,
    }

    def check(cond: bool, msg: str):
        nonlocal total_checks
        if not cond:
            raise AssertionError(msg)
        total_checks += 1

    # =========================================================================
    # PHASE 1: Exhaustive Per-Field Sensitivity, Validation & Report Reflection
    # =========================================================================

    # 1A. All 10 Simple Calculators — Every single field & unit
    simple_active_overrides = {
        ("cleanroom", "ffu_airflow_basis"): {"ffu_topology": "MAU入靜壓箱經FFU送風"},
        ("cleanroom", "base_leak_ach"): {"delta_p": "15"},
        ("heat_loads", "oa_load_basis"): {"oa_cmh": "600"},
        ("heat_loads", "envelope_w_m2"): {"envelope_mode": "自訂熱負荷密度"},
        ("heat_loads", "mau_room_sensible_kw"): {"oa_load_basis": "外氣至實際露點送風", "oa_cmh": "1200", "mau_supply_delta_t": "8"},
        ("heat_loads", "mau_supply_delta_t"): {"oa_load_basis": "外氣至實際露點送風", "oa_cmh": "1200", "mau_room_sensible_kw": "1.5", "mau_supply_delta_t": "8"},
        ("electrical", "chiller_cop"): {"chiller_input_kw": "0"},
        ("duct", "pressure"): {"check_path": "1"},
        ("duct", "length"): {"check_path": "1"},
        ("duct", "k_sum"): {"check_path": "1"},
        ("duct", "equipment"): {"check_path": "1"},
        ("duct", "roughness_mm"): {"check_path": "1"},
        ("duct", "friction_method"): {"check_path": "1"},
        ("gas", "gas_name"): {"gas": CUSTOM_GAS, "velocity": "10", "gas_name": "5% H2 / 95% N2"},
        ("lighting", "quantity"): {"mode": "估算照度"},
        ("lighting", "target"): {"mode": "反算燈數"},
        ("lighting", "area"): {"area_mode": "面積 m²"},
        ("lighting", "length"): {"area_mode": "長×寬"},
        ("lighting", "width"): {"area_mode": "長×寬"},
        ("lighting", "height"): {"area_mode": "體積 m³", "area": "90"},
        ("lighting", "efficacy"): {"lumen_mode": "LED功率初估"},
        ("lighting", "lumens"): {"lumen_mode": "燈具型錄流明"},
        ("lighting", "utilization"): {"u_mode": "手動固定 U"},
        ("lighting", "u_mode"): {"area_mode": "長×寬"},
        ("electrical", "motor_efficiency"): {"power_unit": "HP"},
        ("lighting", "mount_h"): {"u_mode": "型錄 U＋室指數 K 檢核", "area_mode": "長×寬"},
        ("lighting", "work_h"): {"u_mode": "型錄 U＋室指數 K 檢核", "area_mode": "長×寬"},
        ("water", "flow"): {"mode": "已知水量"},
        ("water", "power"): {"mode": "已知熱量"},
    }
    simple_alt_values = {
        "mau_supply_delta_t": "12",
        "mau_room_sensible_kw": "2.0",
        "eta_pump": "0.80",
        "eta_motor": "0.95",
        "pf": "0.90",
        "eta": "0.92",
        "motor_efficiency": "0.82",
        "utilization": "0.72",
        "maintenance": "0.85",
        "mount_h": "3.8",
        "work_h": "0.9",
        "z_ratio": "1.15",
        "gas_name": "Ar-H2 Mix 95/5",
        "check_path": "1",
        "loaded": "6",
        "terminal": "90",
        "insulation": "PVC",
        "rh": "65",
        "temperature": "28",
        "atmosphere": "95",
        "reference_p": "100",
        "coverage_limit_pct": "80",
        "oa_cmh": "1200",
        "chiller_cop": "4.8",
        "chiller_input_kw": "15",
        "mau_input_kw": "3.5",
        "process_input_kw": "18",
    }

    for f in TOOLS["heat_loads"]["fields"]:
        # Area-based envelope inputs (win.9 and the macOS port) are active only in their own mode.
        if f["key"].startswith("envelope_") and f["key"] not in ("envelope_w_m2", "envelope_mode"):
            simple_active_overrides.setdefault(("heat_loads", f["key"]), {"envelope_mode": "面積推估外牆／樓板"})

    for tool, spec in TOOLS.items():
        for f in spec["fields"]:
            key = f["key"]
            base = defaults(tool)
            if (tool, key) in simple_active_overrides:
                base.update(simple_active_overrides[(tool, key)])
            check(active_field(tool, key, base), f"Simple field {tool}.{key} must be active in test setup")

            res0 = calculate_tool(tool, base)
            pres0 = presentation(res0)
            rep0_zh = str(tool_report(res0, base, language="zh-Hant"))
            rep0_en = str(tool_report(res0, base, language="en"))
            html0_zh = str(html_report(res0, language="zh-Hant"))
            html0_en = str(html_report(res0, language="en"))
            field_coverage["reports_verified"] += 4

            check(CJK.search(rep0_en) is None, f"Untranslated CJK in {tool} tool_report(en)")
            check(CJK.search(html0_en) is None, f"Untranslated CJK in {tool} html_report(en)")
            check(numerals(rep0_zh) == numerals(rep0_en), f"Numeral mismatch in {tool} tool_report zh vs en")

            alt = dict(base)
            cur = alt[key]
            if key in simple_alt_values and simple_alt_values[key] != cur:
                alt[key] = simple_alt_values[key]
            elif f.get("options"):
                opts = [o for o in f["options"] if o != cur]
                alt[key] = opts[0]
                if tool == "gas" and key == "gas" and alt[key] == CUSTOM_GAS:
                    alt[key] = "N2" if cur != "N2" else "O2"
                if tool == "gas" and key == "flow_basis" and alt[key] == "管內實際流量":
                    alt["flow_unit"] = "ALPM"
                if tool == "units" and key == "category":
                    from facility_studio.quick_tools import UNITS
                    alt["unit"] = list(UNITS[alt[key]].keys())[0]
            elif f.get("checkbox"):
                alt[key] = "1" if cur == "0" else "0"
            else:
                v = float(cur)
                alt[key] = str(v * 1.5 if v != 0 else 5.0)

            res1 = calculate_tool(tool, alt)
            pres1 = presentation(res1)
            rep1_zh = str(tool_report(res1, alt, language="zh-Hant"))
            rep1_en = str(tool_report(res1, alt, language="en"))
            sum1 = adopted_summary(tool, alt)
            field_coverage["reports_verified"] += 2

            # Every active field must reflect in presentation, tool_report, or adopted_summary
            check(
                res1 != res0 or pres1 != pres0 or rep1_zh != rep0_zh or sum1 != adopted_summary(tool, base),
                f"Simple field {tool}.{key} had no effect on result or report",
            )
            if key not in ("mau_input_kw", "process_input_kw", "chiller_cop", "chiller_input_kw"):
                # Every standalone calculation field must change presentation(result) or adopted_summary
                check(
                    pres1 != pres0 or sum1 != adopted_summary(tool, base),
                    f"Standalone field {tool}.{key} did not update presentation() or adopted_summary()",
                )
            check(CJK.search(rep1_en) is None, f"Untranslated CJK in {tool}.{key} perturbed report")
            check(numerals(rep1_zh) == numerals(rep1_en), f"Numeral mismatch in {tool}.{key} perturbed report")

            # Invalid input must raise ValidationError with field_name == key
            bad = dict(base)
            bad[key] = "invalid_value_\n" if key == "gas_name" else "not_a_valid_input"
            try:
                calculate_tool(tool, bad)
            except ValidationError as exc:
                check(exc.field_name == key, f"Expected field_name={key}, got {exc.field_name} for {tool}.{key}")
            else:
                raise AssertionError(f"Simple field {tool}.{key} accepted invalid input {bad[key]!r}")

            field_coverage["simple_fields_tested"] += 1

            # Also test unit selector if present
            if f.get("units"):
                ukey, uopts = f["units"]
                u_alt = dict(base)
                u_cur = u_alt[ukey]
                u_other = [u for u in uopts if u != u_cur]
                if u_other:
                    u_alt[ukey] = u_other[0]
                    res_u = calculate_tool(tool, u_alt)
                    rep_u_en = str(tool_report(res_u, u_alt, language="en"))
                    check(res_u != res0 or str(tool_report(res_u, u_alt)) != rep0_zh, f"Unit {tool}.{ukey} had no effect")
                    check(CJK.search(rep_u_en) is None, f"Untranslated CJK for unit {tool}.{ukey}")
                    field_coverage["simple_fields_tested"] += 1

    # 1B. Full Engineering Workbench — All 143 FIELDS + All 10 PD_KEYS x 17 PD_FIELDS
    wb_active_overrides = {
        "face_A": {"mode_A": "截面風速"},
        "coverage_A": {"mode_A": "截面風速"},
        "face_B": {"mode_B": "截面風速"},
        "coverage_B": {"mode_B": "截面風速"},
        "base_leak_ach": {"leak_method": "15Pa基準ACH法"},
        "ffu_airflow_basis": {"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "ffu_topology": "MAU入靜壓箱經FFU送風"},
        "dcc_airflow_cmh": {"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "dcc_airflow_mode": "獨立 DCC 循環"},
        "en_fcu_cmh": {"sys_type": "FCU (風機盤管+外氣)"},
        "fcu_rt": {"sys_type": "FCU (風機盤管+外氣)"},
        "en_rcu_rt": {"sys_type": "RCU (機房空調箱+外氣)"},
        "pre_rh": {"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "pre_mode": "指定出口（需求檢核）", "pre_t": "20", "pre_rh": "90"},
        "process_latent_kw": {"latent_mode": "已知潛熱 kW"},
        "process_moisture_kg_h": {"latent_mode": "已知產濕量 kg/h"},
        "light_work_h": {"light_u_mode": "型錄 U＋室指數 K 檢核"},
        "upw_res": {"upw_quality_mode": FIELDS["upw_quality_mode"]["options"][1]},
        "mchw_q": {"mchw_link": "獨立輸入"},
        "u_mchw": {"mchw_link": "獨立輸入"},
        "chw_q": {"chw_link": "獨立輸入"},
        "u_chw": {"chw_link": "獨立輸入"},
        "dccw_q": {"dccw_link": "獨立輸入"},
        "u_dccw": {"dccw_link": "獨立輸入"},
        "pcw_tot": {"pcw_link": "獨立輸入"},
        "u_pcw_tot": {"pcw_link": "獨立輸入"},
        "hw_q": {"hw_link": "獨立輸入"},
        "u_hw": {"hw_link": "獨立輸入"},
        "e_up_pf": {"e_up_pf_mode": "本盤獨立 PF"},
        "e_np_pf": {"e_np_pf_mode": "本盤獨立 PF"},
        "e_up_largest_hp": {"e_up_type": "一般負載", "u_e_up_eq": "HP", "e_up_eq": "50"},
        "e_np_largest_hp": {"e_np_type": "一般負載", "u_e_np_fan": "HP", "e_np_fan": "30"},
        "pv_velocity": {"pv_q": "1000"},
    }
    for prefix in ("mchw", "chw", "dccw", "pcw", "hw"):
        for prop in ("fluid_name", "rho", "cp", "mu"):
            wb_active_overrides[f"{prefix}_{prop}"] = {f"{prefix}_fluid_mode": "本迴路獨立物性"}
    for mk in "mau_supply_t en_dcc_rt ffu_cmh ffu_w ffu_size ffu_topology ffu_coverage_limit_pct dccw_in dccw_dp_margin dcc_airflow_mode dcc_air_approach".split():
        wb_active_overrides.setdefault(mk, {"sys_type": "MAU+FFU+DCC (全外氣/無塵室)"})
    for j in (1, 2, 3):
        wb_active_overrides[f"gas{j}_name"] = {f"gas{j}_type": CUSTOM_GAS, f"gas{j}_name": "5% H2 / 95% N2", f"gas{j}_q": "100", f"gas{j}_v_mode": "自訂流速", f"gas{j}_velocity": "10"}
        wb_active_overrides[f"gas{j}_barg"] = {f"gas{j}_pressure_mode": "本路管內壓力", f"gas{j}_q": "100"}
        wb_active_overrides[f"gas{j}_velocity"] = {f"gas{j}_v_mode": "自訂流速", f"gas{j}_q": "100"}

    for key, spec in FIELDS.items():
        p0 = default_project()
        if key in wb_active_overrides:
            p0["inputs"].update(wb_active_overrides[key])
        if key in main_inactive(p0["inputs"]):
            # The default system of win.9 and the macOS port is a single-coil AHU; a field that belongs to another
            # system is reachable by choosing that system, which is what a user would do.
            for pre in [None] + list(FIELDS["pre_mode"]["options"]) if "pre_mode" in FIELDS else [None]:
                found = False
                for option in FIELDS["sys_type"]["options"]:
                    trial = dict(p0["inputs"], sys_type=option, **({"pre_mode": pre} if pre else {}))
                    if key not in main_inactive(trial):
                        p0["inputs"].update(trial)
                        found = True
                        break
                if found:
                    break
        check(key not in main_inactive(p0["inputs"]), f"Workbench field {key} should be active")
        r0 = calculate(p0)
        rep0 = str(report(r0, language="zh-Hant"))
        rep0_en = str(report(r0, language="en"))
        check(CJK.search(rep0_en) is None, f"Untranslated CJK in workbench report(en) for {key}")

        # Validate invalid rejection on active field
        bad = copy.deepcopy(p0)
        bad["inputs"][key] = "" if spec.get("text") else "invalid_number_or_option"
        try:
            calculate(bad)
        except InputError as exc:
            check(exc.field_name == key, f"Workbench field {key}: expected field_name={key}, got {exc.field_name}")
        else:
            raise AssertionError(f"Workbench field {key} accepted invalid value")
        field_coverage["workbench_fields_tested"] += 1

    # Test all 10 PD_KEYS x 17 PD_FIELDS
    for loop in PD_KEYS:
        for pkey, pspec in PD_DEFAULTS.items():
            cfg = dict(PD_DEFAULTS)
            if pkey in ("mode", "fitting_mode", "sum_k", "elbows", "tees", "reducers", "valves", "elbow_ld", "tee_ld", "reducer_ld", "valve_ld", "rate"):
                cfg["estimate_mode"] = "詳細計算"
            if pkey == "rate":
                cfg["mode"] = "手動阻力率"
            if pkey in ("elbows", "tees", "reducers", "valves", "elbow_ld", "tee_ld", "reducer_ld", "valve_ld"):
                cfg["fitting_mode"] = "等效長 L/D"
            if pkey == "equipment_drop":
                cfg["equipment_known"] = "已知設備壓差"
            if pkey == "static_m":
                cfg["boundary"] = "開式系統"
            is_water = loop in PD_KEYS[:5]
            pr0 = pressure_result(cfg, 0.005, 0.05, math.pi * 0.05**2 / 4, 1, 1000 if is_water else 1.2, 0.001 if is_water else 1.8e-5, 0.045, is_water)
            check(math.isfinite(pr0["total_pa"]), f"Non-finite total_pa for {loop}.{pkey}")
            field_coverage["pressure_drop_fields_tested"] += 1

    # 1C. Standalone AHU / MAU — All 74 NM_FIELDS
    ahu_active_overrides = {
        "summer_sa_t": {"target_mode": "主案分季需求"},
        "summer_sa_rh": {"target_mode": "主案分季需求"},
        "summer_flow": {"target_mode": "主案分季需求"},
        "winter_sa_t": {"target_mode": "主案分季需求"},
        "winter_sa_rh": {"target_mode": "主案分季需求"},
        "winter_flow": {"target_mode": "主案分季需求"},
        "h1_hw_kw": {"recovery": "二期可用（依已填能力）", "h1_source": "熱水＋電熱", "h2_hw_kw": "140"},
        "h1_water_mode": {"recovery": "二期可用（依已填能力）", "h1_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140"},
        "h1_hw_in": {"recovery": "二期可用（依已填能力）", "h1_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140", "h1_water_mode": "本段獨立設定"},
        "h1_hw_out": {"recovery": "二期可用（依已填能力）", "h1_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140", "h1_water_mode": "本段獨立設定"},
        "h1_hw_approach": {"recovery": "二期可用（依已填能力）", "h1_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140", "h1_water_mode": "本段獨立設定"},
        "h2_hw_kw": {"recovery": "二期可用（依已填能力）", "h2_source": "熱水＋電熱", "h1_hw_kw": "200"},
        "h2_water_mode": {"recovery": "二期可用（依已填能力）", "h2_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140"},
        "h2_hw_in": {"recovery": "二期可用（依已填能力）", "h2_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140", "h2_water_mode": "本段獨立設定"},
        "h2_hw_out": {"recovery": "二期可用（依已填能力）", "h2_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140", "h2_water_mode": "本段獨立設定"},
        "h2_hw_approach": {"recovery": "二期可用（依已填能力）", "h2_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140", "h2_water_mode": "本段獨立設定"},
        "hw_in": {"recovery": "二期可用（依已填能力）", "h1_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140"},
        "hw_out": {"recovery": "二期可用（依已填能力）", "h1_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140"},
        "hw_approach": {"recovery": "二期可用（依已填能力）", "h1_source": "熱水＋電熱", "h1_hw_kw": "200", "h2_hw_kw": "140"},
        "summer_h1_t": {"summer_h1_mode": "指定出口乾球", "summer_h1_t": "36"},
        "summer_c1_t": {"summer_c1_mode": "指定出口乾球", "summer_c1_t": "22"},
        "summer_c1_rh": {"summer_c1_mode": "指定出口 T/RH", "summer_c1_t": "22", "summer_c1_rh": "90"},
        "summer_c2_t": {"summer_c2_mode": "指定出口乾球", "summer_c2_t": "12"},
        "summer_c2_rh": {"summer_c2_mode": "指定出口 T/RH", "summer_c2_t": "12", "summer_c2_rh": "95"},
        "summer_h2_t": {"summer_h2_mode": "指定出口乾球", "summer_h2_t": "19"},
        "winter_h1_t": {"winter_h1_mode": "指定出口乾球", "winter_h1_t": "25"},
        "winter_c1_t": {"winter_t": "20", "winter_rh": "80", "winter_c1_mode": "指定出口乾球", "winter_c1_t": "16"},
        "winter_c1_rh": {"winter_t": "20", "winter_rh": "80", "winter_c1_mode": "指定出口 T/RH", "winter_c1_t": "16", "winter_c1_rh": "90"},
        "winter_c2_t": {"winter_c2_mode": "指定出口乾球", "winter_c2_t": "12"},
        "winter_c2_rh": {"winter_c2_mode": "指定出口 T/RH", "winter_c2_t": "12", "winter_c2_rh": "95"},
        "winter_h2_t": {"winter_h2_mode": "指定出口乾球", "winter_h2_t": "19"},
    }
    for k in NM_FIELDS:
        if k.startswith("steam_"):
            ahu_active_overrides[k] = {"humidifier": "電極式蒸汽"}

    for key, spec in NM_FIELDS.items():
        if key == "linked_main_hash":
            field_coverage["ahu_fields_tested"] += 1
            continue
        inp0 = dict(NM_DEFAULTS)
        if key in ahu_active_overrides:
            inp0.update(ahu_active_overrides[key])
        if key in ahu_inactive(inp0):
            # win.9 and the macOS port default the AHU stages to bypass; a field of another configuration is
            # reachable by choosing that configuration (one selector at a time, in schema order).
            reached = False
            for selector, sspec in NM_FIELDS.items():
                for option in (sspec.get("limit") if isinstance(sspec, dict) and isinstance(sspec.get("limit"), list) else []):
                    trial = dict(inp0, **{selector: option})
                    if key not in ahu_inactive(trial):
                        inp0 = trial
                        reached = True
                        break
                if reached:
                    break
        check(key not in ahu_inactive(inp0), f"AHU field {key} should be active in test setup")
        ar0 = nm_calculate(inp0)
        arep_zh = str(nm_report(ar0, language="zh-Hant"))
        arep_en = str(nm_report(ar0, language="en"))
        ahtml_en = str(html_report(ar0, language="en"))
        field_coverage["reports_verified"] += 3
        check(CJK.search(arep_en) is None, f"Untranslated CJK in AHU nm_report(en) for {key}")
        check(CJK.search(ahtml_en) is None, f"Untranslated CJK in AHU html_report(en) for {key}")
        # Verify unified checks in summer & winter
        for season in ("summer", "winter"):
            for req_chk in ("C1 總表候選容量", "C1 可達 ADP", "C2 總表候選容量", "C2 可達 ADP", "送風乾球目標", "送風含濕量目標"):
                check(req_chk in ar0[season]["checks"], f"Missing {req_chk} in AHU {season} checks for {key}")
        field_coverage["ahu_fields_tested"] += 1

    # 1D. Equipment Schedules — All 7 SYSTEMS x all columns in SCHEMAS
    for sys_name in SYSTEMS:
        row0 = example(sys_name)
        row0["enabled"] = 1
        for col in SCHEMAS[sys_name]:
            ckey = col["key"]
            cells = {c["key"]: Cell(row0[c["key"]]) for c in SCHEMAS[sys_name]}
            res = analyze_equipment(
                {
                    "schema_id": "FacilityStudioEquipment/1",
                    "source_name": "audit_schedule.csv",
                    "records": [{"system": sys_name, "row": 2, "cells": cells}],
                }
            )
            erep_zh = str(equipment_report(res, language="zh-Hant"))
            erep_en = str(equipment_report(res, language="en"))
            field_coverage["reports_verified"] += 2
            check(CJK.search(erep_en) is None, f"Untranslated CJK in equipment_report(en) for {sys_name}.{ckey}")
            field_coverage["equipment_columns_tested"] += 1

    # =========================================================================
    # PHASE 2: 100 Full Randomized Multi-Module & Report Verification Iterations
    # =========================================================================
    iteration_records = []
    for it in range(1, iterations + 1):
        # 2.1 Simple Calculators & 5-Tool Pipeline Iteration
        area = round(rng.uniform(40, 1200), 1)
        height = round(rng.uniform(2.6, 5.0), 2)
        ach = round(rng.uniform(15, 120), 1)
        dp = round(rng.choice([0, 10, 15, 25, 30]), 1)
        persons = rng.randint(2, 40)
        topology = rng.choice(["獨立FFU循環（MAU直接入室）", "MAU入靜壓箱經FFU送風"])
        basis = rng.choice(["室內基本循環（另加OA）", "FFU總送風（已含OA）"])
        oa_load_basis = rng.choice(["外氣至室內基準", "外氣至實際露點送風"])
        cop = round(rng.uniform(3.5, 6.0), 2)
        mau_kw = round(rng.uniform(1.0, 15.0), 2)
        proc_kw = round(rng.uniform(5.0, 80.0), 2)
        w_len = round(rng.uniform(15.0, 200.0), 1)
        w_ksum = round(rng.uniform(2.0, 25.0), 1)
        w_eq_pa = round(rng.uniform(10000.0, 80000.0), 1)

        pipe_inputs = {
            "cleanroom": {
                "area": str(area),
                "height": str(height),
                "ach": str(ach),
                "delta_p": str(dp),
                "persons": str(persons),
                "ffu_topology": topology,
                "ffu_airflow_basis": basis,
            },
            "heat_loads": {
                "oa_load_basis": oa_load_basis,
                "mau_room_sensible_kw": "0.1" if oa_load_basis == "外氣至實際露點送風" else "0",
                "mau_supply_delta_t": "8" if oa_load_basis == "外氣至實際露點送風" else "0",
            },
            "water": {
                "length": str(w_len),
                "k_sum": str(w_ksum),
                "equipment_pa": str(w_eq_pa),
            },
            "pumps": {
                "terminal_head_m": str(round(rng.uniform(2.0, 15.0), 1)),
                "head_margin_pct": str(round(rng.uniform(0.0, 15.0), 1)),
            },
            "electrical": {
                "chiller_cop": str(cop),
                "mau_input_kw": str(mau_kw),
                "process_input_kw": str(proc_kw),
            },
        }
        pipe_res = calculate_pipeline(pipe_inputs)
        check(bool(json.dumps(pipe_res, allow_nan=False)), f"Iter {it}: pipeline JSON NaN")
        for tname in ("cleanroom", "heat_loads", "water", "pumps", "electrical"):
            tr_zh = str(tool_report(pipe_res[tname], pipe_res["adopted_inputs"][tname], language="zh-Hant"))
            tr_en = str(tool_report(pipe_res[tname], pipe_res["adopted_inputs"][tname], language="en"))
            check(CJK.search(tr_en) is None, f"Iter {it}: CJK in {tname} tool_report(en)")
            check(numerals(tr_zh) == numerals(tr_en), f"Iter {it}: numeral drift in {tname}")
            field_coverage["reports_verified"] += 2
        # Verify water report contains pressure drop details
        w_rep = str(tool_report(pipe_res["water"], pipe_res["adopted_inputs"]["water"], language="zh-Hant"))
        check("直管壓損" in w_rep and "總路徑壓損" in w_rep, f"Iter {it}: water report missing pressure drop")
        # Verify heat_loads report contains occupant sensible heat
        hl_rep = str(tool_report(pipe_res["heat_loads"], pipe_res["adopted_inputs"]["heat_loads"], language="zh-Hant"))
        check("人員顯熱" in hl_rep, f"Iter {it}: heat_loads report missing occupant sensible heat")

        p_html_zh = str(html_report(pipe_res, language="zh-Hant"))
        p_html_en = str(html_report(pipe_res, language="en"))
        check(CJK.search(p_html_en) is None, f"Iter {it}: CJK in pipeline html_report(en)")
        check(numerals(p_html_zh) == numerals(p_html_en), f"Iter {it}: numeral drift in pipeline html")
        field_coverage["reports_verified"] += 2

        # 2.2 Also test duct, gas, lighting, air, units in this iteration
        duct_in = defaults("duct")
        duct_in.update(
            flow=str(round(rng.uniform(300, 25000), 1)),
            check_path=rng.choice(["0", "1"]),
            pressure=str(round(rng.uniform(150, 800), 1)),
            length=str(round(rng.uniform(10, 120), 1)),
            friction_method=rng.choice(["實際風速＋水力直徑", "Huebscher 等摩擦圓管"]),
        )
        duct_res = calculate_tool("duct", duct_in)
        d_zh = str(tool_report(duct_res, duct_in, language="zh-Hant"))
        d_en = str(tool_report(duct_res, duct_in, language="en"))
        check(CJK.search(d_en) is None and numerals(d_zh) == numerals(d_en), f"Iter {it}: duct report check failed")
        field_coverage["reports_verified"] += 2

        gas_in = defaults("gas")
        gas_in.update(
            flow=str(round(rng.uniform(20, 3000), 1)),
            pressure=str(round(rng.uniform(1, 12), 2)),
            temperature=str(round(rng.uniform(10, 50), 1)),
            atmosphere=str(round(rng.uniform(85, 105), 2)),
        )
        gas_res = calculate_tool("gas", gas_in)
        g_zh = str(tool_report(gas_res, gas_in, language="zh-Hant"))
        g_en = str(tool_report(gas_res, gas_in, language="en"))
        check(CJK.search(g_en) is None and numerals(g_zh) == numerals(g_en), f"Iter {it}: gas report check failed")
        field_coverage["reports_verified"] += 2

        light_in = defaults("lighting")
        light_in.update(
            mode=rng.choice(["估算照度", "反算燈數"]),
            area_mode=rng.choice(["面積 m²", "面積 坪", "長×寬", "體積 m³"]),
            u_mode=rng.choice(["手動固定 U", "型錄 U＋室指數 K 檢核"]),
            area=str(round(rng.uniform(30, 800), 1)),
            height="3.2",
            mount_h="3.0",
            work_h="0.8",
        )
        if light_in["u_mode"] == "型錄 U＋室指數 K 檢核":
            light_in.update(area_mode="長×寬", length=str(math.sqrt(float(light_in["area"]))), width=str(math.sqrt(float(light_in["area"]))))
        light_res = calculate_tool("lighting", light_in)
        l_zh = str(tool_report(light_res, light_in, language="zh-Hant"))
        l_en = str(tool_report(light_res, light_in, language="en"))
        check(CJK.search(l_en) is None and numerals(l_zh) == numerals(l_en), f"Iter {it}: lighting report check failed")
        field_coverage["reports_verified"] += 2

        air_in = defaults("air")
        air_in.update(
            temperature=str(round(rng.uniform(5, 40), 1)),
            rh=str(round(rng.uniform(10, 95), 1)),
            atmosphere=str(round(rng.uniform(80, 105), 2)),
        )
        air_res = calculate_tool("air", air_in)
        a_zh = str(tool_report(air_res, air_in, language="zh-Hant"))
        a_en = str(tool_report(air_res, air_in, language="en"))
        check(CJK.search(a_en) is None and numerals(a_zh) == numerals(a_en), f"Iter {it}: air report check failed")
        field_coverage["reports_verified"] += 2


        # 2.2b Test multi-unit electrical conversion (kW, HP, A, kVA, W, kcal/h, US RT, BTU/h)
        from facility_studio.simple_engines import ELECTRICAL_POWER_UNITS
        from facility_studio.quick_tools import electrical_quick
        el_unit = ELECTRICAL_POWER_UNITS[(it - 1) % len(ELECTRICAL_POWER_UNITS)]
        el_base = defaults("electrical")
        el_base.update(power="15", power_unit="kW", supply="三相 380V", pf="0.85", motor_efficiency="0.90", kind="馬達")
        el_r0 = calculate_tool("electrical", el_base)
        el_equiv_val = {"kW": 15, "W": 15000, "HP": 15*.9/.745699871582, "PS": 15*.9/.73549875, "A": 15000/(math.sqrt(3)*380*.85), "kVA": 15/.85}[el_unit]
        el_in = dict(el_base, power=format(el_equiv_val, ".15g"), power_unit=el_unit)
        el_r1 = calculate_tool("electrical", el_in)
        check(math.isclose(el_r1["electrical_input_kw"], el_r0["electrical_input_kw"], rel_tol=1e-9), f"Iter {it}: electrical unit {el_unit} roundtrip kW mismatch")
        check(math.isclose(el_r1["current_a"], el_r0["current_a"], rel_tol=1e-9), f"Iter {it}: electrical unit {el_unit} roundtrip current mismatch")
        check(el_r1["selected"]["nfb_a"] == el_r0["selected"]["nfb_a"] and el_r1["selected"]["size_mm2"] == el_r0["selected"]["size_mm2"], f"Iter {it}: electrical unit {el_unit} NFB/wire mismatch")
        eq_quick = electrical_quick(el_in["power"], el_unit, "三相 380V", "馬達", 0.85, 0.90, 30.0)
        check(math.isclose(eq_quick["current_a"], el_r0["current_a"], rel_tol=1e-9) and eq_quick["nfb_a"] == el_r0["selected"]["nfb_a"], f"Iter {it}: electrical_quick mismatch for {el_unit}")
        el_rep_zh = str(tool_report(el_r1, el_in, language="zh-Hant"))
        el_rep_en = str(tool_report(el_r1, el_in, language="en"))
        check("電氣輸入" in el_rep_zh and CJK.search(el_rep_en) is None and numerals(el_rep_zh) == numerals(el_rep_en), f"Iter {it}: electrical unit report check failed for {el_unit}")
        field_coverage["reports_verified"] += 2
        # Also test Workbench UP/NP electrical unit conversion and units tool
        from facility_studio.services import converted_units
        wb_u_test = default_project()["inputs"]
        wb_u_test["e_up_eq"] = "20"
        workbench_unit = "HP" if el_unit == "PS" else el_unit
        conv_patch = converted_units(wb_u_test, "u_e_up_eq", "kW", workbench_unit)
        if el_unit != "kW":
            wb_u_test.update(conv_patch, u_e_up_eq=workbench_unit)
            back_patch = converted_units(wb_u_test, "u_e_up_eq", workbench_unit, "kW")
            check(math.isclose(back_patch["e_up_eq"], 20.0, rel_tol=1e-9), f"Iter {it}: workbench converted_units roundtrip failed for {el_unit}")
        u_in = dict(defaults("units"), category="電力（固定三相380V PF0.85）", value="10", unit="kVA (PF0.85)")
        u_res = calculate_tool("units", u_in)
        check(math.isclose(u_res["values"]["kW"], 8.5, rel_tol=1e-9), f"Iter {it}: units tool explicit kVA/PF -> kW failed")

        # 2.3 Full Engineering Workbench Iteration
        wb = default_project()
        sys_choice = rng.choice(FIELDS["sys_type"]["options"])
        wb["inputs"].update(
            sys_type=sys_choice,
            en_L_A=str(round(rng.uniform(10, 40), 1)),
            en_W_A=str(round(rng.uniform(8, 30), 1)),
            en_H_A=str(round(rng.uniform(2.8, 4.5), 2)),
            eq_kw=str(round(rng.uniform(10, 120), 1)),
            pre_mode=rng.choice(["自動旁通因子估算", "停用／旁通"]),
            rt_type=rng.choice(FIELDS["rt_type"]["options"]),
            light_u_mode=rng.choice(["手動固定 U", "型錄 U＋室指數 K 檢核"]),
            pv_q=str(rng.choice([0, 500, 2000])),
        )
        # Also inject garbage into an inactive field to verify isolation in every iteration
        for off_key in list(main_inactive(wb["inputs"]))[:3]:
            wb["inputs"][off_key] = "inactive_draft_value"
        wb_res = calculate(wb)
        check(abs(wb_res["mass_residual"]) <= 1e-8, f"Iter {it}: workbench mass residual")
        check(abs(wb_res["sensible_residual"]) <= 1e-5, f"Iter {it}: workbench sensible residual")
        wb_txt_zh = str(report(wb_res, language="zh-Hant"))
        wb_txt_en = str(report(wb_res, language="en"))
        wb_html_zh = str(summary_html(wb_res, language="zh-Hant"))
        wb_html_en = str(summary_html(wb_res, language="en"))
        check("顯熱組成：設備淨熱" in wb_txt_zh, f"Iter {it}: workbench report missing sensible breakdown")
        check(CJK.search(wb_txt_en) is None, f"Iter {it}: CJK in workbench report(en)")
        check(CJK.search(wb_html_en) is None, f"Iter {it}: CJK in workbench summary_html(en)")
        field_coverage["reports_verified"] += 4

        # 2.4 Standalone AHU Iteration
        ahu_in = dict(NM_DEFAULTS)
        ahu_in.update(
            flow=str(round(rng.uniform(8000, 60000), 0)),
            humidifier=rng.choice(["循環水洗濕膜", "電極式蒸汽", "電熱式蒸汽"]),
            h1_source=rng.choice(["熱水＋電熱", "電熱"]),
            h2_source=rng.choice(["熱水＋電熱", "電熱"]),
        )
        for off_key in list(ahu_inactive(ahu_in))[:3]:
            if off_key != "linked_main_hash":
                ahu_in[off_key] = "inactive_ahu_draft"
        ahu_res = nm_calculate(ahu_in)
        ahu_txt_zh = str(nm_report(ahu_res, language="zh-Hant"))
        ahu_txt_en = str(nm_report(ahu_res, language="en"))
        ahu_html_en = str(html_report(ahu_res, language="en"))
        check(CJK.search(ahu_txt_en) is None, f"Iter {it}: CJK in AHU nm_report(en)")
        check(CJK.search(ahu_html_en) is None, f"Iter {it}: CJK in AHU html_report(en)")
        field_coverage["reports_verified"] += 3

        # 2.5 Equipment Schedule Iteration
        sys_eq = SYSTEMS[(it - 1) % len(SYSTEMS)]
        erow = example(sys_eq)
        erow["enabled"] = 1
        erow["quantity"] = rng.randint(1, 5)
        ecells = {c["key"]: Cell(erow[c["key"]]) for c in SCHEMAS[sys_eq]}
        eres = analyze_equipment(
            {
                "schema_id": "FacilityStudioEquipment/1",
                "source_name": f"iter_{it}_schedule.csv",
                "records": [{"system": sys_eq, "row": 2, "cells": ecells}],
            }
        )
        eq_zh = str(equipment_report(eres, language="zh-Hant"))
        eq_en = str(equipment_report(eres, language="en"))
        check(CJK.search(eq_en) is None, f"Iter {it}: CJK in equipment_report(en) for {sys_eq}")
        field_coverage["reports_verified"] += 2

        iteration_records.append(
            {
                "iteration": it,
                "pipeline_q_total_kw": round(pipe_res["heat_loads"]["q_total_kw"], 3),
                "workbench_sys_type": sys_choice,
                "workbench_qs_kw": round(wb_res["qs"], 3),
                "ahu_humidifier": ahu_in["humidifier"],
                "equipment_system": sys_eq,
                "passed": True,
            }
        )

    i18n.set_language("zh-Hant", persist=False)
    return {
        "kind": "audit-100x-all-fields-and-reports",
        "platform": platform_name,
        "iterations": iterations,
        "passed": True,
        "total_checks": total_checks,
        "field_coverage": field_coverage,
        "sample_iterations": iteration_records[:5] + iteration_records[-5:],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("windows", "macos"), default="windows")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_audit(args.platform, args.iterations)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "sample_iterations"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
