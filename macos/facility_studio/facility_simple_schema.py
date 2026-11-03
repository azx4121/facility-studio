"""Short-form additions; canonical values remain Traditional Chinese."""
from .facility_simple import MATERIALS, LIQUIDS


def install(tools, field):
    ins = [field("insulate", "計算管路保溫", "0", checkbox=True),
           field("ambient_t", "周圍空氣溫度", "30", help="°C"),
           field("ambient_rh", "周圍相對濕度", "75", help="%RH"),
           field("insulation_k", "保溫導熱係數", ".036", help="W/(m·K)；採材料平均使用溫度值"),
           field("external_h", "外表面綜合熱傳係數", "8", advanced=True, help="W/(m²·K)；含對流與輻射，依現場確認"),
           field("dew_margin", "防結露露點裕度", "1", advanced=True, help="K"),
           field("heat_limit", "每米允許熱損／得熱", "20", help="W/m；專案目標，非通用法規"),
           field("contract_insulation_mm", "契約最小保溫厚度", "0", help="mm；依實際適用規範填寫，0表示未指定")]
    tools["liquid"] = dict(title="液體／純水管路", subtitle="清水、純水、冷卻液及化學液體；明列材料、實際內徑、物性、壓損與保溫。",
        fields=[field("liquid", "輸送介質", "清水", options=LIQUIDS),
                field("material", "管路材質", "UPVC／PVC-U", options=MATERIALS),
                field("flow", "設計流量", "100", units=("flow_unit", ("LPM", "m³/h", "US GPM"))),
                field("liquid_t", "液體操作溫度", "20", help="°C"),
                field("liquid_p", "液體絕對壓力", "300", help="kPa(abs)；用於物性，不代表管材承壓通過"),
                field("concentration", "介質質量濃度", "20", help="%；乙／丙二醇水溶液模型採質量百分比"),
                field("properties", "物性來源", "依介質模型", options=("依介質模型", "供應商物性")),
                field("liquid_rho", "操作工況密度", "", help="kg/m³"),
                field("liquid_cp", "操作工況比熱", "", help="kJ/(kg·K)"),
                field("liquid_mu", "操作工況動力黏度", "", help="Pa·s；不是 cSt"),
                field("property_reference", "物性資料與適用條件", "", help="供應商／SDS／測試依據，註明濃度與溫度"),
                field("geometry", "管徑選擇方式", "外徑系列＋指定 SDR", options=("外徑系列＋指定 SDR", "指定外徑及管壁")),
                field("sdr", "採用管外徑／管壁 SDR", "17", help="純幾何初估，須依管材型錄確認"),
                field("outer_mm", "管路外徑", "25", help="mm；不可填公稱英吋值"),
                field("wall_mm", "最小實際管壁", "2", help="mm"),
                field("velocity", "本案流速警戒", "1.5", help="m/s；非所有化學液體通用安全流速"),
                field("friction_limit", "本案摩擦壓損警戒", "400", help="Pa/m"),
                field("roughness_mm", "管內絕對粗糙度", ".0015", advanced=True, help="mm；新塑膠管初估，依實際狀態修正"),
                field("length", "最不利路徑直管長", "30", help="m"),
                field("k_sum", "管件阻力係數總和", "4", advanced=True, help="ΣK")]+ins,
        units=dict(flow_unit="LPM"))
    tools["liquid"]["fields"] += [
        field("check_npsh", "加做泵浦吸入校核", "0", checkbox=True),
        field("suction_surface_kpa", "液槽表面絕對壓力", "101.325", help="kPa(abs)；開放槽填當地大氣壓，密閉槽填液面實際絕壓"),
        field("suction_level_m", "最低液面相對泵基準", "0", help="m；液面高於泵為正，低於泵為負"),
        field("suction_nozzle_offset_m", "吸入口相對泵基準高度", "0", help="m；相對原廠 NPSH 基準面，高於為正；不同基準不可混用"),
        field("suction_loss_kpa", "吸入側總壓損", "", help="kPa；含入口、吸入管、閥、濾器；非排出路徑，不能留空當零"),
        field("vapor_pressure_kpa", "同工況泡點壓力", "", help="kPa(abs)；化學液／混合液須提供，不能沿用純水值"),
        field("vapor_reference", "泡點壓力來源與工況", "", help="原廠或試驗資料；註明溫度及濃度"),
        field("npshr_m", "工況原廠 NPSHr", "", help="m；依泵型、流量與轉速曲線，空白保留待資料"),
        field("pump_curve_reference", "原廠泵曲線與工作點", "", help="型號、文件版次、流量及轉速；不自動視為原廠確認"),
        field("npsh_margin_m", "本案 NPSH 額外裕度", "", help="m；加在原廠 NPSHr 上，依原廠／業主確認"),
        field("npsh_margin_reference", "裕度採用依據", "", help="原廠／業主規範版次與工況；不預設通用裕度"),
    ]
    tools["vacuum"] = dict(title="PV 真空快算", subtitle="在此頁輸入標準流量與真空絕壓，完成實際流量、管徑、流速與抽速限制檢查。",
        fields=[field("flow", "標準氣體流量", "100", units=("flow_unit", ("SLPM", "SCFM", "Sm³/h")), help="下方明列標準狀態氣體量，不是管內實際量"),
                field("vacuum_p", "管內真空絕對壓力", "150", units=("vacuum_unit", ("Torr(abs)", "Pa(abs)", "kPa(abs)", "mbar(abs)"))),
                field("temperature", "氣體操作溫度", "20", help="°C；目前導通率僅空氣模型"),
                field("atmosphere", "所在地大氣絕壓", "101.325", advanced=True, help="kPa(abs)"),
                field("standard_t", "標準流量參考溫度", "0", advanced=True, help="°C"),
                field("standard_p", "標準流量參考絕壓", "101.325", advanced=True, help="kPa(abs)"),
                field("diameter_mode", "管徑模式", "依流速初估", options=("依流速初估", "指定內徑")),
                field("inner_mm", "實際管內徑", "50", help="mm"),
                field("velocity", "本案流速警戒", "15", help="m/s；分子流不得僅憑流速核准管徑"),
                field("length", "直管長度", "10", help="m；導通率模型不含彎頭及閥件"),
                field("pump_l_s", "工況泵入口抽速", "100", help="L/s；須採原廠工作壓力對應曲線")],
        units=dict(flow_unit="SLPM", vacuum_unit="Torr(abs)"))
    # Keep the existing heat/flow tool, add its own insulation calculation.
    tools["water"]["fields"] += ins
    tools["water"]["fields"].append(field("insulation_outer_mm", "保溫計算用實際管外徑", "", help="mm；無可信外徑表時須填實測，不能以內徑代替"))


