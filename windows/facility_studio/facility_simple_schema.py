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
