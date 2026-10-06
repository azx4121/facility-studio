import copy
from .data import CLEANROOM_DB, V31_DEFAULTS, VOLTAGE_MAP
from .utils import EXTRA_DEFAULTS, PD_DEFAULTS
from .utils import PD_DEFAULTS as BASE_PD_DEFAULTS

PD_DEFAULTS = dict(BASE_PD_DEFAULTS)
VERSION = "5.5.4"
SCHEMA_VERSION = 8
PAGES = [
    "總覽與空氣線圖",
    "空調與空間",
    "熱負荷與照明",
    "特氣與真空",
    "動力配電",
    "排氣風管",
    "水系統與純水",
    "壓損矩陣",
    "設計報告",
]
FIELDS = {}
GROUPS = []
DEFAULTS = dict(V31_DEFAULTS)
DEFAULTS.update({k: v for k, v in EXTRA_DEFAULTS.items() if k not in DEFAULTS})
DEFAULTS.update(
    {
        "project_name": "廠務設計試算",
        "pre_mode": "自動旁通因子估算",
        "mau_supply_t": "22",
        "ffu_cmh": "1000",
        "ffu_w": "0",
        "fcu_rt": "10",
        "chw1_dt": "5",
        "mchw_q": "160",
        "u_mchw": "LPM",
        "mchw_link": "連動負荷",
        "chw_link": "連動負荷",
        "dccw_link": "連動負荷",
        "pcw_link": "連動負荷",
        "hw_link": "獨立输入",
        "mode_A": "ACH",
        "mode_B": "ACH",
        "face_A": ".35",
        "face_B": ".35",
        "coverage_A": "1",
        "coverage_B": "1",
        "water_rho": "1000",
        "water_cp": "4.1868",
        "gas_min_barg": "5",
        "e_up_ground": "待核",
        "e_np_ground": "待核",
        "pre_mode": "自動旁通因子估算",
        "coil_approach": "1",
        "e_pipe": "3根以下 (標準)",
    }
)
DEFAULTS["hw_link"] = "獨立輸入"


def group(page, title, specs):
    keys = []
    for row in specs:
        key, label, unit, *rest = row
        opts = rest[0] if rest and isinstance(rest[0], (list, tuple)) else None
        low = rest[0] if rest and (not opts) else None
        high = rest[1] if len(rest) > 1 else None
        if key not in DEFAULTS:
            raise RuntimeError(key)
        FIELDS[key] = {
            "label": label,
            "unit": unit,
            "options": opts,
            "low": low,
            "high": high,
            "text": unit == "文字",
            "page": page,
        }
        keys.append(key)
    GROUPS.append((page, title, keys))


group(
    0,
    "專案與共同氣候（圖表／空調共用）",
    [
        ("project_name", "專案名稱", "文字"),
        ("atm_kpa", "大氣壓", "kPa", 60, 120),
        ("oa_t", "夏季外氣乾球", "°C", -40, 60),
        ("oa_rh", "夏季外氣相對濕度", "%RH", 0, 100),
        ("ra_t", "室內乾球", "°C", 5, 40),
        ("ra_rh", "室內相對濕度目標", "%RH", 1, 95),
        ("ow_t", "冬季外氣乾球", "°C", -40, 50),
        ("ow_rh", "冬季外氣相對濕度", "%RH", 0, 100),
    ],
)
group(
    1,
    "系統分工與設備",
    [
        (
            "sys_type",
            "空調系統",
            "",
            [
                "MAU+FFU+DCC (全外氣/無塵室)",
                "AHU (OA+RA 混合)",
                "FCU (風機盤管+外氣)",
                "RCU (機房空調箱+外氣)",
            ],
        ),
        (
            "rt_type",
            "冷凍噸基準",
            "",
            ["US RT (美制 3024 kcal/hr)", "JIS RT (日制 3320 kcal/hr)"],
        ),
        ("mau_supply_t", "MAU 最終送風溫度", "°C", 5, 40),
        ("en_dcc_rt", "單台 DCC 同工況顯熱能力", "RT", 0.1, 10000),
        ("en_rcu_rt", "單台 RCU 同工況冷量", "RT", 0.1, 10000),
        ("en_fcu_cmh", "單台 FCU 室內基準風量", "CMH", 1, 10000000.0),
        ("fcu_rt", "單台 FCU 同工況冷量", "RT", 0.1, 10000),
        ("ffu_cmh", "單台 FFU 室內基準風量", "CMH", 1, 10000000.0),
        ("ffu_w", "單台 FFU 入室發熱", "W", 0, 10000),
        ("sf", "容量安全餘裕", "%", 0, 100),
    ],
)
for z in ["A", "B"]:
    l = z.lower()
    group(
        1,
        z + " 區空間／循環需求",
        [
            (f"c_{l}", "潔淨等級（紀錄）", "", list(CLEANROOM_DB)),
            (f"mode_{z}", "風量計算模式", "", ["ACH", "截面風速"]),
            (f"en_L_{z}", "長度", "m", 0, 10000),
            (f"en_W_{z}", "寬度", "m", 0, 10000),
            (f"en_H_{z}", "淨高", "m", 0, 100),
            (f"en_ach_{z}", "換氣次數", "1/h", 0, 2000),
            (f"face_{z}", "有效送風面風速", "m/s", 0.01, 2),
            (f"coverage_{z}", "送風面積／地板面積", "比例", 0.01, 1),
            (f"en_p_{z}", "對共同低壓區壓差", "Pa", 0, 200),
            (f"ppl_{z}", "同時在室人數", "人", 0, 100000),
        ],
    )
