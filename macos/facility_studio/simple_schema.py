"""Short forms and clearly labelled reference values for independent tools."""

from .simple_engines import SUPPLIES
from .data import FFU_SIZES
from .gas_catalog import GAS_OPTIONS, CUSTOM_GAS, has_demand
from .quick_tools import UNITS


def field(
    key,
    label,
    default,
    *,
    options=(),
    advanced=False,
    units=None,
    help="",
    checkbox=False,
):
    return dict(
        key=key,
        label=label,
        default=str(default),
        options=tuple(options),
        advanced=advanced,
        units=units,
        help=help,
        checkbox=checkbox,
    )


TOOLS = {
    "electrical": dict(
        title="電力配線",
        subtitle="輸入設備kW，查看NFB候選、每相線徑與電流。",
        fields=[
            field("power", "設備用電功率", "10", help="kW，填電氣輸入功率"),
            field("supply", "供電方式", "三相 380V", options=SUPPLIES),
            field(
                "kind", "使用方式", "一般設備", options=("一般設備", "連續運轉", "馬達")
            ),
            field("pf", "功率因數 PF", ".85", advanced=True),
            field("eta", "效率 η（電氣輸入填1）", "1", advanced=True,
                  help="若設備kW是馬達軸輸出，填馬達效率如0.90；輸入電功率填1。"),
            field(
                "length",
                "單程配線距離",
                "30",
                advanced=True,
                help="m；壓降計算會自動處理相數",
            ),
            field(
                "insulation", "銅線絕緣", "XLPE", options=("XLPE", "PVC"), advanced=True
            ),
            field(
                "terminal",
                "設備端子溫度",
                "60",
                options=("60", "75", "90"),
                advanced=True,
                help="°C",
            ),
            field("ambient", "周圍溫度", "35", advanced=True, help="°C"),
            field("loaded", "同管載流導線數", "3", advanced=True),
            field("drop_limit", "允許電壓降", "3", advanced=True, help="%"),
            field("mau_input_kw", "帶入用：MAU輸入電功率", "0", advanced=True, help="kW；按帶入上游才加入設備合計"),
            field("process_input_kw", "帶入用：製程設備電功率", "0", advanced=True, help="kW；勿以室內熱負荷代替輸入電功率"),
            field("chiller_cop", "帶入用：冰機COP", "0", advanced=True, help="冷量kW/輸入kW；0表示尚未提供"),
            field("chiller_input_kw", "帶入用：冰機輸入電功率", "0", advanced=True, help="kW；有明填時優先於COP換算"),
        ],
    ),
    "duct": dict(
        title="風管尺寸",
        subtitle="先用風量定寸；需要檢查靜壓時，再啟用路徑壓力檢查。",
        fields=[
            field(
                "flow", "需要的風量", "3000", units=("flow_unit", ("CMH", "CFM", "L/s"))
            ),
            field(
                "pressure",
                "可用管路靜壓",
                "200",
                units=("pressure_unit", ("Pa", "mmAq", "kPa")),
            ),
            field(
                "velocity",
                "設計風速上限",
                "8",
                advanced=True,
                help="m/s；噪音與用途會影響取值",
            ),
            field("ratio", "方管寬高比上限", "2", advanced=True),
            field("friction_method", "摩擦壓損換算法", "實際風速＋水力直徑",
                  options=("實際風速＋水力直徑", "Huebscher 等摩擦圓管"), advanced=True),
            field("roughness_mm", "風管絕對粗糙度", "0.09", advanced=True, help="mm"),
            field(
                "check_path",
                "加做路徑靜壓檢查",
                "0",
                checkbox=True,
            ),
            field(
                "length",
                "最不利路徑直管長度",
                "20",
                advanced=True,
                help="m；此路徑各段視為相同尺寸",
            ),
            field(
                "k_sum",
                "管件阻力係數加總",
                "4",
                advanced=True,
                help="ΣK；依實際彎頭與管件確認",
            ),
            field(
                "equipment",
                "設備及末端壓降",
                "100",
                advanced=True,
                help="Pa；包含此路徑的濾網、風口等",
            ),
        ],
        units={"flow_unit": "CMH", "pressure_unit": "Pa"},
    ),
    "gas": dict(
        title="CDA／特氣管徑",
        subtitle="壓力填管內壓力表讀值；流量、壓力、流速一起決定管徑。",
        fields=[
            field("gas", "氣體", "CDA", options=GAS_OPTIONS, help="CDA（潔淨乾燥空氣）"),
            field("gas_name", "自訂氣體名稱／混合比例", "", help="例：5% H2／95% N2；請依供應商確認物性"),
            field("flow_basis", "流量資料基準", "標準流量", options=("標準流量", "管內實際流量"), help="SLPM/SCFM是標準量；銘牌只有L/min時須先確認。切換基準按目前溫壓等量換算，不會憑數字猜測。"),
            field(
                "flow",
                "所需標準流量",
                "800",
                units=("flow_unit", ("SLPM", "SCFM", "Sm³/h")),
                help="標準基準採25°C／101.325kPa(abs)，進階可調；實際量是目前管內溫壓下的体積量。",
            ),
            field(
                "pressure",
                "管內表壓",
                "6",
                units=("pressure_unit", ("bar(g)", "kPa(g)", "kgf/cm²(g)", "MPa(g)")),
            ),
            field(
                "velocity", "設計流速上限", "15", help="m/s；既有氣體保留初估值；新增氣體須填設計流速"
            ),
            field("z_ratio", "壓縮因子比 Z管內／Z標準", "1", advanced=True, help="0.1–3；1為理想氣體，請依供應商確認"),
            field("temperature", "管內氣體溫度", "25", advanced=True, help="°C"),
            field(
                "atmosphere", "所在地大氣壓", "101.325", advanced=True, help="kPa(abs)"
            ),
            field(
                "reference_t",
                "標準流量參考溫度",
                "25",
                advanced=True,
                help="°C，應與原廠流量基準一致",
            ),
            field(
                "reference_p",
                "標準流量參考壓力",
                "101.325",
                advanced=True,
                help="kPa(abs)",
            ),
        ],
        units={"flow_unit": "SLPM", "pressure_unit": "bar(g)"},
    ),
    "lighting": dict(
        title="照明照度",
        subtitle="填空間與燈具，估平均Lux；也可用目標Lux反算幾盞燈。",
        fields=[
            field("mode", "我要計算", "估算照度", options=("估算照度", "反算燈數")),
            field(
                "area_mode",
                "我手上的空間資料",
                "面積 m²",
                options=("面積 m²", "面積 坪", "長×寬", "體積 m³"),
            ),
            field("area", "空間面積", "30", help="依上方選擇，填m²、坪或m³"),
            field("length", "空間長度", "6", help="m"),
            field("width", "空間寬度", "5", help="m"),
            field(
                "height",
                "同一空間的淨高（m）",
                "3",
                help="只用來將m³換算為m²；請填同一空間的淨高。",
            ),
            field("watts", "每盞燈具功率", "40", help="W"),
            field("quantity", "已裝燈具數量", "10", help="盞"),
            field("target", "目標平均照度", "500", help="Lux"),
            field(
                "lumen_mode",
                "燈具流明來源",
                "LED功率初估",
                options=("LED功率初估", "燈具型錄流明"),
                advanced=True,
            ),
            field(
                "efficacy",
                "LED初估光效",
                "100",
                advanced=True,
                help="lm/W，初估假設，非燈具保證值",
            ),
            field(
                "lumens",
                "型錄每盞光通量",
                "4000",
                advanced=True,
                help="lm；燈具不是用Lux標示光通量",
            ),
            field("utilization", "照明利用率 U", ".6", advanced=True),
            field("maintenance", "維護係數 M", ".8", advanced=True),
        ],
    ),
    "water": dict(
        title="冷熱水快算",
        subtitle="已知水量或熱量，就能估管徑、水速、冷熱容量。",
        fields=[
            field("mode", "我已知道", "已知水量", options=("已知水量", "已知熱量")),
            field(
                "flow",
                "循環水量",
                "100",
                units=("flow_unit", ("LPM", "US GPM", "m³/h")),
            ),
            field("power", "冷熱負荷", "100", units=("power_unit", ("kW", "US RT"))),
            field("delta", "供回水溫差", "5", help="°C溫差"),
            field("velocity", "設計水速上限", "1.5", advanced=True, help="m/s"),
            field("length", "最不利路徑直管長度", "30", advanced=True, help="m"),
            field("k_sum", "管件阻力係數 ΣK", "4", advanced=True),
            field("equipment_pa", "設備及末端壓降", "0", advanced=True, help="Pa；0代表尚未納入設備"),
            field("roughness_mm", "水管絕對粗糙度", "0.045", advanced=True, help="mm"),
        ],
        units={"flow_unit": "LPM", "power_unit": "kW"},
    ),
    "air": dict(
        title="空氣狀態／線圖",
        subtitle="填乾球與濕度，數值及線圖點位即時更新；曲線依目前大氣壓計算。",
        fields=[
            field("temperature", "空氣乾球溫度", "25", help="°C"),
            field("rh", "相對濕度", "50", help="%RH"),
            field(
                "atmosphere", "所在地大氣壓", "101.325", advanced=True, help="kPa(abs)"
            ),
        ],
    ),
    "units": dict(
        title="單位換算",
        subtitle="選物理量、填數值與原單位，即可查看其他常用單位。",
        fields=[
            field("category", "要換算什麼", "風量", options=UNITS),
            field("value", "原數值", "1000"),
            field("unit", "原單位", "CMH", options=tuple(UNITS["風量"])),
        ],
    ),
}

