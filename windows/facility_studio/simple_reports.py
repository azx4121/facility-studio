from .i18n import localized_report

"""Short results shared by the independent forms and their exports."""

from .simple_schema import TOOLS


def presentation(result):
    tool = result["tool"]
    details = []
    if tool == "electrical":
        candidate = result["selected"]
        if candidate:
            cards = [
                ("NFB候選", f"{candidate['nfb_a']:g} AT"),
                ("每相銅線", f"{candidate['size_mm2']:g} mm² × {candidate['runs']}組"),
                ("運轉電流", f"{result['current_a']:,.2f} A"),
            ]
            details = [
                f"設計電流 {result['design_a']:,.2f}A ≤ NFB {candidate['nfb_a']:g}AT ≤ 有效載流 {candidate['ampacity_a']:,.2f}A",
                f"單程 {result['length_m']:g}m｜電壓降 {candidate['drop_v']:,.2f}V / {candidate['drop_pct']:.2f}%",
            ]
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
        details = [
            f"方管實際風速 {rect['velocity_mps']:.2f}m/s｜圓管 {round_duct['velocity_mps']:.2f}m/s｜上限 {result['velocity_limit']:g}m/s",
            f"可用管路靜壓 {result['pressure_pa']:,.1f}Pa",
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
        details = [
            f"標準流量 {result['standard_lpm']:,.2f} SLPM｜最低所需內徑 {result['minimum_id_mm']:.2f}mm",
            f"管內表壓 {result['gauge_kpa']/100:g}bar(g)｜絕對壓 {result['absolute_kpa']:.3f}kPa(abs)",
        ]
        if pipe:
            details.append(f"參考內徑 {pipe['id']:g}mm；內徑與材料依實供產品核對。")
    elif tool == "lighting":
        cards = [
            ("平均照度", f"{result['illuminance_lux']:,.1f} Lux"),
            ("燈具數量", f"{result['quantity']:,} 盞"),
            ("照明用電", f"{result['total_kw']:,.3f} kW"),
        ]
        details = [
            f"照明面積 {result['area_m2']:,.2f}m²｜每盞 {result['lumens_per_lamp']:,.0f}lm、{result['watts']:g}W",
            f"流明來源：{result['lumen_mode']}｜U={result['utilization']:g}，M={result['maintenance']:g}",
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
            f"乾球 {state['t']:g}°C｜濕度 {state['rh']:.2f}%RH",
            f"含濕比 {state['w']*1000:.3f}g/kg乾空氣｜比容 {state['v_da']:.4f}m³/kg乾空氣",
        ]
    else:
        rows = list(result["values"].items())
        cards = [(unit, f"{value:,.6g}") for unit, value in rows[:3]]
        details = [f"{value:,.10g} {unit}" for unit, value in rows]
    return cards, details


@localized_report
def tool_report(result, inputs):
    cards, details = presentation(result)
    from .simple_schema import active_field

    lines = [f"廠務簡易工具 5.5.5｜{TOOLS[result['tool']]['title']}", "", "輸入條件"]
    for row in TOOLS[result["tool"]]["fields"]:
        key = row["key"]
        if active_field(result["tool"], key, inputs):
            value = inputs[key]
            if row["checkbox"]:
                value = "是" if value == "1" else "否"
            if row["units"]:
                value += " " + inputs[row["units"][0]]
            lines.append(f"  {row['label']}：{value}")
    lines += ["", "結果"] + [f"  {label}：{value}" for label, value in cards]
    if result["tool"] == "lighting" and inputs["area_mode"] == "體積 m³":
        lines.append(
            f"  地板照明面積＝體積 {inputs['area']}m³ ÷ 淨高 {inputs['height']}m＝{result['area_m2']:,.3f}m²"
        )
    lines += ["  " + text for text in details]
    lines += ["", "公式", result["formula"], "", "採用範圍", result["note"]]
    return "\n".join(lines) + "\n"