group(
    1,
    "漏氣、排氣補充與人員外氣",
    [
        ("en_gap_L", "A 區門縫總長", "m", 0, 10000),
        ("en_gap_W", "A 區門縫寬", "m", 0, 1),
        ("en_door_A", "A 區單門面積", "m²", 0, 100),
        ("en_door_F", "A 區每小時開門次數", "1/h", 0, 360),
        ("gap_B_L", "B 區門縫總長", "m", 0, 10000),
        ("gap_B_W", "B 區門縫寬", "m", 0, 1),
        ("door_B_A", "B 區單門面積", "m²", 0, 100),
        ("door_B_F", "B 區每小時開門次數", "1/h", 0, 360),
        ("door_open_seconds", "每次開門時間", "s", 0, 3600),
        ("leak_cd", "漏氣流量係數", "比例", 0.1, 1),
        ("prd_q", "額外 PRD 洩壓量", "CMH", 0, 100000000.0),
        ("oa_per_person", "每人外氣設定", "CMH/人", 0, 200),
        ("en_manual_oa", "指定外氣，0 為自動", "室內基準 CMH", 0, 100000000.0),
        ("pv_room_fraction", "PV 從室內抽取比例", "比例", 0, 1),
    ],
)
group(
    1,
    "兩段盤管／再熱／加濕",
    [
        (
            "pre_mode",
            "一段盤管控制",
            "",
            ["自動旁通因子估算", "指定出口（需求檢核）", "停用／旁通"],
        ),
        ("chw1_in", "一段供水溫度", "°C", 0, 60),
        ("adp_approach", "一段 ADP 高於供水", "K", 0.1, 15),
        ("pre_t", "一段目標出口乾球", "°C", 0, 60),
        ("pre_rh", "指定一段出口相對濕度", "%RH", 1, 100),
        ("chw2_in", "二段供水溫度", "°C", 0, 30),
        ("coil_approach", "二段最低 ADP 高於供水", "K", 0.1, 15),
        ("allow_reheat", "允許加熱／再熱", "", ["1", "0"]),
        ("allow_humidify", "允許加濕", "", ["1", "0"]),
        ("dccw_in", "DCCW 供水溫度", "°C", 0, 50),
        ("dccw_dp_margin", "乾盤管露點安全裕度", "K", 0, 10),
    ],
)
group(
    2,
    "照度與燈具（啟動即計算）",
    [
        ("light_lux", "平均照度目標", "lux", 0, 100000),
        ("light_lm", "單盞光通量", "lm", 1, 10000000.0),
        ("light_w", "單盞輸入功率／入室熱", "W", 0, 1000000.0),
        ("light_u", "利用係數 U", "比例", 0.01, 1),
        ("light_m", "維護係數 M", "比例", 0.01, 1),
    ],
)
group(
    2,
    "設備散熱與製程產濕",
    [
        ("eq_kw", "同範圍設備總發熱", "kW", 0, 10000000.0),
        ("eq_rt", "設備運轉率", "%", 0, 100),
        ("exh_ratio", "運轉熱由排氣帶走比例", "%", 0, 100),
        ("pcw_n", "同工況 PCW 開機台數", "台", 0, 1000000.0),
        ("pcw_lpm", "單機 PCW 水量", "LPM", 0, 10000000.0),
        ("pcw_dt", "PCW 機台水溫差", "K", 0.01, 100),
        ("oven_kw", "其他未重複計入烤箱熱", "kW", 0, 10000000.0),
        ("process_latent_kw", "製程潛熱參考值", "kW", 0, 10000000.0),
        ("people_sensible_w", "人體顯熱", "W/人", 0, 1000),
        ("people_latent_w", "人體潛熱", "W/人", 0, 1000),
    ],
)
group(
    2,
    "圍護與其他入室熱",
    [
        ("en_wall", "外牆面積", "m²", 0, 100000000.0),
        ("wall_u", "外牆 U 值", "", 0, 100),
        ("en_floor", "樓板面積", "m²", 0, 100000000.0),
        ("floor_u", "樓板 U 值", "", 0, 100),
        ("u_unit", "U 值單位", "", ["kcal/(h·m²·K)", "W/(m²·K)"]),
        ("floor_adj_t", "樓板相鄰空間溫度", "°C", -40, 90),
        ("solar_kw", "日射入室熱", "kW", 0, 10000000.0),
        ("fan_room_kw", "其他未重複計入風機熱", "kW", 0, 10000000.0),
    ],
)
for j in (1, 2, 3):
    group(
        3,
        f"特氣 {j}",
        [
            (
                f"gas{j}_type",
                "氣體種類",
                "",
                ["N2", "CDA", "O2", "Ar", "He", "H2", "CO2", "GN2", "PN2"],
            ),
            (f"gas{j}_q", "標準體積流量", "", 0, 100000000.0),
            (f"u_gas{j}", "流量單位", "", ["SLPM", "SCFM", "CMH"]),
        ],
    )