def active(tool, key, data):
    if key in {"ambient_t", "ambient_rh", "insulation_k", "external_h", "dew_margin", "heat_limit", "contract_insulation_mm", "insulation_outer_mm"}:
        return data.get("insulate", "0") == "1"
    if tool == "liquid":
        if key in {"suction_surface_kpa", "suction_level_m", "suction_nozzle_offset_m", "suction_loss_kpa", "vapor_pressure_kpa", "vapor_reference", "npshr_m", "pump_curve_reference", "npsh_margin_m", "npsh_margin_reference"}:
            from .pump_suction import pure_fluid
            return data.get("check_npsh", "0") == "1" and (key not in {"vapor_pressure_kpa", "vapor_reference"} or pure_fluid(data, data.get("liquid")) is None)
        if key in {"liquid_rho", "liquid_cp", "liquid_mu", "property_reference"}:
            return data.get("properties") == "供應商物性" or data.get("liquid") not in LIQUIDS[:6]
        if key == "concentration":
            return data.get("liquid") not in ("清水", "UPW／DI／RO", "乙醇", "甲醇", "丙酮")
        if key == "sdr":
            return data.get("geometry") == "外徑系列＋指定 SDR"
        if key in {"outer_mm", "wall_mm"}:
            return data.get("geometry") == "指定外徑及管壁"
    if tool == "vacuum" and key == "inner_mm":
        return data.get("diameter_mode") == "指定內徑"
    return None
