"""Independent single-MAU design review, integrated into the desktop application.
Demand states are not a simulation of under-capacity installed equipment.
"""

NM_GROUPS = []
NM_FIELDS = {}
NM_DEFAULTS = {}


def nm_group(title, rows):
    keys = []
    for key, label, default, unit, limit in rows:
        NM_DEFAULTS[key] = str(default)
        NM_FIELDS[key] = {"label": label, "unit": unit, "limit": limit}
        keys.append(key)
    NM_GROUPS.append((title, keys))


nm_group(
    "1｜通用單機邊界（送風目標，不等於室內負荷平衡）",
    [
        ("name", "專案名稱", "分段空調箱設計範例", "文字", None),
        ("flow", "指定風量", 58000, "CMH", (1, 10000000.0)),
        (
            "flow_basis",
            "風量所在狀態",
            "送風狀態（待核對）",
            "",
            ["送風狀態（待核對）", "各季外氣入口狀態"],
        ),
        ("p", "大氣絕壓", 101.325, "kPa", (60, 120)),
        ("summer_t", "夏季外氣乾球", 35, "°C", (-30, 60)),
        ("summer_rh", "夏季外氣濕度", 70, "%RH", (0, 100)),
        ("winter_t", "冬季外氣乾球", 5, "°C", (-30, 50)),
        ("winter_rh", "冬季外氣濕度", 40, "%RH", (0, 100)),
        ("sa_t", "單機送風目標乾球", 22, "°C", (5, 40)),
        ("sa_rh", "單機送風目標濕度", 55, "%RH", (5, 95)),
    ],
)
nm_group(
    "2｜段落與加熱源（保留實體電熱器）",
    [
        ("sequence", "H1／C1 位置", "H1 → C1", "", ["H1 → C1", "C1 → H1（比較方案）"]),
        (
            "h1_order",
            "H1 內部相對位置",
            "電熱 → 熱水",
            "",
            ["電熱 → 熱水", "熱水 → 電熱"],
        ),
        (
            "h2_order",
            "H2 內部相對位置",
            "熱水 → 電熱",
            "",
            ["熱水 → 電熱", "電熱 → 熱水"],
        ),
        ("h1_kw", "H1 已配置電熱器", 400, "kW", (0, 10000)),
        ("h2_kw", "H2 已配置電熱器", 200, "kW", (0, 10000)),
        ("heat_eta", "電熱入空氣效率", 1, "比例", (0.5, 1)),
        (
            "recovery",
            "熱回收可用情境",
            "一期未上線",
            "",
            ["一期未上線", "二期可用（依已填能力）"],
        ),
        ("hw_in", "回收熱水供水", 30, "°C", (5, 95)),
        ("hw_out", "回收熱水回水", 24, "°C", (1, 90)),
        ("hw_approach", "熱水盤管最小端差初估", 2, "K", (0.1, 15)),
        ("h1_hw_kw", "H1 廠商同工況熱水能力，0 待提供", 0, "kW", (0, 10000)),
        ("h2_hw_kw", "H2 廠商同工況熱水能力，0 待提供", 0, "kW", (0, 10000)),
    ],
)
nm_group(
    "3｜預冷 C1 與再冷 C2",
    [
        ("c1_in", "C1 冰水供水", 14, "°C", (0, 40)),
        ("c1_out", "C1 冰水回水", 19, "°C", (1, 50)),
        ("c1_adp", "C1 ADP 高於供水", 1, "K", (0.1, 15)),
        ("c1_t", "C1 夏季自動模式出口目標", 22, "°C", (5, 45)),
        ("c1_rt", "C1 總表候選容量（待正本確認）", 250, "US RT", (0, 10000)),
        ("c2_in", "C2 冰水供水", 7, "°C", (0, 30)),
        ("c2_out", "C2 冰水回水", 12, "°C", (1, 40)),
        ("c2_adp", "C2 最低 ADP 高於供水", 1, "K", (0.1, 15)),
        ("c2_rt", "C2 總表候選容量（待正本確認）", 160, "US RT", (0, 10000)),
        ("sf", "需求容量餘裕", 0, "%", (0, 100)),
    ],
)
nm_group(
    "4｜循環水洗濕膜（不視為蒸汽加濕）",
    [
        (
            "wash_mode",
            "水洗運轉方式",
            "AMC 需求持續水洗",
            "",
            ["AMC 需求持續水洗", "只在需要加濕時", "旁通／停用"],
        ),
        ("wash_eff", "濕膜有效度（初估，待廠商提供）", 0.85, "比例", (0.05, 1)),
        ("wash_rating", "總表加濕能力（轉述，待正本核對）", 619.4, "kg/h", (0, 100000)),
        ("media_area", "廠商有效淋水面積，0 待提供", 0, "m²", (0, 1000)),
        ("wetting_rate", "廠商單位面積循環水量，0 待提供", 0, "LPM/m²", (0, 10000)),
        ("spray_head", "廠商噴頭壓力水頭，0 待提供", 0, "m", (0, 200)),
        ("spray_rise", "水面至噴頭高差，0 待提供", 0, "m", (0, 100)),
        ("loop_loss", "循環管路／濾網損失，0 待提供", 0, "m", (0, 200)),
        ("drift_lph", "另計飛水／排污用水預留", 0, "L/h", (0, 100000.0)),
    ],
)
nm_group(
    "5｜EC 風機、濾網與設備壓差",
    [
        ("fan_qty", "EC 風機配置台數", 8, "台", (1, 100)),
        ("fan_unit_kw", "單台額定電力（轉述，待型錄確認）", 7.8, "kW", (0, 1000)),
        ("fan_air_kw", "實際進入氣流的風機熱，0 待核", 0, "kW", (0, 1000)),
        (
            "dp_status",
            "空氣側壓差資料",
            "尚未完整提供",
            "",
            ["尚未完整提供", "已填完整同風量資料"],
        ),
        ("dp_filter", "初／中效濾網終阻力", 0, "Pa", (0, 10000)),
        ("dp_h1", "H1 兩加熱元件阻力合計", 0, "Pa", (0, 10000)),
        ("dp_c1", "C1 盤管阻力", 0, "Pa", (0, 10000)),
        ("dp_wash", "水洗膜／擋水器阻力合計", 0, "Pa", (0, 10000)),
        ("dp_c2", "C2 盤管阻力", 0, "Pa", (0, 10000)),
        ("dp_h2", "H2 兩加熱元件阻力合計", 0, "Pa", (0, 10000)),
        ("dp_hepa", "PTFE HEPA 終阻力", 0, "Pa", (0, 10000)),
        ("dp_external", "機外需求靜壓及其他阻力", 0, "Pa", (0, 10000)),
        ("fan_eff", "風機總效率（試算）", 0.65, "比例", (0.1, 1)),
    ],
)
NM_BASIC = set(
    "name flow flow_basis summer_t summer_rh winter_t winter_rh sa_t sa_rh h1_kw h2_kw recovery hw_in hw_out h1_hw_kw h2_hw_kw c1_in c1_out c1_t c1_rt c2_in c2_out c2_rt wash_mode wash_eff wash_rating fan_qty fan_unit_kw fan_air_kw dp_status".split()
)
NM_CONTROL_NOTES = "控制與量測規劃（供圖審；非 PLC 可執行程式）\n1. OA：量測外氣 T/RH；模式依含濕量需求切換，不只按日曆季節。\n2. H1：配置進／出風 T；預熱目標由水洗需求反算。一般加濕模式使 C1 旁通，避免預熱後又不必要預冷；防凍需求需另訂例外。\n3. 水洗：出口 T/RH、循環水流量／泵回訊、水槽高／低／極低液位。加濕需求與 AMC 持續洗滌需求分開；AMC 效率依污染物及原廠資料，程式不保證去除率。\n4. 水槽：低位補水、高位停止；極低位停循環泵；排水／清洗期間依供應商程序停泵並聯鎖補排水，避免乾轉或邊排邊補失控。水質／換水門檻由 RO 與洗滌水管理規格決定。\n5. C2：盤管後、再熱前量測 T/RH 或露點。真實盤管出口未必飽和，不可一律把乾球當露點。\n6. H2／EC：風機後送風 T 作再熱修正，納入實際風機熱；H1/H2 電熱均需風量證明、獨立過溫切斷及必要延時散熱，不能只靠軟體訊號。\n7. 濾網／濕膜：依實際元件配置壓差量測；濕膜與擋水器功能不可直接互相替代。末端／風管壓力控制須與最低通風、風機轉速限制協調。\n8. 8 台 EC 各自故障／運轉回訊及適當保護；一台停機後能否維持風量，需 N−1 工況風機曲線，不能由台數自動保證。"
AHU_OPTIONAL_NUMBERS = {"spray_head", "spray_rise", "loop_loss"} | {
    k for k in NM_DEFAULTS if k.startswith("dp_") and k != "dp_status"
}
for k in AHU_OPTIONAL_NUMBERS:
    NM_DEFAULTS[k] = ""
    NM_FIELDS[k]["label"] = NM_FIELDS[k]["label"].replace("0 待提供", "留空待提供")