group(
    3,
    "溫壓基準與真空",
    [
        ("gas_barg", "供氣表壓", "bar(g)", 0, 300),
        ("gas_min_barg", "定寸採用最低表壓", "bar(g)", 0, 300),
        ("gas_std_t", "標準體積參考溫度", "°C", -40, 60),
        ("gas_std_kpa", "標準體積參考絕壓", "kPa", 60, 120),
        ("gas_temp", "管內氣體溫度", "°C", -40, 100),
        ("gas_z_ratio", "Z_actual / Z_standard", "比例", 0.1, 3),
        ("pv_q", "PV 標準抽氣量", "", 0, 100000000.0),
        ("u_pv", "PV 流量單位", "", ["SLPM", "SCFM", "CMH"]),
        ("pv_torr", "PV 管內絕對壓力", "Torr(abs)", 1, 760),
        ("v_pv_mat", "真空管材（規格紀錄）", "文字"),
    ],
)
group(
    4,
    "電源、線材與候選排序",
    [
        ("e_volt", "三相線電壓", "", list(VOLTAGE_MAP)),
        ("e_pf", "等效功率因數", "比例", 0.1, 1),
        ("e_eff", "HP 換算的馬達效率", "比例", 0.1, 1),
        ("e_wire", "絕緣型式", "", ["XLPE 絕緣電纜 (90°C)", "PVC 一般電纜 (60°C)"]),
        (
            "e_temp",
            "環溫區間",
            "",
            ["35℃ 以下 (標準)", "36~40℃", "41~45℃", "46~50℃", "51~55℃"],
        ),
        (
            "e_pipe",
            "同管載流線數區間",
            "",
            [
                "3根以下 (標準)",
                "4根",
                "5~6根",
                "7~9根",
                "10~20根",
                "21~30根",
                "31~40根",
                "41根以上",
            ],
        ),
        ("e_terminal_c", "端子溫度額定", "°C", ["60", "75", "90"]),
        ("e_length_m", "單程配線長度", "m", 0, 10000),
        ("e_drop_limit_pct", "壓降上限", "%", 0.1, 20),
        ("e_sort", "合格候選排序", "", ["最少並聯組數", "最少總銅截面"]),
    ],
)
for panel, items in [
    ("up", [("eq", "設備"), ("oven", "烤箱")]),
    (
        "np",
        [
            ("fan", "風機"),
            ("heat", "加熱"),
            ("humid", "加濕"),
            ("exh", "排氣"),
            ("pump", "水泵"),
        ],
    ),
]:
    rows = [(f"e_{panel}_type", "負載類型", "", ["一般負載", "連續負載", "馬達負載"])]
    for key, title in items:
        rows.extend(
            [
                (f"e_{panel}_{key}", title + " 負荷", "", 0, 10000000.0),
                (f"u_e_{panel}_{key}", title + " 單位", "", ["A", "kW", "HP"]),
            ]
        )
    rows.extend(
        [
            (f"e_{panel}_largest_hp", "其中最大馬達（0 未知）", "HP", 0, 10000000.0),
            (f"e_{panel}_ground", "接地線工程覆核紀錄", "文字"),
        ]
    )
    group(4, panel.upper() + " 配電盤", rows)
