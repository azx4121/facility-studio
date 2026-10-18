from .i18n import localized_report

"""Short results shared by the independent forms and their exports."""

from .simple_schema import TOOLS
from .version import VERSION, REPORT_VERSION
from .gas_catalog import gas_label, CUSTOM_GAS
from .i18n import verbatim


def presentation(result):
    tool = result["tool"]
    details = []
    if tool == "cleanroom":
        cards = [
            ("FFU 需求台數", f"{result['ffu_count']:,} 台"),
            ("MAU 外氣量", f"{result['oa_cmh']:,.1f} CMH"),
            ("天花板覆蓋率", f"{result['coverage_ratio']:,.1f} %"),
        ]
        details = [
            f"室內容積 {result['volume_m3']:,.1f} m³｜基本循環 {result['recirculation_cmh']:,.1f} CMH｜配置上限 {result['coverage_limit_pct']:g} %",
            f"FFU 總設計風量 {result['ffu_total_cmh']:,.1f} CMH｜單台 {result['ffu_unit_cmh']:,.1f} CMH｜{result['ffu_size']}",
            f"DCC 循環回風 {result['dcc_cmh']:,.1f} CMH｜外氣 {result['oa_cmh']:,.1f} CMH",
            f"壓差洩漏 {result['leakage_cmh']:,.1f} CMH｜排氣 {result['exhaust_cmh']:,.1f} CMH",
            f"FFU 輸入電力／室內風機熱 {result['ffu_fan_kw']:,.2f} kW",
            "結構空間超限，請調整 FFU 尺寸、風量或天花板配置。" if result['coverage_exceeded'] else "覆蓋率未超過本案配置上限；仍須核對格柵與設備配置。",
        ]
        details.extend(result.get("warnings", []))
    elif tool == "heat_loads":
        cards = [
            ("主機總冷量", f"{result['q_total_rt']:,.2f} US RT"),
            ("DCC 顯熱需求", f"{result.get('q_dcc_kw', result['q_room_sensible_kw']):,.2f} kW"),
            ("MAU 外氣冷量", f"{result['q_mau_kw']:,.2f} kW"),
        ]
        details = [
            f"系統總冷量 {result['q_total_kw']:,.2f} kW｜{result['q_total_rt']:,.2f} US RT",
            f"照明 {result['q_lighting_kw']:,.2f} kW｜圍護 {result['q_envelope_kw']:,.2f} kW｜設備 {result['q_equipment_kw']:,.2f} kW",
            f"FFU 風機熱 {result['q_ffu_kw']:,.2f} kW｜人員顯熱 {result.get('q_people_sensible_kw', 0):,.2f} kW｜人員潛熱 {result['q_people_latent_kw']:,.2f} kW",
        ]
        if result.get("oa_load_basis") == "外氣至實際露點送風":
            details.append(
                f"MAU 顯熱抵扣 {result.get('mau_room_sensible_kw', 0):,.2f} kW｜抵扣上限 {result.get('mau_sensible_limit_kw', 0):,.2f} kW"
            )
        if result.get("load_basis"):
            details.append(result["load_basis"])
        details.extend(result.get("warnings", []))
    elif tool == "pumps":
        motor = result.get("recommended_motor_kw")
        cards = [
            ("建議馬達銘牌", f"{motor:,.2f} kW" if motor is not None else "超出內建級距"),
            ("設計揚程", f"{result['head_m']:,.2f} m"),
            ("設計流量", f"{result['flow_lpm']:,.2f} LPM"),
        ]
        details = [
            f"水功率 {result['hydraulic_power_kw']:,.3f} kW｜泵軸功率 {result['shaft_power_kw']:,.3f} kW｜馬達輸入 {result['motor_input_kw']:,.3f} kW",
            f"管路水頭 {result.get('path_head_m', result['head_m']):,.2f} m｜末端損失 {result.get('terminal_head_m', 0):,.2f} m｜靜揚程 {result.get('static_head_m', 0):,.2f} m｜揚程裕度 {result.get('head_margin_pct', 0):g} %",
            f"泵效率 {result['eta_pump']:.1%}｜馬達效率 {result['eta_motor']:.1%}｜馬達含裕度需求 {result.get('required_motor_kw', result['shaft_power_kw'] * 1.15):,.3f} kW",
            "馬達銘牌依軸功率加 15% 裕度，向上匹配內建級距；輸入電功率另計。",
        ]
        details.extend(result.get("warnings", []))
    elif tool == "electrical":
        candidate = result["selected"]
        if candidate:
            cards = [
                ("NFB候選", f"{candidate['nfb_a']:g} AT"),
                ("每相銅線", f"{candidate['size_mm2']:g} mm² × {candidate['runs']}組"),
                ("運轉電流", f"{result['current_a']:,.2f} A"),
            ]
            details = [
                f"電氣輸入 {result['power_kw']:,.3f} kW｜{result['power_w']:,.1f} W｜{result['apparent_kva']:,.2f} kVA",
                f"設計電流 {result['design_a']:,.2f}A ≤ NFB {candidate['nfb_a']:g}AT ≤ 有效載流 {candidate['ampacity_a']:,.2f}A",
                f"單程 {result['length_m']:g}m｜電壓降 {candidate['drop_v']:,.2f}V / {candidate['drop_pct']:.2f}%｜壓降上限 {result.get('drop_limit_pct', 3):g}%",
                f"銅線 {result.get('insulation', 'XLPE')}｜端子 {result['terminal_c']}°C｜環溫 {result.get('ambient_c', 35):g}°C（溫度係數 {result['dt']:.2f}）｜同管 {result.get('loaded_conductors', 3)}根（同管係數 {result['dp']:.2f}）",
            ]
            if "design_breaker_a" in result:
                motor = result.get("shaft_kw") is not None or result["kind"] == "馬達"
                basis = "馬達負載" if motor else "一般負載" if result["kind"] == "一般設備" else "連續負載"
                factor = 1.0 if basis == "一般負載" else 1.25
                details.append(f"設計電流依據：{basis}；運轉電流 {result['current_a']:,.4f} A × {factor:g}＝{result['design_a']:,.4f} A；馬達啟動、短路與保護協調另核。")
            if "electrical_input_kw" in result:
                details.append(f"有效輸入電功率 {result['electrical_input_kw']:,.3f} kW｜採用效率 {result.get('eta', 1):.3f}")
            if result.get("shaft_kw") is not None:
                details.append(f"馬達軸輸出 {result['shaft_kw']:,.3f} kW；馬達效率 η：{result['motor_efficiency']:g}")
        else:
            cards = [("NFB", "無需求"), ("線徑", "無需求"), ("電流", "0 A")]
    elif tool == "duct":
        rect, round_duct = result["rectangle"], result["round"]
        cards = [
            (
                "方管",
                (
                    f"{rect['w_mm']:g} × {rect['h_mm']:g} mm"
                    if result["flow_cmh"]
                    else "無需求"
                ),
            ),
            (
                "圓管",
                (
                    f"Ø {round_duct['diameter_m']*1000:,.1f} mm / {round_duct['round_in']:g}″"
                    if result["flow_cmh"]
                    else "無需求"
                ),
            ),
            ("設計風量", f"{result['flow_cmh']:,.1f} CMH"),
        ]
        k_val = result.get("k_sum") if result.get("k_sum") is not None else rect.get("k", 0)
        eq_val = result.get("equipment_input_pa") if result.get("equipment_input_pa") is not None else rect.get("equipment_pa", 0)
        rough_val = result.get("roughness_mm") if result.get("roughness_mm") is not None else rect.get("roughness_mm", 0.09)
        method_val = result.get("friction_method") or rect.get("friction_method", "實際風速＋水力直徑")
        details = [
            f"方管實際風速 {rect['velocity_mps']:.2f}m/s｜圓管 {round_duct['velocity_mps']:.2f}m/s｜上限 {result['velocity_limit']:g}m/s｜寬高比上限 {result['ratio']:g}",
            (
                f"可用管路靜壓 {result['pressure_pa']:,.1f}Pa｜直管長 {result['length_m']:g}m｜ΣK={k_val:g}｜設備壓降 {eq_val:,.1f}Pa｜粗糙度 {rough_val:g}mm｜{method_val}"
                if result["path_checked"]
                else "只計尺寸；未檢查靜壓，靜壓草稿未採用。"
            ),
        ]
        if result["path_checked"] and result["flow_cmh"]:
            for label, row in [("方管", rect), ("圓管", round_duct)]:
                state = "預算足夠" if row["budget_sufficient"] else "預算不足"
                details.append(
                    f"{label}路徑阻力 {row['loss_pa']:,.1f}Pa｜餘壓 {row['pressure_margin_pa']:,.1f}Pa｜{state}"
                )
        else:
            details.append("未核總路徑阻力，不把靜壓數字當成風管或風機已合格。")
    elif tool == "gas":
        pipe = result["pipe"]
        cards = [
            ("參考管徑", pipe["name"] if pipe else "無需求"),
            ("實際流量", f"{result['actual_lpm']:,.2f} ALPM"),
            ("管內流速", f"{result['velocity_mps']:.2f} m/s"),
        ]
        atm_kpa = result.get("atmosphere_kpa", result["absolute_kpa"] - result["gauge_kpa"])
        details = [
            f"標準流量 {result['standard_lpm']:,.2f} SLPM｜最低所需內徑 {result['minimum_id_mm']:.2f}mm｜流速上限 {result['velocity_limit']:g}m/s",
            f"管內表壓 {result['gauge_kpa']/100:g}bar(g)｜大氣壓 {atm_kpa:g}kPa(abs)｜絕對壓 {result['absolute_kpa']:.3f}kPa(abs)",
            f"管內溫度 {result['temperature_c']:g}°C｜標準參考 {result['reference_t']:g}°C、{result['reference_p']:g}kPa(abs)",
        ]
        label = gas_label(result["gas"], result.get("custom_name"))
        details.append("氣體：" + (verbatim(label) if result["gas"] == CUSTOM_GAS else label) + f"｜Z管內／Z標準 {result['z_ratio']:g}")
        if pipe:
            details.append(f"參考內徑 {pipe['id']:g}mm；內徑與材料依實供產品核對。")
    elif tool == "lighting":
        cards = [
            ("平均照度", f"{result['illuminance_lux']:,.1f} Lux"),
            ("燈具數量", f"{result['quantity']:,} 盞"),
            ("照明用電", f"{result['total_kw']:,.3f} kW"),
        ]
        u_detail = (
            f"室指數K={result['room_index_k']:.2f}；採用型錄U={result['utilization']:.4f}"
            if result.get("room_index_k") is not None
            else f"U={result['utilization']:g}"
        )
        details = [
            f"照明面積 {result['area_m2']:,.2f}m²｜每盞 {result['lumens_per_lamp']:,.0f}lm、{result['watts']:g}W",
            f"流明來源：{result['lumen_mode']}｜{u_detail}，M={result['maintenance']:g}",
        ]
        if result["target_lux"] is not None:
            details.append(
                f"目標 {result['target_lux']:g}Lux；盞數向上取整後採用上述平均照度。"
            )
    elif tool == "water":
        pipe, thermal = result["pipe"], result["thermal"]
        size = pipe["size"] + (f" × {pipe['runs']}並聯" if pipe["runs"] > 1 else "")
        cards = [
            ("循環水量", f"{thermal['lpm']:,.2f} LPM"),
            ("參考管徑", size),
            ("冷熱容量", f"{thermal['kw']:,.2f} kW"),
        ]
        details = [
            f"容量 {thermal['us_rt']:,.2f} US RT｜供回水溫差 {thermal['delta_t']:g}K",
            f"實際內徑 {pipe['id_mm']:g}mm｜每路水速 {pipe['velocity_mps']:.2f}m/s",
        ]
        if "pressure" in result:
            pr = result["pressure"]
            details.append(
                f"直管壓損 {pr['friction_pa_m']:,.2f}Pa/m｜總路徑壓損 {pr['loss_pa']:,.1f}Pa｜損失水頭 {pr['head_m']:,.2f}m｜直管長 {pr['length_m']:g}m｜ΣK={pr.get('k', pr.get('k_sum', 0)):g}｜設備壓降 {pr['equipment_pa']:,.1f}Pa｜粗糙度 {pr['roughness_mm']:g}mm"
            )
        if pipe.get("reference"):
            ref = pipe["reference"]
            details.append(f"採用碳鋼STD參考：外徑 {ref['outside_mm']:g}mm／壁厚 {ref['wall_mm']:g}mm；依實供管材核對。")
        details.extend(result.get("warnings", []))
    elif tool == "air":
        state = result["state"]
        dp = (
            f"{state['dewpoint_c']:.2f} °C"
            if state["dewpoint_c"] is not None
            else "無有限露點"
        )
        cards = [
            ("濕球溫度", f"{state['wetbulb_c']:.2f} °C"),
            ("露點溫度", dp),
            ("空氣焓值", f"{state['h']:.2f} kJ/kg乾空氣"),
        ]
        details = [
            f"乾球 {state['t']:g}°C｜濕度 {state['rh']:.2f}%RH｜大氣壓 {state['pressure_kpa']:g}kPa(abs)",
            f"含濕比 {state['w']*1000:.3f}g/kg乾空氣｜比容 {state['v_da']:.4f}m³/kg乾空氣",
        ]
    else:
        rows = list(result["values"].items())
        cards = [(unit, f"{value:,.6g}") for unit, value in rows[:3]]
        details = [f"{value:,.10g} {unit}" for unit, value in rows]
    return cards, details