"V5.5.1: explicit seasonal stage controls and separate steam humidification.\nStates describe specified/required conditions; equipment rating tests are separate.\n"
NM_V1_KEYS = set(NM_DEFAULTS)
NM_SOURCE_OPTIONS = ["熱水＋電熱", "電熱", "回收熱水", "停用"]
nm_group(
    "6｜H1／H2 熱源選擇",
    [
        (
            tag + "_source",
            tag.upper() + " 使用熱源",
            "熱水＋電熱",
            "",
            NM_SOURCE_OPTIONS,
        )
        for tag in ["h1", "h2"]
    ],
)
for tag in ["h1", "h2"]:
    nm_group(
        tag.upper() + "｜獨立熱水與電熱條件",
        [
            (
                tag + "_water_mode",
                "熱水條件來源",
                "共用回收水",
                "",
                ["共用回收水", "本段獨立設定"],
            ),
            (tag + "_hw_in", "本段熱水供水", 30, "°C", (5, 95)),
            (tag + "_hw_out", "本段熱水回水", 24, "°C", (1, 90)),
            (tag + "_hw_approach", "本段熱水最小端差", 2, "K", (0.1, 15)),
            (tag + "_eta", "本段電熱效率，0 沿用共同", 0, "比例", (0, 1)),
        ],
    )