for key, name in [
    ("gex", "一般"),
    ("sex", "酸性"),
    ("aex", "鹼性"),
    ("vex", "有機"),
    ("hex", "熱排"),
]:
    group(
        5,
        key.upper() + " " + name + "排氣",
        [
            (key + "_q", "名目風量", "", 0, 100000000.0),
            ("u_" + key, "風量單位", "", ["CMH", "CFM"]),
            ("v_" + key, "設計風速上限", "m/s", 0.1, 60),
        ],
    )
group(
    5,
    "風管共同條件",
    [
        ("duct_shape", "採用形狀", "", ["方管", "圓管"]),
        ("duct_ratio", "方管長寬比上限", "比例", 1, 4),
        ("exhaust_margin_pct", "排氣設計風量餘裕", "%", 0, 100),
        ("air_rho", "風管空氣密度", "kg/m³", 0.1, 5),
        ("air_mu", "風管空氣動力黏度", "Pa·s", 5e-06, 0.0001),
        ("duct_roughness_mm", "風管粗糙度", "mm", 0, 5),
    ],
)
for key, q, u, delta in [
    ("mchw", "mchw_q", "u_mchw", "chw1_dt"),
    ("chw", "chw_q", "u_chw", "dt_chw"),
    ("dccw", "dccw_q", "u_dccw", "dt_dccw"),
    ("pcw", "pcw_tot", "u_pcw_tot", "dt_pcw_sys"),
    ("hw", "hw_q", "u_hw", "dt_hw"),
]:
    group(
        6,
        key.upper() + " 水側負荷與水量",
        [
            (key + "_link", "水量來源", "", ["連動負荷", "獨立輸入"]),
            (q, "獨立輸入水量", "", 0, 100000000.0),
            (u, "水量單位", "", ["LPM", "GPM"]),
            (delta, "設計水溫差", "K", 0.01, 100),
        ],
    )
group(
    6,
    "水側物性（按實際流體修訂）",
    [
        ("water_rho", "密度", "kg/m³", 900, 1300),
        ("water_cp", "比熱", "kJ/(kg·K)", 2, 5),
        ("water_mu", "動力黏度", "Pa·s", 0.0001, 0.1),
        ("water_velocity_max", "水管流速上限", "m/s", 0.1, 10),
        ("water_roughness_mm", "水管粗糙度", "mm", 0, 5),
    ],
)
group(
    6,
    "純水循環與水質規格",
    [
        (
            "upw_type",
            "純水型式",
            "",
            ["UPW (超純水)", "DI (去離子水)", "RO (逆滲透水)"],
        ),
        ("upw_q", "循環流量", "LPM", 0, 100000000.0),
        ("upw_v", "流速限制", "m/s", 0.05, 10),
        ("upw_v_mode", "流速限制意義", "", ["最低維持流速", "最高允許流速"]),
        ("upw_mat", "管材規格", "文字"),
        ("upw_res", "電阻率／導電度", "文字"),
        ("upw_toc", "TOC 規格", "文字"),
        ("upw_do", "DO 規格", "文字"),
        ("upw_temp", "溫度規格", "文字"),
    ],
)
LEGACY_INPUT_KEYS = set(FIELDS)
DEFAULTS.update(
    {
        "latent_mode": "尚不清楚（暫不計製程）",
        "process_moisture_kg_h": "0",
        "pv_pressure_unit": "Torr(abs)",
        "upw_quality_mode": "自動參考值",
    }
)
group(
    2,
    "室內產濕／除濕需求",
    [
        (
            "latent_mode",
            "製程水氣資料",
            "",
            [
                "尚不清楚（暫不計製程）",
                "沒有額外產濕",
                "已知產濕量 kg/h",
                "已知潛熱 kW",
            ],
        ),
        ("process_moisture_kg_h", "額外進入室內的水氣", "kg/h", 0, 1000000.0),
    ],
)
group(
    3,
    "PV 顯示單位",
    [
        (
            "pv_pressure_unit",
            "PV 壓力單位（自動換算）",
            "",
            ["Torr(abs)", "kPa(abs)", "mbar(abs)"],
        )
    ],
)
group(
    6,
    "水質參考值來源",
    [("upw_quality_mode", "電阻率參考來源", "", ["自動參考值", "自訂規格"])],
)
for page, title, keys in GROUPS:
    if "process_latent_kw" in keys:
        keys.remove("process_latent_kw")
    if "latent_mode" in keys:
        keys.append("process_latent_kw")
    if "pv_torr" in keys:
        keys.insert(keys.index("pv_torr") + 1, "pv_pressure_unit")
    if title == "PV 顯示單位":
        keys.clear()
    if "upw_type" in keys:
        keys.insert(keys.index("upw_type") + 1, "upw_quality_mode")
    if title == "水質參考值來源":
        keys.clear()
