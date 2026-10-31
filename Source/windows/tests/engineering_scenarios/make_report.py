"""Build SCENARIO_REPORT.md from results.json and priority_defects.json (run run_scenarios.py and priority_defects.py first).

Every number in the per-case and sweep sections is read from the JSON, never typed. The prose (issue list, pending-data table,
three-layer conclusions) is in ISSUES / PENDING below and is the reviewer's judgement, kept next to the data it refers to.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
PD = json.loads((HERE / "priority_defects.json").read_text(encoding="utf-8"))

KEY = ("G1", "G1b", "G2", "G3", "G4", "G5", "G6", "G8a", "G11")


def fmt(v):
    if isinstance(v, float):
        return f"{v:,.6g}"
    return str(v)


# severity: H high / M medium / L low. "FAIL" here means a finding about the product, not about this test suite.
ISSUES = [
    ("ISS-1", "M", "FAIL", "U 值單位易誤解", "PD-4b, PD-4c",
     "預設單位 kcal/(h·m²·K)；欄位本身無單位、無提示文字，報告只列牆體負荷 kW，不列 U 值與單位。把 W/(m²·K) 的數值填進預設單位，牆／樓板負荷會少算 14 %（1/1.163）且完全沒有警告。計算本身正確（PD-4a，兩種單位皆與手算一致）。",
     "最小重現：en_wall=100, wall_u=0.5, 其餘同 CR-03，u_unit 維持預設 → 外牆 0.6978 kW；若使用者意圖是 W/(m²·K) 則應為 0.6000 kW。",
     "欄位與單位選擇器分離，且 FIELD_HELP 沒有 wall_u／floor_u／u_unit 條目，報告不回印輸入。",
     "把單位直接顯示在 U 值欄位標籤；加 FIELD_HELP；報告在負荷組成中回印 U 值與單位；單位切換時提示是否換算數值。"),
    ("ISS-2", "L", "FAIL", "拒絕訊息未標示為「未達條件」，且 CR-05 無數字", "OBS-1 (CR-05), OBS-2 (H-02, H-04, F-03)",
     "外氣低於補償下限與乾盤管進水未達露點的拒絕，以輸入錯誤顯示，不是「未達條件」；CR-05 訊息只有「乾盤管進水未達露點＋安全裕度」，不含水溫、露點與需要值。原因經獨立驗算皆正確（R2 PASS），所以是呈現問題，不是計算問題。",
     "CR-05 輸入（見 results.json）→ ValidationError 14 字訊息；H-02 → 「指定外氣 450 低於補償下限 600.0 CMH」。",
     "這幾條檢核早於 F-1 防護，訊息格式沒有統一。", "統一訊息格式：未達條件＋原因＋實際值／需要值＋可調整的欄位（P-01 的訊息已是這個格式，可作範本）。"),
    ("ISS-3", "L", "NOT APPLICABLE", "「初估檢核通過」對任何有負荷的房間都到不了", "PD-2a, PD-2c, PD-2d",
     "只要顯熱或潛熱不為 0，「設備同工況選型」永遠是待後續，所以最高只到「初估完成（待後續階段確認）」。這已是刻意設計，且 PD-2a 證明補齊使用者能補的資料後可以到達該狀態；原本『永遠無法 PASS』的疑點在標示上已解決。是否保留「初估檢核通過」屬產品決策。",
     "D-01 輸入＋latent_mode=沒有額外產濕、e_np_fan=5、ffu_w=200、c2_bf_min=0.15、各管路已知設備壓差 → 初估完成（待後續階段確認）。",
     "quality.py 的狀態階層設計。", "產品決策：保留並在說明中講清楚，或移除這個永遠到不了的狀態。"),
    ("ISS-4", "L", "FAIL", "H／P 類案例沒有負荷輸入時，供風量只由下限決定，顯熱選型未被驗證", "H-01, H-03, P-02, P-03",
     "規格沒有給人員、照明、圍護與設備負荷，引擎照實算出 qs=0，供風溫差為 0。結果只證明『下限風量×盤管』的算術，不證明房間顯熱選型。這是規格缺料，不是引擎錯誤，但報告若被讀成『手術室已驗證』就是誤導。",
     "H-01：50 m²×3 m = 150 m³，送風 20 ACH = 3,000 CMH，引擎 qs = 0 kW、供風 3,000 CMH（全由下限決定）；P-02 同理（18,000 CMH）。", "計畫案例未給負荷。", "待補人員、照明、設備、圍護資料後重跑（見待補資料表）。"),
    ("ISS-5", "M", "FAIL", "合成案例 CR-01：500 ACH 在預設 FFU 與天花板模組下裝不下", "CR-01 E1",
     "1,500,000 CMH ÷ 1,000 CMH/台 = 1,500 台 × 0.72 m² = 1,080 m²，超過 1,000 m² 地板（覆蓋率 108 %，引擎上限 85 %）。引擎正確標示「未達條件」，所以引擎行為正確；這是工程選型層的結論：要嘛提高單台風量，要嘛縮小循環 ACH，要嘛改用大尺寸模組（S-03 顯示 1200×600 模組需單台 ≥ 約 1,271 CMH 才裝得下）。",
     "CR-01 如規格輸入。", "規格 + 預設 FFU 的幾何不可行。", "這是案例結論而非程式缺陷；請業主提供實際 FFU 型號。"),
    ("ISS-6", "L", "FAIL", "既有 GUI 測試 9 項失敗（simple_gui 5、v554_gui 4）與下拉選單選取文字遮擋", "上一輪完整測試",
     "與本輪無關、本輪未改程式；上一輪完整測試在 Linux/Xvfb 的結果與 F-1 修補前相同。屬於測試過時或 GUI 排版問題，Windows 原生外觀未驗證。",
     "tests/simple_gui_checks.py、tests/v554_gui_checks.py", "測試對應舊 UI 版面／字型度量。", "在 Windows 實機重跑並更新測試期望值。"),
    ("ISS-7", "L", "FAIL", "乾燥外氣下的保守誤拒", "F-1 修補報告",
     "F-1 修補後在 4,000 個隨機 AHU 情境中 1 例因外氣含濕量低於室內而被拒絕（保守方向，不會多給風量）。",
     "見 tests/fixtures/feed_stress_20261031/after_f1_fix/F1_FIX_REPORT.md", "可達性判準採嚴格 BF ≥ 0。", "列為已知限制，待討論是否放寬。"),
]

PENDING = [
    ("圍護結構（牆面積、U 值、樓板、日射）", "全部 20 案", "牆／樓板／日射皆設 0（A-ENV）→ 低估靠外牆房間負荷", "建築圖與熱工資料"),
    ("人員數與人體散熱、照明功率", "全部 20 案", "人員、照明設 0（A-PPL）→ H／P 類 qs=0", "業主 URS／平面配置"),
    ("設備顯熱的同時率與入室比例", "全部", "規格的『設備顯熱 kW』直接當入室熱，PCW／排氣帶走熱比例 0（A-EQ）", "設備清單與冷卻方式"),
    ("製程水氣／潛熱", "CR、H、P、D、F", "latent_mode 未指定，製程水氣設 0（A-LAT）", "製程資料"),
    ("洩漏／門縫／開口與壓差目標值", "CR-05, CR-06, H-01..04, P-02", "en_p_A=0、洩漏 0（A-PRS）；不得由風量差推定 Pa", "漏風測試或洩漏模型、URS 壓差"),
    ("轉移風量與負壓／排風櫃補風路徑", "H-02, H-04, F-03", "引擎無此模型 → BLOCKED", "新增模型或另用外部工具"),
    ("局部 ISO 5 區", "P-01", "背景 ACH 不能推定局部潔淨度；引擎無此模型", "RABS／隔離器廠商資料與確效計畫"),
    ("FFU 型號、有效風量、阻力曲線、備援與故障台數", "CR-01..08", "預設 1,000 CMH、0.72 m²、無阻力與備援欄位（A-CHW）", "FFU 廠商性能表"),
    ("盤管性能（BF 下限、排數）、冰水／乾盤管供水溫度與溫差", "全部含除濕案", "冰水 7 °C、乾盤管水 14 °C、approach 1 K 為引擎預設（A-CHW）；BF 下限未提供 → 排數能力待資料", "盤管廠商選型書"),
    ("設備備援（N+1）", "D-01, D-02, CR-01..08", "引擎無備援欄位", "業主可用性要求"),
    ("風機曲線、管徑、設備壓降、水力實際長度", "全部", "只有管路小計，設備阻力待資料（A-HYD）", "管路圖、設備資料"),
    ("電氣：電壓、線纜、保護、敷設條件", "全部", "G9 NOT APPLICABLE：未指定電氣條件（A-ELE）", "電氣設計輸入與適用規範版本"),
    ("電池化學種類與氫氣／排氣量", "D-02", "顯熱不能證明通風安全 → BLOCKED", "電池廠商資料與安全分析"),
    ("控制精度 ±0.5 °C、穩定性", "F-02", "穩態需求計算，無控制回路模型 → BLOCKED", "控制設計與感測器規格"),
    ("冬季條件下的室內加熱設備與熱源", "CR-07", "W1 檢核只驗證空氣側加濕／再熱收支；NP 電力待資料", "加熱設備資料"),
    ("適用法規與版本（潔淨度、醫院、GMP、電氣）", "全部", "L3 NOT VERIFIED，本報告不作任何符合性宣稱", "業主指定的規範與版本"),
]


def main():
    L = []
    w = L.append
    cases = R["cases"]
    tally = {}
    for c in cases:
        tally[c["conclusion"]] = tally.get(c["conclusion"], 0) + 1
    ck = {s: sum(1 for c in cases for k in c["checks"] if k["status"] == s) for s in ("PASS", "FAIL", "BLOCKED", "NOT APPLICABLE")}
    w("# Facility Studio V5.6.0 win.9｜20 組代表性工程情境驗證報告\n")
    w("日期：2026-10-31｜依據：《20 組代表性工程情境驗證計畫》｜**僅 Linux 環境驗證**（Python 3.12、psychrolib 2.5.0、Xvfb）；Windows 原生 GUI／EXE／安裝程式**未驗證**，須另行驗收。\n")
    w("本輪**未修改任何正式程式**，亦未發布 Release；所有結果由 `tests/engineering_scenarios/` 的腳本產生，可重現。\n")
    w("> 本報告驗證的是計算實作（第 1 層）與選型合理性（第 2 層）。第 3 層（規範符合性：FEED、醫院感染控制、GMP、電氣法規）**NOT VERIFIED**，本報告不作任何符合性宣稱。案例為測試設定，不是已竣工實測資料。\n")
    w("## 1. 總結\n")
    w(f"- 20 案第 1 層結論：**PASS {tally.get('PASS', 0)}**、**FAIL {tally.get('FAIL', 0)}**、**BLOCKED {tally.get('BLOCKED', 0)}**（BLOCKED 為引擎拒絕該輸入或無法表達，不列為通過）。")
    w(f"- 檢核項合計：PASS {ck['PASS']}、FAIL {ck['FAIL']}、BLOCKED {ck['BLOCKED']}、NOT APPLICABLE {ck['NOT APPLICABLE']}。FAIL 的那一項是 CR-01 的第 2 層（FFU 覆蓋率 108 % > 85 %），引擎本身已正確標示未達條件。")
    w(f"- 5 組邊界掃描：" + "；".join(f"{s['id']} {s['conclusion']}" for s in R["sweeps"]) + "。")
    pdc = {s: sum(1 for p in PD if p["status"] == s) for s in ("PASS", "FAIL", "BLOCKED", "NOT APPLICABLE")}
    w(f"- 優先缺陷驗證：{pdc}。F-1 在基準版可重現（約 7.41×10⁹ CMH 且只標待補資料），在目前分支被明確拒絕；U 值單位易誤解**仍存在**（ISS-1）。")
    w("- **「PASS 很多」不等於工程合理**：H／P 類 4 案沒有負荷輸入（qs=0），PASS 只代表算術與規格一致；CR-01 則是引擎正確指出規格不可行。請看第 8 節的整體問題清單與第 9 節的待補資料。\n")
    w("## 2. 執行環境與讀取檔案\n")
    w("- 讀取：`Facility_Studio_20組代表性工程情境測試_20261031.txt`（本計畫）、`Source/windows/facility_studio/{engine,quality,schema,airflow_guard,reports,optional_inputs}.py`、前一輪 `F1_FIX_REPORT.md`。")
    w("- 分支 `claude/festive-newton-0o715t`，產品碼與上一次提交相同（`git diff HEAD -- facility_studio` 無差異）。")
    w("- 基準對照：`git archive 2c46056`（匯入的基準版）。\n")
    w("## 3. 假設（規格未給、逐一列出；不是實測值）\n")
    w("| 編號 | 項目 | 採用 | 備註 |\n|---|---|---|---|")
    for a in R["assumptions"]:
        w(f"| {a['id']} | {a['item']} | {a['used']} | {a['note']} |")
    w("")
    w("## 4. 逐案結果\n")
    w("| ID | 情境 | 系統 | 引擎結果 | 第 1 層 | 第 2 層 | 重現命令 |\n|---|---|---|---|---|---|---|")
    for c in cases:
        e = c.get("engine")
        res = (f"循環 {e['circulation_cmh']:,.0f} CMH／FFU {e['ffu_count']}／DCC {e['dcc_count']}／RCU {e['rcu_count']}／供風 {e['supply_room_cmh']:,.0f} CMH／總冷 {e['q_total_kw']:.1f} kW／{c['quality']['status']}"
               if e else "拒絕：" + c["message"][:60])
        w(f"| {c['id']} | {c['scenario']} | {c['system']} | {res} | {c['conclusion']} | {c['conclusion_L2'][:70]} | `{c['reproduce']}` |")
    w("")
    for c in cases:
        w(f"### {c['id']}｜{c['scenario']}\n")
        w(f"- 規格：{json.dumps(c['spec'], ensure_ascii=False)}")
        w(f"- 對映到引擎的輸入（只列與預設不同者）：`{json.dumps(c['engine_inputs'], ensure_ascii=False)}`")
        w(f"- 結論：**{c['conclusion']}**（第 2 層：{c['conclusion_L2']}）— {c['conclusion_note']}")
        if c["outcome"] == "rejected":
            w(f"- 引擎訊息：{c['message']}")
        else:
            w(f"- 品質閘門：{c['quality']['status']}（未達 {c['quality']['failed']}、待資料 {c['quality']['pending']}、待後續 {c['quality']['deferred']}）")
            for wn in c["warnings"]:
                w(f"- 警告：{wn}")
        if c["blocked_aspects"]:
            w("- BLOCKED 面向：" + "；".join(f"{b['aspect']}（{b['reason']}）" for b in c["blocked_aspects"]))
        w("\n| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |\n|---|---|---|---|---|---|---|")
        for k in c["checks"]:
            if k["id"] in KEY or k["status"] in ("FAIL", "BLOCKED") or c["outcome"] == "rejected":
                w(f"| {k['id']} {k['name'][:60]} | {k['layer']} | {k['status']} | {fmt(k['expected']) if k['expected'] is not None else ''} | {fmt(k['actual']) if k['actual'] is not None else ''} | {fmt(k['error']) if k.get('error') is not None else ''} | {k['note'][:90]} |")
        w("")
    w("### 非案例探針（明確標示，不是計畫案例）\n")
    for p in R.get("probes", []):
        w(f"- {p['case']}：{p['label']} → {p['outcome']}（{p.get('status', p.get('message', ''))}）。{p['note']}")
    w("\n## 5. 五組非隨機邊界掃描\n")
    for s in R["sweeps"]:
        w(f"### {s['id']}｜{s['case']}｜{s['conclusion']}\n")
        w(f"- 結果：{s['summary']}")
        w(f"- 步階選取依據與實際步長：{s['basis']}")
        w(f"- 先於引擎給出的預測：{s['prediction']}")
        w(f"- 預測與引擎不一致項：{s['problems'] if s['problems'] else '無'}")
        for b in s.get("blocked", []):
            w(f"- BLOCKED：{b['aspect']} — {b['reason']}")
        if s.get("failed_unit_table_external"):
            w("\n測試者以外部公式（非引擎）計算的故障台數表（安裝台數 = ceil(Q/單台)+故障台數）：\n\n| 故障台數 | 需安裝台數 | 可用風量 CMH | 缺口 CMH |\n|---|---|---|---|")
            for t in s["failed_unit_table_external"]:
                w(f"| {t['failed_units']} | {t['required_installed']} | {t['available_airflow_cmh']:,.0f} | {t['shortfall_cmh']:,.0f} |")
        w("\n| 步階 | 預測 | 引擎 | 狀態 |\n|---|---|---|---|")
        for st in s["steps"]:
            w(f"| {st['step']} | {'接受' if st['predicted_accept'] else '拒絕'} | {'接受' if st['accepted'] else '拒絕'} | {st.get('status') or st.get('message', '')[:50]} |")
        w("")
    w("## 6. 優先缺陷驗證\n")
    w("| 編號 | 項目 | 狀態 | 說明 |\n|---|---|---|---|")
    for p in PD:
        w(f"| {p['id']} | {p['name'][:80]} | {p['status']} | {p['detail'][:260].replace('|', '/')} |")
    w("\n## 7. 三層結論\n")
    w("| 層 | 結論 |\n|---|---|")
    w("| 1 計算實作 | 15 案 PASS：幾何、風量、FFU 台數、濕空氣狀態（PsychroLib）、盤管能量收支、餘裕只加一次、水力（Colebrook）、冬季加濕收支（CR-07）、中英文報告數字一致；5 案引擎拒絕（原因經獨立驗算）→ BLOCKED；5 組掃描與預測一致 |")
    w("| 2 工程選型合理性 | CR-01 在預設 FFU 下覆蓋率 108 % → 不可行（引擎已標示）；H／P 4 案缺負荷資料，選型合理性**無法判斷**；D／F 案在預設 7 °C 冰水下有除濕，資料中心實務常用較高水溫，屬待確認；其餘 CR 案未發現獨立檢核能指出的問題。不等於合理，只是這些檢核沒找到問題 |")
    w("| 3 規範符合性 | **NOT VERIFIED**。未對照任何規範版本、設計輸入與審核證據，不得宣稱符合 FEED、醫院感染控制、藥廠 GMP、無塵室等級或電氣法規 |\n")
    w("## 8. 整體問題清單\n")
    for i in ISSUES:
        w(f"### {i[0]}｜{i[3]}｜嚴重度 {i[1]}｜{i[2]}\n- 來源：{i[4]}\n- 說明：{i[5]}\n- 最小重現：{i[6]}\n- 可能根因：{i[7]}\n- 修正建議：{i[8]}\n")
    w("## 9. 待補工程資料表\n")
    w("| 資料 | 影響案例 | 目前處理 | 取得來源 |\n|---|---|---|---|")
    for p in PENDING:
        w("| " + " | ".join(p) + " |")
    w("\n## 10. 重現\n")
    w("```bash\ncd Source/windows\npython tests/engineering_scenarios/run_scenarios.py            # 20 案 + 5 掃描 → results.json\npython tests/engineering_scenarios/run_scenarios.py --case CR-02\npython tests/engineering_scenarios/priority_defects.py --baseline-src <git archive 2c46056 的 Source/windows>\npython tests/engineering_scenarios/make_report.py             # 重建本報告\n```\n")
    w("## 11. 未驗證項目\n")
    w("- Windows 原生 GUI、EXE、MSI 安裝程式；Linux 虛擬顯示不等同。\n- 第 3 層全部（規範符合性）。\n- 計畫中 7,412,540,040 CMH 的確切輸入未提供，F-1 以記錄的重現案例驗證同一失效模式。\n- 以上未列為 PASS 的項目均為 BLOCKED／NOT APPLICABLE／待確認。")
    (HERE / "SCENARIO_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote SCENARIO_REPORT.md", len("\n".join(L)))


if __name__ == "__main__":
    main()
