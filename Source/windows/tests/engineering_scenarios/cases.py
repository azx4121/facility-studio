"""The 20 representative cases and 5 boundary sweeps of the 2026-10-31 verification plan, as data.

Every value in SPEC is copied from the plan table. MAPPING says how each plan field becomes an engine input, and
ASSUMPTIONS lists every engine input the plan does not give, with the value used and why. Nothing is tuned to pass.
"""
import math

# id, scenario, area m2, height m, room C, room %RH, OA CMH, exhaust CMH, ACH kind, ACH, equipment sensible kW (None = not specified), focus
SPEC = [
    ("CR-01", "半導體 Class 10 無塵室", 1000, 3.0, 22, 50, 12000, 9000, "循環", 500, 500, "高ACH、FFU與DCC選型"),
    ("CR-02", "半導體 Class 100 無塵室", 2000, 3.0, 22, 50, 20000, 16000, "循環", 120, 800, "MAU/FFU風量分工"),
    ("CR-03", "電子廠 Class 1000", 1500, 3.5, 23, 50, 15000, 12000, "循環", 70, 600, "製程顯熱與除濕"),
    ("CR-04", "電子組裝 Class 10000", 1200, 3.5, 24, 50, 9000, 7500, "循環", 35, 250, "人員照明設備負荷"),
    ("CR-05", "潔淨包裝 Class 100000", 800, 3.0, 24, 55, 4000, 3200, "循環", 20, 80, "低ACH、正壓概念"),
    ("CR-06", "半導體高排氣製程區", 1800, 4.0, 22, 45, 58000, 52000, "循環", 120, 1200, "補風、排氣、壓差與FFU"),
    ("CR-07", "冬季無塵室加濕", 1000, 3.0, 22, 50, 12000, 10000, "循環", 70, 200, "冬季外氣5°C/70%RH；加熱加濕再熱"),
    ("CR-08", "夏季高濕無塵室", 1000, 3.0, 22, 45, 15000, 12000, "循環", 120, 300, "夏季外氣35°C/75%RH；除濕再熱"),
    ("H-01", "醫院正壓手術室", 50, 3.0, 21, 50, 900, 750, "送風", 20, None, "換氣、外氣、正壓與濕度"),
    ("H-02", "醫院負壓隔離病房", 30, 3.0, 23, 50, 450, 600, "送風", 12, None, "負壓、排風與補風"),
    ("H-03", "醫院保護性環境病房", 35, 3.0, 22, 45, 500, 350, "送風", 12, None, "正壓與潔淨送風"),
    ("H-04", "醫院檢驗實驗室", 150, 3.0, 23, 50, 2500, 3000, "送風", 12, None, "排風櫃與補風"),
    ("P-01", "無菌藥品灌裝背景區", 200, 3.0, 20, 45, 3000, 2500, "送風", 40, None, "背景環境及局部ISO 5分開驗證"),
    ("P-02", "藥廠潔淨走廊", 300, 3.0, 22, 50, 2000, 1600, "送風", 20, None, "壓差梯度、門開啟影響"),
    ("P-03", "生技細胞培養室", 120, 3.0, 22, 50, 1500, 1200, "送風", 20, None, "潔淨送風與溫濕度"),
    ("D-01", "資料中心伺服器機房", 500, 3.5, 24, 45, 1500, 1200, None, None, 600, "高顯熱、設備備援"),
    ("D-02", "UPS／電池設備室", 100, 3.0, 25, 50, 1000, 900, None, None, 60, "UPS散熱；電池安全通風另核"),
    ("F-01", "一般電子製造廠", 2000, 5.0, 26, 55, 20000, 18000, None, None, 500, "工業負荷與空調選型"),
    ("F-02", "精密量測恆溫室", 200, 3.0, 22, 50, 1500, 1200, None, None, 30, "小溫差、精度及控制穩定性（22±0.5）"),
    ("F-03", "高溫高濕工業製程區", 600, 4.0, 28, 60, 15000, 18000, None, None, 300, "高濕、排氣大於外氣、補風"),
]
FIELDS = ("id", "scenario", "area_m2", "height_m", "room_t", "room_rh", "oa_cmh", "exhaust_cmh", "ach_kind", "ach", "equip_kw", "focus")

# footprint L x W is NOT given; a plain rectangle with the stated area is used (assumption A-GEO)
FOOTPRINT = {1000: (40, 25), 2000: (50, 40), 1500: (50, 30), 1200: (40, 30), 800: (40, 20), 1800: (60, 30), 50: (10, 5), 30: (6, 5), 35: (7, 5),
             150: (15, 10), 200: (20, 10), 300: (30, 10), 120: (12, 10), 500: (25, 20), 100: (10, 10), 600: (30, 20)}

MAU, AHU, RCU = "MAU+FFU+DCC (全外氣/無塵室)", "AHU (OA+RA 混合)", "RCU (機房空調箱+外氣)"
SYSTEM = {"CR": MAU, "H": AHU, "P": AHU, "D": RCU, "F": AHU}