FIELDS["process_latent_kw"]["label"] = "額外製程潛熱（不含人員／外氣）"
FIELDS["pv_torr"].update(
    label="PV 管內絕對壓力", unit="所選單位", low=1e-06, high=1000000.0
)
FIELDS["upw_res"]["label"] = "電阻率參考（25°C）"
DEFAULTS.update(
    {
        "upw_res": "18.2 MΩ·cm @25°C（參考目標）",
        "upw_toc": "依製程確認",
        "upw_do": "依製程確認",
    }
)
DEFAULTS = {k: str(DEFAULTS[k]) for k in FIELDS}
QUALITY_PRESETS = {
    "UPW (超純水)": "18.2 MΩ·cm @25°C（參考目標）",
    "DI (去離子水)": "≥ 1.0 MΩ·cm @25°C（初估參考）",
    "RO (逆滲透水)": "≥ 0.05 MΩ·cm @25°C（初估參考）",
}
BASIC_KEYS = set(
    "project_name oa_t oa_rh ra_t ra_rh ow_t ow_rh sys_type sf en_dcc_rt en_rcu_rt en_fcu_cmh fcu_rt ffu_cmh en_manual_oa chw1_in chw2_in dccw_in light_lux light_lm light_w eq_kw eq_rt exh_ratio pcw_n pcw_lpm pcw_dt oven_kw latent_mode process_moisture_kg_h process_latent_kw en_wall en_floor e_volt e_pf e_eff e_wire e_temp e_pipe e_length_m duct_shape upw_type upw_quality_mode upw_q upw_v upw_res pv_q u_pv pv_torr pv_pressure_unit gas_barg gas_min_barg".split()
)
for z in "AB":
    BASIC_KEYS.update(
        (
            "c_" + z.lower() if k == "class" else k + z
            for k in ["class", "en_L_", "en_W_", "en_H_", "en_ach_", "en_p_", "ppl_"]
        )
    )
for z in "AB":
    BASIC_KEYS.update(["mode_" + z, "face_" + z, "coverage_" + z])
for j in (1, 2, 3):
    BASIC_KEYS.update([f"gas{j}_type", f"gas{j}_q", f"u_gas{j}"])
for pan, keys in [
    ("up", ["eq", "oven"]),
    ("np", ["fan", "heat", "humid", "exh", "pump"]),
]:
    BASIC_KEYS.add(f"e_{pan}_type")
    for k in keys:
        BASIC_KEYS.update([f"e_{pan}_{k}", f"u_e_{pan}_{k}"])
for k in ["gex", "sex", "aex", "vex", "hex"]:
    BASIC_KEYS.update([k + "_q", "u_" + k])
for k, q, u, dt in [
    ("mchw", "mchw_q", "u_mchw", "chw1_dt"),
    ("chw", "chw_q", "u_chw", "dt_chw"),
    ("dccw", "dccw_q", "u_dccw", "dt_dccw"),
    ("pcw", "pcw_tot", "u_pcw_tot", "dt_pcw_sys"),
    ("hw", "hw_q", "u_hw", "dt_hw"),
]:
    BASIC_KEYS.update([k + "_link", q, u, dt])