def result_rows(result):
    """Stable four-column rows for the dashboard's detail Treeview."""
    cards, details = presentation(result)
    rows = [(label, value, "", "計算結果") for label, value in cards]
    rows.extend(("計算明細", value, "", "需求初估") for value in details)
    return rows


def input_rows(result, inputs=None):
    """Only supplied, active conditions; never invent a legacy result's inputs."""
    from .simple_schema import active_field, defaults, input_unit
    inputs = result.get("adopted_inputs", {}) if inputs is None else inputs
    if not isinstance(inputs, dict):
        return []
    tool = result["tool"]
    values = dict(defaults(tool), **inputs)
    rows = []
    for row in TOOLS[tool]["fields"]:
        key = row["key"]
        if key not in inputs or not active_field(tool, key, values):
            continue
        value = verbatim(values[key]) if key == "gas_name" else str(values[key])
        if row["checkbox"]:
            value = "是" if value == "1" else "否"
        unit = input_unit(tool, row, values)
        rows.append((row["label"], value + (" " + unit if unit else "")))
    return rows


def electrical_source_rows(pipeline):
    """Retain individual equipment inputs even when different splits sum alike."""
    known = {"FFU", "照明", "CHWP", "MAU", "製程設備", "Chiller"}
    return [(row["name"] if row["name"] in known else verbatim(row["name"]),
             f"{row['power_kw']:,.6f} kW", row["basis"])
            for row in pipeline.get("electrical_loads", [])]