for season, title in [("summer", "夏季"), ("winter", "冬季")]:
    rows = []
    for tag, label, temp in [
        ("h1", "H1 預熱", 35),
        ("c1", "C1 預冷", 22),
        ("c2", "C2 再冷", 12.55),
        ("h2", "H2 再熱", 22),
    ]:
        prefix = season + "_" + tag
        modes = ["自動需求", "旁通", "指定出口乾球"] + (
            ["指定出口 T/RH"] if tag.startswith("c") else []
        )
        rows.extend(
            [
                (
                    prefix + "_mode",
                    title + " " + label + " 控制",
                    "自動需求",
                    "",
                    modes,
                ),
                (prefix + "_t", label + " 指定出口乾球", temp, "°C", (-20, 80)),
            ]
        )
        if tag.startswith("c"):
            rows.append((prefix + "_rh", label + " 指定出口濕度", 95, "%RH", (1, 100)))
    nm_group(title + "｜逐段出口條件（入口由上一段連動）", rows)
nm_group(
    "加濕熱源｜濕膜／蒸汽／並用",
    [
        (
            "humidifier",
            "加濕設備組合",
            "循環水洗濕膜",
            "",
            [
                "循環水洗濕膜",
                "電極式蒸汽",
                "電熱式蒸汽",
                "水洗＋電極式蒸汽",
                "水洗＋電熱式蒸汽",
                "不加濕",
            ],
        ),
        ("steam_capacity", "蒸汽額定產汽量，0 待提供", 0, "kg/h", (0, 100000)),
        ("steam_kw", "蒸汽額定電力，0 待提供", 0, "kW", (0, 100000)),
        ("steam_h", "蒸汽比焓（100°C 飽和初估）", 2676.125, "kJ/kg", (2501, 3000)),
        ("steam_feed_t", "蒸汽機補水溫度", 20, "°C", (1, 90)),
        ("steam_eta", "蒸汽發生器效率", 0.95, "比例", (0.1, 1)),
        (
            "steam_water",
            "蒸汽機給水資料",
            "尚未確認",
            "",
            ["尚未確認", "原廠確認可用", "去離子／超純水"],
        ),
        ("steam_conductivity", "給水電導率，0 待提供", 0, "μS/cm", (0, 10000)),
        ("steam_cond_min", "原廠允許電導率下限，0 待提供", 0, "μS/cm", (0, 10000)),
        ("steam_cond_max", "原廠允許電導率上限，0 待提供", 0, "μS/cm", (0, 10000)),
    ],
)
NM_BASIC.update({"h1_source", "h2_source", "humidifier"})
for season in ["summer", "winter"]:
    for tag in ["h1", "c1", "c2", "h2"]:
        NM_BASIC.add(season + "_" + tag + "_mode")

NM_V3_KEYS = set(NM_DEFAULTS)
nm_group(
    "主案連動｜分季入口與送風需求",
    [
        (
            "target_mode",
            "送風設定方式（來源以視窗上方為準）",
            "共用送風目標",
            "",
            ["共用送風目標", "主案分季需求"],
        ),
        ("summer_sa_t", "夏季送風目標乾球", 22, "°C", (-20, 80)),
        ("summer_sa_rh", "夏季送風目標 RH", 55, "%RH", (0, 100)),
        ("winter_sa_t", "冬季送風目標乾球", 22, "°C", (-20, 80)),
        ("winter_sa_rh", "冬季送風目標 RH", 55, "%RH", (0, 100)),
        ("summer_flow", "夏季送風實際風量", 58000, "送風基準 CMH", (1, 1e7)),
        ("winter_flow", "冬季送風實際風量", 58000, "送風基準 CMH", (1, 1e7)),
        ("pump_input_kw", "已確認水洗泵輸入電力（留空未知）", "", "kW", (0, 100000)),
        ("linked_main_hash", "主案連動版本", "尚未連動", "", None),
    ],
)
AHU_OPTIONAL_NUMBERS.add("pump_input_kw")
NM_BASIC.add("target_mode")