TOOLS.update({
    "cleanroom": dict(title="潔淨室風量", subtitle="室內循環ACH、外氣與FFU設備分開計算，確認天花板可安裝量。", fields=[
        field("area", "室內地板面積", "100", help="m²"),
        field("height", "室內淨高", "3", help="m"),
        field("ffu_topology", "MAU／FFU氣流路徑", "MAU入靜壓箱經FFU送風", options=("獨立FFU循環（MAU直接入室）", "MAU入靜壓箱經FFU送風")),
        field("ffu_airflow_basis", "ACH／截面風量基準", "室內基本循環（另加OA）", options=("FFU總送風（已含OA）", "室內基本循環（另加OA）")),
        field("ach", "採用基準換氣次數", "60", help="1/h；依所選風量基準"),
        field("persons", "同時在室人數", "10", help="人"),
        field("exhaust_cmh", "製程及一般排氣合計", "0", help="CMH"),
        field("delta_p", "對低壓區設計壓差", "15", help="Pa；≤0時不估正壓外洩"),
        field("base_leak_ach", "15Pa基準洩漏換氣次數", "1", advanced=True, help="1/h；初估假設，非潔淨規範固定值"),
        field("oa_cmh", "指定OA（0為自動下限）", "0", advanced=True, help="CMH"),
        field("ffu_unit_cmh", "單台FFU額定風量", "1000", help="CMH"),
        field("ffu_size", "FFU名義尺寸", "1200x600 (0.72m²)", options=FFU_SIZES),
        field("ffu_unit_kw", "單台FFU輸入電功率", "0.18", help="kW；以原廠實際工況確認"),
        field("coverage_limit_pct", "天花板可安裝比例上限", "85", advanced=True, help="%"),
    ]),
    "heat_loads": dict(title="熱負荷初估", subtitle="分列室內顯熱、FFU發熱與MAU全熱，檢查外氣焓差的計算邊界。", fields=[
        field("area", "空間地板面積", "100", help="m²"),
        field("persons", "同時在室人數", "10", help="人"),
        field("equipment_kw", "設備入室顯熱", "20", help="kW；扣除密閉排氣及PCW已帶走部分"),
        field("lighting_w_m2", "照明功率密度", "12", help="W/m²"),
        field("envelope_w_m2", "圍護結構熱負荷密度", "20", help="W/m²；初估值"),
        field("people_sensible_w", "每人顯熱", "75", advanced=True, help="W/人"),
        field("people_latent_w", "每人潛熱", "55", advanced=True, help="W/人"),
        field("ffu_count", "FFU運轉台數", "0", help="台"),
        field("ffu_unit_kw", "單台FFU輸入電功率", "0.18", help="kW"),
        field("oa_cmh", "MAU設計外氣量", "0", help="CMH"),
        field("oa_delta_h", "外氣冷卻焓差", "50", help="kJ/kg；須配合下方控制體基準"),
        field("oa_load_basis", "外氣焓差終點", "外氣至室內基準", options=("外氣至室內基準", "外氣至實際露點送風"), advanced=True),
        field("mau_room_sensible_kw", "MAU入室顯熱供冷抵扣", "0", advanced=True, help="kW；僅實際露點模式；未填則總冷量採未抵扣上界"),
        field("mau_supply_delta_t", "室內減MAU送風溫差", "0", advanced=True, help="K；抵扣供冷時須明填，0代表未提供溫差"),
    ]),
    "pumps": dict(title="冰水泵浦", subtitle="水功率、軸功率與輸入電功率分列，依軸功率選馬達銘牌。", fields=[
        field("flow", "設計循環流量", "100", units=("flow_unit", ("LPM", "m³/h", "US GPM"))),
        field("head_m", "管路及已計設備損失揚程", "20", help="m"),
        field("terminal_head_m", "額外末端設備損失", "0", advanced=True, help="m；已在管路內計算者勿重加"),
        field("static_head_m", "開式系統靜揚程", "0", advanced=True, help="m；閉式循環填0"),
        field("head_margin_pct", "摩擦與設備損失裕度", "0", advanced=True, help="%"),
        field("eta_pump", "泵浦效率", "0.70", help="比例"),
        field("eta_motor", "馬達效率", "0.90", help="比例"),
    ], units={"flow_unit": "LPM"}),
})