def case(row):
    c = dict(zip(FIELDS, row))
    prefix = c["id"].split("-")[0]
    c["system"] = SYSTEM[prefix]
    return c


CASES = [case(r) for r in SPEC]


def inputs(c):
    """Plan fields -> engine inputs, plus the neutral values for everything the plan does not give."""
    L, W = FOOTPRINT[c["area_m2"]]
    assert L * W == c["area_m2"]
    o = dict(
        sys_type=c["system"], en_L_A=L, en_W_A=W, en_H_A=c["height_m"], ra_t=c["room_t"], ra_rh=c["room_rh"],
        oa_t=35, oa_rh=75 if c["id"] == "CR-08" else 65,                       # plan: default summer outdoor air 35 C / 65 %RH (CR-08: 75 %RH)
        en_manual_oa=c["oa_cmh"], gex_q=c["exhaust_cmh"], exhaust_margin_pct=0,   # plan gives the final exhaust flow: no extra 5 % margin
        en_ach_A=c["ach"] if c["ach"] is not None else 0,
        eq_kw=c["equip_kw"] if c["equip_kw"] is not None else 0, eq_rt=100, exh_ratio=0,
        # --- not given by the plan: switched off, not invented (see ASSUMPTIONS)
        ppl_A=0, light_lux=0, en_wall=0, en_floor=0, solar_kw=0, process_latent_kw=0, process_moisture_kg_h=0, oven_kw=0, fan_room_kw=0,
        en_p_A=0, en_gap_L=0, en_door_F=0,
    )
    if c["id"] == "CR-07":
        o.update(ow_t=5, ow_rh=70)                                                # plan: winter outdoor air 5 C / 70 %RH
    if c["system"] == MAU:
        o.update(ffu_topology="獨立FFU循環（MAU直接入室）")                          # circulation by FFU, outdoor air straight from the MAU, listed separately
    return o


ASSUMPTIONS = [
    ("A-GEO", "房間外形", "平面長寬未給；用面積相符的長方形（見 FOOTPRINT）", "只影響門縫／洩漏預設，已關閉洩漏"),
    ("A-ENV", "圍護結構", "牆、樓板面積與 U 值、日射均未給；牆、樓板面積設 0、日射 0（視為無圍護得熱）", "待補；會低估靠外牆房間的負荷"),
    ("A-PPL", "人員與照明", "人數、人體散熱、燈具均未給；人數 0、照度 0", "待補；人員潛熱與照明得熱為 0"),
    ("A-EQ", "設備顯熱", "表中「未指定」者設備顯熱 0；有給者運轉率 100%、無排氣帶走（直接採表值為室內顯熱）", "待補；醫院、藥廠案例無任何顯熱負荷"),
    ("A-LAT", "製程產濕", "未給；額外製程潛熱與水氣設 0（引擎預設 5 kW 不採用）；製程產濕狀態保持「尚不清楚」，閘門自然列待資料", "待補"),
    ("A-OA", "外氣量基準", "表中外氣 CMH 視為室內基準 CMH（引擎 en_manual_oa）", "待補；若為外氣狀態體積流量，換算不同"),
    ("A-EXH", "排氣", "表中排氣 CMH 放入一般排氣風管 gex_q，排氣設計餘裕設 0%", "引擎沒有「房間排氣」欄位，只有排氣風管"),
    ("A-ACH", "ACH 語意", "表「循環」案例採 MAU＋FFU＋DCC、獨立FFU循環（MAU直接入室），en_ach_A＝循環ACH；表「送風」案例採混風 AHU，en_ach_A＝送風量下限；未指定者設 0", "兩種語意在引擎是同一欄位"),
    ("A-SYS", "系統型式", "無塵室→MAU＋FFU＋DCC；醫院、藥廠、一般廠房、恆溫室→混風 AHU；資料中心→RCU（機房空調箱）", "表未指定系統"),
    ("A-PRS", "壓差", "表未給壓差值；en_p_A＝0、門縫與開門次數＝0，故引擎不估洩漏、不推定正壓", "壓差值待補；引擎只能表達 ≥0 的壓差"),
    ("A-CHW", "冰水與盤管", "冰水供水、溫差、ADP 裕度、盤管 BF、設備單台能力、FFU 單台風量（1000 CMH）皆用引擎預設", "待補；引擎預設值不是實測"),
    ("A-HYD", "水力", "管長、管件、設備壓差、流速上限用引擎預設", "待補"),
    ("A-ELE", "電氣", "表未給電氣負載；配電檢查 NOT APPLICABLE", "待補"),
    ("A-WIN", "冬季", "CR-07 冬季外氣 5°C／70%RH，其餘冬季外氣用引擎預設 8°C／70%RH", "預設只影響冬季輸出"),
]