REFERENCE_KEYS = set(
    "atm_kpa light_u light_m people_sensible_w people_latent_w water_rho water_cp water_mu water_velocity_max water_roughness_mm air_rho air_mu duct_roughness_mm v_gex v_sex v_aex v_vex v_hex duct_ratio exhaust_margin_pct gas_std_t gas_std_kpa gas_temp gas_z_ratio adp_approach coil_approach dccw_dp_margin leak_cd door_open_seconds oa_per_person".split()
)
FIELD_HELP = {
    "light_lux": "工作面平均照度；燈具數量會自動計算。",
    "eq_kw": "填設備總發熱，非一律把銘牌電力當成入室熱。",
    "pcw_n": "同時開機台數；水帶走的熱不可再次算入室內。",
    "pv_torr": "全部為絕對壓力；150 Torr ≈ 20.00 kPa ≈ 199.98 mbar。",
    "upw_res": "水型只提供初估參考，RO／DI 製法本身不保證此值。",
    "process_moisture_kg_h": "每小時實際散入室內的水；已由密閉排氣帶走的部分不要算入。",
    "process_latent_kw": "只填額外製程水氣負荷；人員與外氣已另外計算。",
}
PD_KEYS = ["MCHW", "CHW", "DCCW", "PCW", "HW", "GEX", "SEX", "AEX", "VEX", "HEX"]
PD_FIELDS = [
    ("length_m", "直管長度", "m"),
    ("elbows", "彎頭", "只"),
    ("tees", "三通", "只"),
    ("reducers", "大小頭", "只"),
    ("valves", "閥件", "只"),
    ("equipment_drop", "設備壓差", "指定單位"),
    ("unit", "壓差／阻力率單位", ["Pa", "kPa", "mmAq", "mH2O"]),
    ("mode", "計算方式", ["Darcy 自動", "手動阻力率"]),
    ("rate", "手動阻力率", "指定單位/m"),
    ("fitting_mode", "管件模式", ["等效長 L/D", "直接 K 值"]),
    ("sum_k", "管件 K 加總", ""),
    ("elbow_ld", "彎頭 L/D", ""),
    ("tee_ld", "三通 L/D", ""),
    ("reducer_ld", "大小頭 L/D", ""),
    ("valve_ld", "閥件 L/D", ""),
    ("manual_id_mm", "自訂圓管 ID，0 自動", "mm"),
    ("boundary", "系統邊界", ["閉式循環", "開式系統"]),
    ("static_m", "開式靜揚程", "m"),
    ("efficiency", "泵／風機效率", "比例"),
]
LEGACY_PD_KEYS = set(PD_DEFAULTS)
PD_DEFAULTS.update(
    estimate_mode="簡易估算", allowance_pct="30", equipment_known="尚無資料（不含設備）"
)
PD_FIELDS = [
    ("estimate_mode", "壓損計算方式", ["簡易估算", "詳細計算"]),
    ("allowance_pct", "管件等效長度餘裕", "%"),
    ("equipment_known", "設備壓差資料", ["尚無資料（不含設備）", "已知設備壓差"]),
] + PD_FIELDS
_pd_order = [
    "estimate_mode",
    "length_m",
    "allowance_pct",
    "equipment_known",
    "equipment_drop",
    "unit",
    "boundary",
    "static_m",
]
PD_FIELDS = sorted(
    PD_FIELDS,
    key=lambda f: (
        _pd_order.index(f[0])
        if f[0] in _pd_order
        else len(_pd_order) + [x[0] for x in PD_FIELDS].index(f[0])
    ),
)


def default_project():
    pd = {k: copy.deepcopy(PD_DEFAULTS) for k in PD_KEYS}
    for k in PD_KEYS:
        pd[k].update(equipment_drop="0")
    for k in PD_KEYS[5:]:
        pd[k].update(unit="Pa", boundary="開式系統")
    return {
        "schema_version": SCHEMA_VERSION,
        "inputs": copy.deepcopy(DEFAULTS),
        "pressure_drop": pd,
        "provenance": {
            k: {"source": "系統預設", "note": "初估起點；依現場確認"} for k in FIELDS
        },
    }