def defaults(tool):
    spec = TOOLS[tool]
    return dict(
        {row["key"]: row["default"] for row in spec["fields"]}, **spec.get("units", {})
    )


def active_field(tool, key, data):
    if tool == "cleanroom" and key == "ffu_airflow_basis":
        return data.get("ffu_topology") == "MAU入靜壓箱經FFU送風"
    if tool == "heat_loads" and key in ("mau_room_sensible_kw", "mau_supply_delta_t"):
        return data.get("oa_load_basis") == "外氣至實際露點送風"
    if tool == "gas" and key == "gas_name":
        return data.get("gas") == CUSTOM_GAS and has_demand(data.get("flow", "0"))
    if tool == "lighting":
        conditions = {
            "quantity": data["mode"] == "估算照度",
            "target": data["mode"] == "反算燈數",
            "area": data["area_mode"] != "長×寬",
            "length": data["area_mode"] == "長×寬",
            "width": data["area_mode"] == "長×寬",
            "height": data["area_mode"] == "體積 m³",
            "efficacy": data["lumen_mode"] == "LED功率初估",
            "lumens": data["lumen_mode"] == "燈具型錄流明",
        }
        return conditions.get(key, True)
    if tool == "water":
        if key == "flow":
            return data["mode"] == "已知水量"
        if key == "power":
            return data["mode"] == "已知熱量"
    if tool == "duct" and key in ("pressure", "length", "k_sum", "equipment", "roughness_mm", "friction_method"):
        return data["check_path"] == "1"
    return True