def electrical_source_basis(pipeline):
    inputs = pipeline.get("adopted_inputs", {}).get("electrical", {})
    if float(inputs.get("chiller_input_kw", 0)):
        return "冰機用電依據：明填冰機輸入電功率。"
    cop = float(inputs.get("chiller_cop", 0))
    if cop and "Chiller" in {row["name"] for row in pipeline.get("electrical_loads", [])}:
        return f"冰機用電依據：冷量 {pipeline['heat_loads']['q_total_kw']:,.6f} kW ÷ COP {cop:g}。"
    return ""


@localized_report
def pipeline_report(result):
    from .reports import executive_summary_text

    lines = ["廠務跨模組設計摘要｜V" + REPORT_VERSION, "", executive_summary_text(result)]
    pipeline = result.get("pipeline", result)
    sources = electrical_source_rows(pipeline)
    if sources:
        lines += ["", "設備輸入用電來源"] + ["｜".join(row) for row in sources]
        lines.append(f"設備輸入電功率合計：{sum(row['power_kw'] for row in pipeline['electrical_loads']):,.6f} kW")
        if electrical_source_basis(pipeline):
            lines.append(electrical_source_basis(pipeline))
    for key, value in pipeline.items():
        if isinstance(value, dict) and value.get("tool"):
            cards, details = presentation(value)
            conditions = input_rows(value, pipeline.get("adopted_inputs", {}).get(key))
            lines += ["", key, "輸入條件"] + [label + "：" + text for label, text in conditions]
            if not conditions:
                lines.append("採用輸入條件未附於此結果，請附原始輸入資料。")
            lines += ["結果"] + [label + "：" + number for label, number in cards] + details
    if pipeline.get("warnings"):
        lines += ["", "需確認的條件"] + list(pipeline["warnings"])
    return "\n".join(lines) + "\n"


@localized_report
def tool_report(result, inputs):
    cards, details = presentation(result)
    from .simple_schema import active_field, defaults

    inputs = dict(defaults(result["tool"]), **inputs)

    lines = [f"廠務簡易工具 {REPORT_VERSION}｜{TOOLS[result['tool']]['title']}", "", "核心設計量"]
    lines += [f"  {label}：{value}" for label, value in cards]
    lines += ["", "輸入條件"]
    lines += [f"  {label}：{value}" for label, value in input_rows(result, inputs)]
    lines += ["", "結果"] + [f"  {label}：{value}" for label, value in cards]
    if result["tool"] == "lighting" and inputs["area_mode"] == "體積 m³":
        lines.append(
            f"  地板照明面積＝體積 {inputs['area']}m³ ÷ 淨高 {inputs['height']}m＝{result['area_m2']:,.3f}m²"
        )
    lines += ["  " + text for text in details]
    lines += ["", "公式", result["formula"], "", "採用範圍", result["note"]]
    return "\n".join(lines) + "\n"
