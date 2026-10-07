"""Short forms and clearly labelled reference values for independent tools."""

from .simple_engines import SUPPLIES
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
            field("gas", "氣體", "CDA", options=("CDA", "N2", "Ar")),
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
                "velocity", "設計流速上限", "15", help="m/s；CDA初估15，N2／Ar初估12"
            ),
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


def defaults(tool):
    spec = TOOLS[tool]
    return dict(
        {row["key"]: row["default"] for row in spec["fields"]}, **spec.get("units", {})
    )


def active_field(tool, key, data):
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
    if tool == "duct" and key in ("pressure", "length", "k_sum", "equipment"):
        return data["check_path"] == "1"
    return True


def adopted_summary(tool, data):
    if tool == "electrical":
        return f"採用：PF {data['pf']}｜銅線{data['insulation']}｜單程{data['length']}m｜環溫{data['ambient']}°C｜端子{data['terminal']}°C｜同管{data['loaded']}根｜壓降≤{data['drop_limit']}%"
    if tool == "duct":
        return f"採用：風速≤{data['velocity']}m/s｜寬高比≤{data['ratio']}｜方管50mm、圓管2英吋級距｜{'已啟用路徑阻力檢查' if data['check_path']=='1' else '僅定寸，靜壓是否足夠待路徑資料'}"
    if tool == "gas":
        return f"採用：{data.get('flow_basis', '標準流量')}｜管內{data['temperature']}°C｜標準流量{data['reference_t']}°C、{data['reference_p']}kPa(abs)｜理想氣體Z=1"
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