def adopted_summary(tool, data):
    if tool == "cleanroom":
        topology = data.get('ffu_topology', 'MAU入靜壓箱經FFU送風')
        basis = data.get('ffu_airflow_basis', '室內基本循環（另加OA）') if topology == 'MAU入靜壓箱經FFU送風' else '獨立循環基準'
        return f"採用：{topology}｜{basis}｜15Pa基準洩漏{data['base_leak_ach']}ACH｜FFU {data['ffu_size']}｜安裝上限{data['coverage_limit_pct']}%"
    if tool == "heat_loads":
        return f"採用：中性供風初估｜外氣焓差{data['oa_delta_h']}kJ/kg（{data['oa_load_basis']}）｜FFU每台{data['ffu_unit_kw']}kW"
    if tool == "pumps":
        return f"採用：清水｜泵效率{data['eta_pump']}｜馬達效率{data['eta_motor']}｜馬達銘牌按軸功率加15%選級"
    if tool == "electrical":
        return f"採用：PF {data['pf']}｜銅線{data['insulation']}｜單程{data['length']}m｜環溫{data['ambient']}°C｜端子{data['terminal']}°C｜同管{data['loaded']}根｜壓降≤{data['drop_limit']}%"
    if tool == "duct":
        return f"採用：風速≤{data['velocity']}m/s｜寬高比≤{data['ratio']}｜方管50mm、圓管2英吋級距｜{'已啟用路徑阻力檢查' if data['check_path']=='1' else '僅定寸，靜壓是否足夠待路徑資料'}"
    if tool == "gas":
        return f"採用：{data.get('flow_basis', '標準流量')}｜管內{data['temperature']}°C｜標準流量{data['reference_t']}°C、{data['reference_p']}kPa(abs)｜Z管內／Z標準={data.get('z_ratio', '1')}"
    if tool == "lighting":
        source = (
            f"LED {data['efficacy']}lm/W初估"
            if data["lumen_mode"] == "LED功率初估"
            else f"型錄{data['lumens']}lm/盞"
        )
        return f"採用：{source}｜利用率U={data['utilization']}｜維護M={data['maintenance']}｜均勻一般照明初估"
    if tool == "water":
        return f"採用：水速≤{data['velocity']}m/s｜清水ρ=1000、cp=4.1868｜依實際參考內徑選型"
    if tool == "air":
        return f"採用：大氣壓{data['atmosphere']}kPa(abs)，以kg乾空氣為基準"
    return "溫度含零點位移；壓力換算保持原有表壓／絕對壓基準"
