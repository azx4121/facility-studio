"""One public equipment schedule schema shared by importers and templates."""

SCHEMA_ID = "FacilityStudioEquipment/1"
HEADER_ROW = 5
SYSTEMS = ("電力", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV")
DERIVED_HEADERS = {
    "計算_全開kW",
    "計算_同時kW",
    "計算_全開量(原單位)",
    "計算_同時量(原單位)",
}


def column(
    key,
    label,
    *,
    default=None,
    required=False,
    kind="number",
    low=0,
    high=100000000,
    options=(),
    help=""
):
    return dict(
        key=key,
        label=label,
        default=default,
        required=required,
        kind=kind,
        low=low,
        high=high,
        options=list(options),
        help=help,
    )


COMMON = [
    column(
        "enabled",
        "啟用(1/0)",
        required=True,
        kind="integer",
        high=1,
        help="1納入計算，0不納入。範例預設0。",
    ),
    column("id", "設備編號", kind="text", required=True, help="同一系統內不得重複。"),
    column("name", "設備名稱", kind="text", required=True),
    column(
        "group",
        "供應群組",
        kind="text",
        default="主系統",
        help="填配電盤或共用主管名稱。不同群組分開定寸。",
    ),
    column("quantity", "設備台數", kind="integer", default=1, low=1, high=1000000),
    column(
        "usage",
        "同時使用率(%)",
        default=100,
        high=100,
        help="瞬間同時需求的估算係數，填0~100；不是每小時運轉分鐘數。支路仍按額定負載。",
    ),
]
NOTES = column("notes", "備註", kind="text", default="")
FLOW = column("flow", "每台需求流量", required=True)
VELOCITY = lambda default: column(
    "velocity", "定寸流速上限(m/s)", default=default, low=0.1, high=40
)
WATER_UNIT = column(
    "unit",
    "流量單位",
    kind="choice",
    default="LPM",
    options=("LPM", "US GPM", "m³/h", "L/s"),
)
GAS_UNIT = column(
    "unit",
    "流量單位",
    kind="choice",
    default="SLPM",
    options=("SLPM", "SCFM", "Sm³/h", "ALPM"),
    help="S表示標準狀態流量；ALPM是下方管內溫壓的實際L/min。",
)
GAS_REFERENCE = [
    column("reference_t", "標準流量溫度(°C)", default=25, low=-60, high=60),
    column("reference_p", "標準流量絕壓(kPa)", default=101.325, low=60, high=120),
]
GAS_OPERATING = [
    column("pressure", "管內表壓", required=True),
    column(
        "pressure_unit",
        "壓力單位",
        kind="choice",
        default="bar(g)",
        options=("bar(g)", "kPa(g)", "kgf/cm²(g)", "MPa(g)"),
    ),
    column("temperature", "管內溫度(°C)", default=25, low=-60, high=150),
    column("atmosphere", "當地大氣壓(kPa絕壓)", default=101.325, low=60, high=120),
]

SCHEMAS = {
    "電力": COMMON
    + [
        column(
            "power",
            "每台輸入功率(kW)",
            required=True,
            high=1000000,
            help="電氣輸入kW；馬達軸輸出或HP需先換算並考慮效率。插座數不再乘功率。",
        ),
        column(
            "voltage",
            "供電電壓(V)",
            required=True,
            low=50,
            high=690,
            help="三相填線間電壓；單相填設備兩端電壓。不同供電方式分組，不直接合併電流。",
        ),
        column(
            "phases", "供電相數(1/3)", required=True, kind="choice", options=("1", "3")
        ),
        column("pf", "功率因數(PF)", default=0.85, low=0.1, high=1),
        column(
            "kind",
            "負載類型",
            kind="choice",
            default="一般設備",
            options=("一般設備", "連續運轉", "馬達"),
        ),
        column(
            "sockets",
            "每台所需插座數",
            kind="integer",
            default=0,
            high=10000,
            help="僅統計點位。每台功率已包含該設備需求，不再乘插座數。",
        ),
        column("length", "單程配線長度(m)", default=30, high=10000),
        NOTES,
    ],
    "PCW": COMMON
    + [
        FLOW,
        WATER_UNIT,
        column("delta", "供回水溫差(K)", default=5, low=0.1, high=100),
        VELOCITY(1.5),
        NOTES,
    ],
    "CDA": COMMON
    + [FLOW, GAS_UNIT, *GAS_OPERATING, VELOCITY(15), *GAS_REFERENCE, NOTES],
    "N2": COMMON
    + [FLOW, GAS_UNIT, *GAS_OPERATING, VELOCITY(12), *GAS_REFERENCE, NOTES],
    "EXHAUST": COMMON
    + [
        column(
            "exhaust_type",
            "排氣類型",
            kind="choice",
            default="GEX",
            options=("GEX", "SEX", "AEX", "VEX", "HEX"),
            help="一般／酸性／鹼性／有機／機台熱排分開彙總，不能自行混接。",
        ),
        FLOW,
        column(
            "unit",
            "流量單位",
            kind="choice",
            default="CMH",
            options=("CMH", "CFM", "L/s"),
        ),
        column(
            "pressure",
            "設備要求靜壓(Pa)",
            help="設備端要求，僅列最大值；不是全路徑風機ESP。未知填空白保留待資料。",
        ),
        VELOCITY(8),
        NOTES,
    ],
    "DI": COMMON
    + [
        FLOW,
        WATER_UNIT,
        column(
            "circulation",
            "每台額外循環量(LPM)",
            default=0,
            help="額外持續循環量不乘同時使用率。避免把已含循環的流量重複填入。",
        ),
        VELOCITY(1.2),
        NOTES,
    ],
    "PV": COMMON
    + [
        FLOW,
        GAS_UNIT,
        column("pressure", "管內絕對壓力", required=True, low=0.000001),
        column(
            "pressure_unit",
            "壓力單位",
            kind="choice",
            default="Torr(abs)",
            options=("Torr(abs)", "kPa(abs)", "mbar(abs)"),
        ),
        column("temperature", "管內溫度(°C)", default=25, low=-60, high=150),
        VELOCITY(18),
        *GAS_REFERENCE,
        NOTES,
    ],
}

EXAMPLES = {
    "電力": dict(
        id="EQ-001",
        name="製程設備範例",
        group="UP-01",
        power=10,
        voltage=380,
        phases="3",
        sockets=1,
    ),
    "PCW": dict(id="EQ-001", name="水冷機台範例", group="PCW-01", flow=30),
    "CDA": dict(id="EQ-001", name="氣動設備範例", group="CDA-01", flow=100, pressure=6),
    "N2": dict(id="EQ-001", name="氮氣設備範例", group="N2-01", flow=50, pressure=5),
    "EXHAUST": dict(
        id="EQ-001", name="排氣設備範例", group="EX-01", flow=500, pressure=200
    ),
    "DI": dict(id="EQ-001", name="洗滌設備範例", group="DI-01", flow=10, circulation=2),
    "PV": dict(id="EQ-001", name="真空設備範例", group="PV-01", flow=100, pressure=150),
}


def example(system):
    data = {c["key"]: c["default"] for c in SCHEMAS[system]}
    data.update(EXAMPLES[system], enabled=0)
    return data


def template_spec():
    return dict(
        schema_id=SCHEMA_ID,
        header_row=HEADER_ROW,
        systems=[dict(name=s, columns=SCHEMAS[s], example=example(s)) for s in SYSTEMS],
    )