V52_INPUT_KEYS = set(FIELDS)
for j in (1, 2, 3):
    DEFAULTS.update(
        {
            f"gas{j}_pressure_mode": "共用最低壓力",
            f"gas{j}_barg": "5",
            f"gas{j}_v_mode": "依氣體參考",
            f"gas{j}_velocity": "12",
        }
    )
    group(
        3,
        f"特氣 {j}｜進階定寸條件",
        [
            (
                f"gas{j}_pressure_mode",
                "管內壓力來源",
                "",
                ["共用最低壓力", "本路管內壓力"],
            ),
            (f"gas{j}_barg", "本路定寸管內表壓", "bar(g)", 0, 300),
            (f"gas{j}_v_mode", "設計流速來源", "", ["依氣體參考", "自訂流速"]),
            (f"gas{j}_velocity", "本路自訂流速上限（自訂時生效）", "m/s", 0.1, 100),
        ],
    )
DEFAULTS["pv_velocity"] = "18"
group(3, "PV｜進階定寸條件", [("pv_velocity", "PV 設計流速上限", "m/s", 0.1, 100)])
FIELD_HELP.update(
    {
        "gas_min_barg": "共用的定寸最低管內表壓。各路進階可改本路值；不是已完成壓降反算。",
        "gas_barg": "共同供氣源表壓。各路管內定寸表壓不得高於此值。",
    }
)
V53_INPUT_KEYS = set(FIELDS)
DEFAULTS.update(
    dcc_airflow_mode="沿用 FFU 循環", dcc_airflow_cmh="0", dcc_air_approach="1"
)
group(
    1,
    "DCC 空氣側可達條件",
    [
        (
            "dcc_airflow_mode",
            "DCC 循環風量來源",
            "",
            ["沿用 FFU 循環", "獨立 DCC 循環"],
        ),
        ("dcc_airflow_cmh", "DCC 獨立循環風量", "室內基準 CMH", 0, 100000000.0),
        ("dcc_air_approach", "出風高於供水的最小溫差", "K", 0.1, 15),
    ],
)
BASIC_KEYS.update({"dcc_airflow_mode", "dcc_airflow_cmh"})
DEFAULTS.update(
    project_name="一般廠房初估範例",
    sys_type="AHU (OA+RA 混合)",
    en_L_A="20",
    en_W_A="15",
    en_H_A="4",
    en_ach_A="8",
    ppl_A="20",
    eq_kw="40",
    eq_rt="80",
    pcw_n="0",
    exh_ratio="0",
    en_wall="280",
    en_floor="300",
    c_a="無 (None)",
    en_p_A="0",
    en_gap_L="0",
    en_door_F="0",
    prd_q="0",
    gas1_q="0",
    gas2_q="0",
    pv_q="0",
    upw_q="0",
    latent_mode="沒有額外產濕",
    light_lux="500",
    hw_link="連動負荷",
)
PV_HVAC_KEYS = {
    "pv_q",
    "u_pv",
    "gas_std_kpa",
    "gas_std_t",
    "atm_kpa",
    "pv_room_fraction",
}
UTILITY_ONLY_KEYS = {
    k
    for k, f in FIELDS.items()
    if f["page"] == 4 or (f["page"] == 3 and k not in PV_HVAC_KEYS)
}

# V5.5.1: winter uses explicit room gains; legacy files keep their former boundary.
V54_INPUT_KEYS = set(FIELDS)
SCHEMA_VERSION = 9
DEFAULTS.update(
    winter_model="室內熱濕平衡（定風量）",
    winter_floor_adj_t="22",
    winter_gain_ratio="100",
    winter_moisture_ratio="100",
    winter_solar_kw="0",
)
group(
    1,
    "冬季設計邊界",
    [
        (
            "winter_model",
            "冬季計算範圍",
            "",
            ["室內熱濕平衡（定風量）", "外氣處理基準（舊版）"],
        ),
        ("winter_floor_adj_t", "冬季樓板相鄰溫度", "°C", -40, 60),
        ("winter_gain_ratio", "冬季室內顯熱來源比例", "% 夏季內部得熱", 0, 200),
        ("winter_moisture_ratio", "冬季室內產濕比例", "% 夏季產濕", 0, 200),
        ("winter_solar_kw", "冬季另計日射／其他顯熱", "kW", 0, 1e6),
    ],
)
BASIC_KEYS.add("winter_model")
FIELD_HELP["winter_model"] = (
    "室內模式以明列得熱、外牆、樓板與產濕作穩態收支；沿用夏季設計風量。並非逐時建築負荷或多室模型。"
)
