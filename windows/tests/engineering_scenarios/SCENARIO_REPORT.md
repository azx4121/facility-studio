# Facility Studio V5.6.0 win.9｜20 組代表性工程情境驗證報告

日期：2026-10-31｜依據：《20 組代表性工程情境驗證計畫》｜**僅 Linux 環境驗證**（Python 3.12、psychrolib 2.5.0、Xvfb）；Windows 原生 GUI／EXE／安裝程式**未驗證**，須另行驗收。

本輪**未修改任何正式程式**，亦未發布 Release；所有結果由 `tests/engineering_scenarios/` 的腳本產生，可重現。

> 本報告驗證的是計算實作（第 1 層）與選型合理性（第 2 層）。第 3 層（規範符合性：FEED、醫院感染控制、GMP、電氣法規）**NOT VERIFIED**，本報告不作任何符合性宣稱。案例為測試設定，不是已竣工實測資料。

## 1. 總結

- 20 案第 1 層結論：**PASS 15**、**FAIL 0**、**BLOCKED 5**（BLOCKED 為引擎拒絕該輸入或無法表達，不列為通過）。
- 檢核項合計：PASS 337、FAIL 1、BLOCKED 5、NOT APPLICABLE 36。FAIL 的那一項是 CR-01 的第 2 層（FFU 覆蓋率 108 % > 85 %），引擎本身已正確標示未達條件。
- 5 組邊界掃描：S-01 PASS；S-01b PASS；S-02 PASS；S-03 PASS；S-04 PASS；S-05 PASS。
- 優先缺陷驗證：{'PASS': 11, 'FAIL': 2, 'BLOCKED': 2, 'NOT APPLICABLE': 1}。F-1 在基準版可重現（約 7.41×10⁹ CMH 且只標待補資料），在目前分支被明確拒絕；U 值單位易誤解**仍存在**（ISS-1）。
- **「PASS 很多」不等於工程合理**：H／P 類 4 案沒有負荷輸入（qs=0），PASS 只代表算術與規格一致；CR-01 則是引擎正確指出規格不可行。請看第 8 節的整體問題清單與第 9 節的待補資料。

## 2. 執行環境與讀取檔案

- 讀取：`Facility_Studio_20組代表性工程情境測試_20261031.txt`（本計畫）、`Source/windows/facility_studio/{engine,quality,schema,airflow_guard,reports,optional_inputs}.py`、前一輪 `F1_FIX_REPORT.md`。
- 分支 `claude/festive-newton-0o715t`，產品碼與上一次提交相同（`git diff HEAD -- facility_studio` 無差異）。
- 基準對照：`git archive 2c46056`（匯入的基準版）。

## 3. 假設（規格未給、逐一列出；不是實測值）

| 編號 | 項目 | 採用 | 備註 |
|---|---|---|---|
| A-GEO | 房間外形 | 平面長寬未給；用面積相符的長方形（見 FOOTPRINT） | 只影響門縫／洩漏預設，已關閉洩漏 |
| A-ENV | 圍護結構 | 牆、樓板面積與 U 值、日射均未給；牆、樓板面積設 0、日射 0（視為無圍護得熱） | 待補；會低估靠外牆房間的負荷 |
| A-PPL | 人員與照明 | 人數、人體散熱、燈具均未給；人數 0、照度 0 | 待補；人員潛熱與照明得熱為 0 |
| A-EQ | 設備顯熱 | 表中「未指定」者設備顯熱 0；有給者運轉率 100%、無排氣帶走（直接採表值為室內顯熱） | 待補；醫院、藥廠案例無任何顯熱負荷 |
| A-LAT | 製程產濕 | 未給；額外製程潛熱與水氣設 0（引擎預設 5 kW 不採用）；製程產濕狀態保持「尚不清楚」，閘門自然列待資料 | 待補 |
| A-OA | 外氣量基準 | 表中外氣 CMH 視為室內基準 CMH（引擎 en_manual_oa） | 待補；若為外氣狀態體積流量，換算不同 |
| A-EXH | 排氣 | 表中排氣 CMH 放入一般排氣風管 gex_q，排氣設計餘裕設 0% | 引擎沒有「房間排氣」欄位，只有排氣風管 |
| A-ACH | ACH 語意 | 表「循環」案例採 MAU＋FFU＋DCC、獨立FFU循環（MAU直接入室），en_ach_A＝循環ACH；表「送風」案例採混風 AHU，en_ach_A＝送風量下限；未指定者設 0 | 兩種語意在引擎是同一欄位 |
| A-SYS | 系統型式 | 無塵室→MAU＋FFU＋DCC；醫院、藥廠、一般廠房、恆溫室→混風 AHU；資料中心→RCU（機房空調箱） | 表未指定系統 |
| A-PRS | 壓差 | 表未給壓差值；en_p_A＝0、門縫與開門次數＝0，故引擎不估洩漏、不推定正壓 | 壓差值待補；引擎只能表達 ≥0 的壓差 |
| A-CHW | 冰水與盤管 | 冰水供水、溫差、ADP 裕度、盤管 BF、設備單台能力、FFU 單台風量（1000 CMH）皆用引擎預設 | 待補；引擎預設值不是實測 |
| A-HYD | 水力 | 管長、管件、設備壓差、流速上限用引擎預設 | 待補 |
| A-ELE | 電氣 | 表未給電氣負載；配電檢查 NOT APPLICABLE | 待補 |
| A-WIN | 冬季 | CR-07 冬季外氣 5°C／70%RH，其餘冬季外氣用引擎預設 8°C／70%RH | 預設只影響冬季輸出 |

## 4. 逐案結果

| ID | 情境 | 系統 | 引擎結果 | 第 1 層 | 第 2 層 | 重現命令 |
|---|---|---|---|---|---|---|
| CR-01 | 半導體 Class 10 無塵室 | MAU+FFU+DCC (全外氣/無塵室) | 循環 1,500,000 CMH／FFU 1500／DCC 46／RCU 0／供風 12,000 CMH／總冷 745.4 kW／未達條件 | PASS | FLAG: FFUs fit the ceiling (coverage <= engine limit 85 %) | `python tests/engineering_scenarios/run_scenarios.py --case CR-01` |
| CR-02 | 半導體 Class 100 無塵室 | MAU+FFU+DCC (全外氣/無塵室) | 循環 720,000 CMH／FFU 720／DCC 74／RCU 0／供風 20,000 CMH／總冷 1209.0 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case CR-02` |
| CR-03 | 電子廠 Class 1000 | MAU+FFU+DCC (全外氣/無塵室) | 循環 367,500 CMH／FFU 368／DCC 55／RCU 0／供風 15,000 CMH／總冷 889.3 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case CR-03` |
| CR-04 | 電子組裝 Class 10000 | MAU+FFU+DCC (全外氣/無塵室) | 循環 147,000 CMH／FFU 147／DCC 23／RCU 0／供風 9,000 CMH／總冷 412.9 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case CR-04` |
| CR-05 | 潔淨包裝 Class 100000 | MAU+FFU+DCC (全外氣/無塵室) | 拒絕：乾盤管進水未達露點＋安全裕度 | BLOCKED | BLOCKED | `python tests/engineering_scenarios/run_scenarios.py --case CR-05` |
| CR-06 | 半導體高排氣製程區 | MAU+FFU+DCC (全外氣/無塵室) | 循環 864,000 CMH／FFU 864／DCC 111／RCU 0／供風 58,000 CMH／總冷 2459.5 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case CR-06` |
| CR-07 | 冬季無塵室加濕 | MAU+FFU+DCC (全外氣/無塵室) | 循環 210,000 CMH／FFU 210／DCC 19／RCU 0／供風 12,000 CMH／總冷 445.4 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case CR-07` |
| CR-08 | 夏季高濕無塵室 | MAU+FFU+DCC (全外氣/無塵室) | 循環 360,000 CMH／FFU 360／DCC 28／RCU 0／供風 15,000 CMH／總冷 672.3 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case CR-08` |
| H-01 | 醫院正壓手術室 | AHU (OA+RA 混合) | 循環 3,000 CMH／FFU 0／DCC 0／RCU 0／供風 3,000 CMH／總冷 25.7 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case H-01` |
| H-02 | 醫院負壓隔離病房 | AHU (OA+RA 混合) | 拒絕：指定外氣 450 低於補償下限 600.0 CMH | BLOCKED | BLOCKED | `python tests/engineering_scenarios/run_scenarios.py --case H-02` |
| H-03 | 醫院保護性環境病房 | AHU (OA+RA 混合) | 循環 1,260 CMH／FFU 0／DCC 0／RCU 0／供風 1,260 CMH／總冷 13.8 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case H-03` |
| H-04 | 醫院檢驗實驗室 | AHU (OA+RA 混合) | 拒絕：指定外氣 2500 低於補償下限 3000.0 CMH | BLOCKED | BLOCKED | `python tests/engineering_scenarios/run_scenarios.py --case H-04` |
| P-01 | 無菌藥品灌裝背景區 | AHU (OA+RA 混合) | 拒絕：未達條件：盤管最低可達含濕量 6.656 g/kg（冰水供水＋ADP 裕度 8.00°C）不低於室內含濕量 6.528  | BLOCKED | BLOCKED | `python tests/engineering_scenarios/run_scenarios.py --case P-01` |
| P-02 | 藥廠潔淨走廊 | AHU (OA+RA 混合) | 循環 18,000 CMH／FFU 0／DCC 0／RCU 0／供風 18,000 CMH／總冷 72.5 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case P-02` |
| P-03 | 生技細胞培養室 | AHU (OA+RA 混合) | 循環 7,200 CMH／FFU 0／DCC 0／RCU 0／供風 7,200 CMH／總冷 45.3 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case P-03` |
| D-01 | 資料中心伺服器機房 | RCU (機房空調箱+外氣) | 循環 0 CMH／FFU 0／DCC 0／RCU 7／供風 184,270 CMH／總冷 623.8 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case D-01` |
| D-02 | UPS／電池設備室 | RCU (機房空調箱+外氣) | 循環 0 CMH／FFU 0／DCC 0／RCU 1／供風 18,534 CMH／總冷 74.2 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case D-02` |
| F-01 | 一般電子製造廠 | AHU (OA+RA 混合) | 循環 0 CMH／FFU 0／DCC 0／RCU 0／供風 155,379 CMH／總冷 748.1 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case F-01` |
| F-02 | 精密量測恆溫室 | AHU (OA+RA 混合) | 循環 0 CMH／FFU 0／DCC 0／RCU 0／供風 9,150 CMH／總冷 55.2 kW／待補資料 | PASS | no engineering concern found by the independent checks | `python tests/engineering_scenarios/run_scenarios.py --case F-02` |
| F-03 | 高溫高濕工業製程區 | AHU (OA+RA 混合) | 拒絕：指定外氣 15000 低於補償下限 18000.0 CMH | BLOCKED | BLOCKED | `python tests/engineering_scenarios/run_scenarios.py --case F-03` |

### CR-01｜半導體 Class 10 無塵室

- 規格：{"area_m2": 1000, "height_m": 3.0, "room_t": 22, "room_rh": 50, "oa_cmh": 12000, "exhaust_cmh": 9000, "ach_kind": "循環", "ach": 500, "equip_kw": 500, "focus": "高ACH、FFU與DCC選型"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "en_L_A": "40", "en_W_A": "25", "en_H_A": "3", "oa_rh": "65", "en_manual_oa": "12000", "gex_q": "9000", "exhaust_margin_pct": "0", "en_ach_A": "500", "eq_kw": "500", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0", "ffu_topology": "獨立FFU循環（MAU直接入室）"}`
- 結論：**PASS**（第 2 層：FLAG: FFUs fit the ceiling (coverage <= engine limit 85 %)）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：未達條件（未達 1、待資料 8、待後續 1）
- 警告：壓損 CHW、DCCW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。
- 警告：FFU覆蓋率 108.0% 超過專案安裝上限 85%。
- BLOCKED 面向：FFU 備援與故障台數、單台阻力（引擎沒有備援或阻力欄位（見 S-03））

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 3,000 | 3,000 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 1.5e+06 | 1.5e+06 | 0 |  |
| G2 FFU count = ceil(circulation / unit airflow); unit 1000 CMH  | L1 | PASS | 1500 | 1500 | 0 |  |
| G3 MAU outdoor air is listed apart from the FFU circulation and | L1 | PASS | OA 12000 / FFU circulation 1.5e+06 | OA 12000 / FFU 1.5e+06 | 0 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 269.942 | 269.942 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 773.696 | 773.696 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | 未達條件 | 未達條件 |  | FFU coverage 108.0 % > 85 % | items 未達1 待資料8 待後續1 |
| E1 FFUs fit the ceiling (coverage <= engine limit 85 %) | L2 | FAIL | <= 85 % | 108.0 % |  | engineering infeasible as stated; the engine reports it as 未達條件 |

### CR-02｜半導體 Class 100 無塵室

- 規格：{"area_m2": 2000, "height_m": 3.0, "room_t": 22, "room_rh": 50, "oa_cmh": 20000, "exhaust_cmh": 16000, "ach_kind": "循環", "ach": 120, "equip_kw": 800, "focus": "MAU/FFU風量分工"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "en_L_A": "50", "en_W_A": "40", "en_H_A": "3", "oa_rh": "65", "en_manual_oa": "20000", "gex_q": "16000", "exhaust_margin_pct": "0", "en_ach_A": "120", "eq_kw": "800", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0", "ffu_topology": "獨立FFU循環（MAU直接入室）"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 8、待後續 1）
- 警告：壓損 CHW、DCCW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 6,000 | 6,000 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 720,000 | 720,000 | 0 |  |
| G2 FFU count = ceil(circulation / unit airflow); unit 1000 CMH  | L1 | PASS | 720 | 720 | 0 | plan 3.2: CR-02 needs 720 units at 1000 CMH |
| G3 MAU outdoor air is listed apart from the FFU circulation and | L1 | PASS | OA 20000 / FFU circulation 720000 | OA 20000 / FFU 720000 | 3.63798e-12 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 449.904 | 449.904 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 1,289.49 | 1,289.49 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料8 待後續1 |

### CR-03｜電子廠 Class 1000

- 規格：{"area_m2": 1500, "height_m": 3.5, "room_t": 23, "room_rh": 50, "oa_cmh": 15000, "exhaust_cmh": 12000, "ach_kind": "循環", "ach": 70, "equip_kw": 600, "focus": "製程顯熱與除濕"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "en_L_A": "50", "en_W_A": "30", "en_H_A": "3.5", "ra_t": "23", "oa_rh": "65", "en_manual_oa": "15000", "gex_q": "12000", "exhaust_margin_pct": "0", "en_ach_A": "70", "eq_kw": "600", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0", "ffu_topology": "獨立FFU循環（MAU直接入室）"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 8、待後續 1）
- 警告：壓損 CHW、DCCW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 5,250 | 5,250 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 367,500 | 367,500 | 0 |  |
| G2 FFU count = ceil(circulation / unit airflow); unit 1000 CMH  | L1 | PASS | 368 | 368 | 0 |  |
| G3 MAU outdoor air is listed apart from the FFU circulation and | L1 | PASS | OA 15000 / FFU circulation 367500 | OA 15000 / FFU 367500 | 1.81899e-12 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 323.684 | 323.684 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 927.728 | 927.728 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料8 待後續1 |

### CR-04｜電子組裝 Class 10000

- 規格：{"area_m2": 1200, "height_m": 3.5, "room_t": 24, "room_rh": 50, "oa_cmh": 9000, "exhaust_cmh": 7500, "ach_kind": "循環", "ach": 35, "equip_kw": 250, "focus": "人員照明設備負荷"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "en_L_A": "40", "en_W_A": "30", "en_H_A": "3.5", "ra_t": "24", "oa_rh": "65", "en_manual_oa": "9000", "gex_q": "7500", "exhaust_margin_pct": "0", "en_ach_A": "35", "eq_kw": "250", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0", "ffu_topology": "獨立FFU循環（MAU直接入室）"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 8、待後續 1）
- 警告：壓損 CHW、DCCW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 4,200 | 4,200 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 147,000 | 147,000 | 0 |  |
| G2 FFU count = ceil(circulation / unit airflow); unit 1000 CMH  | L1 | PASS | 147 | 147 | 0 |  |
| G3 MAU outdoor air is listed apart from the FFU circulation and | L1 | PASS | OA 9000 / FFU circulation 147000 | OA 9000 / FFU 147000 | 0 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 185.799 | 185.799 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 532.528 | 532.528 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料8 待後續1 |

### CR-05｜潔淨包裝 Class 100000

- 規格：{"area_m2": 800, "height_m": 3.0, "room_t": 24, "room_rh": 55, "oa_cmh": 4000, "exhaust_cmh": 3200, "ach_kind": "循環", "ach": 20, "equip_kw": 80, "focus": "低ACH、正壓概念"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "en_L_A": "40", "en_W_A": "20", "en_H_A": "3", "ra_t": "24", "ra_rh": "55", "oa_rh": "65", "en_manual_oa": "4000", "gex_q": "3200", "exhaust_margin_pct": "0", "en_ach_A": "20", "eq_kw": "80", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0", "ffu_topology": "獨立FFU循環（MAU直接入室）"}`
- 結論：**BLOCKED**（第 2 層：BLOCKED）— engine refuses; the cause is verified independently | the plan omits the data the case needs (assumption A-CHW)
- 引擎訊息：乾盤管進水未達露點＋安全裕度
- BLOCKED 面向：正壓概念（規格未給壓差值，引擎只接受 >= 0 的壓差輸入）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| R1 refusal states a cause (an infeasible case is not silently a | L1 | PASS |  |  |  | 乾盤管進水未達露點＋安全裕度 |
| R1b refusal text names the limit it hit | L1 | PASS |  |  |  | OBS-1: the message is not labelled 未達條件 and gives no numbers (shown as an input error) |
| R2 dry-coil water must stay above room dew point + margin (defa | L1 | PASS | > 15.41 C | 14.0 C (engine default, assumption A-CHW) | -1.41098 |  |
| R3 the case needs a dry-coil water temperature the plan does no | L2 | BLOCKED |  |  |  | dry-coil supply water >= 15.41 C |

### CR-06｜半導體高排氣製程區

- 規格：{"area_m2": 1800, "height_m": 4.0, "room_t": 22, "room_rh": 45, "oa_cmh": 58000, "exhaust_cmh": 52000, "ach_kind": "循環", "ach": 120, "equip_kw": 1200, "focus": "補風、排氣、壓差與FFU"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "en_L_A": "60", "en_W_A": "30", "ra_rh": "45", "oa_rh": "65", "en_manual_oa": "58000", "gex_q": "52000", "exhaust_margin_pct": "0", "en_ach_A": "120", "eq_kw": "1200", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0", "ffu_topology": "獨立FFU循環（MAU直接入室）"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 8、待後續 1）
- 警告：壓損 CHW、DCCW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。
- BLOCKED 面向：壓差（規格未給漏風／開口資料；不得由 58000-52000 的風量差推定壓差）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 7,200 | 7,200 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 864,000 | 864,000 | 0 |  |
| G2 FFU count = ceil(circulation / unit airflow); unit 1000 CMH  | L1 | PASS | 864 | 864 | 0 |  |
| G3 MAU outdoor air is listed apart from the FFU circulation and | L1 | PASS | OA 58000 / FFU circulation 864000 | OA 58000 / FFU 864000 | 0 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 1,385.47 | 1,385.47 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 3,970.96 | 3,970.96 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料8 待後續1 |

### CR-07｜冬季無塵室加濕

- 規格：{"area_m2": 1000, "height_m": 3.0, "room_t": 22, "room_rh": 50, "oa_cmh": 12000, "exhaust_cmh": 10000, "ach_kind": "循環", "ach": 70, "equip_kw": 200, "focus": "冬季外氣5°C/70%RH；加熱加濕再熱"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "en_L_A": "40", "en_W_A": "25", "en_H_A": "3", "oa_rh": "65", "en_manual_oa": "12000", "gex_q": "10000", "exhaust_margin_pct": "0", "en_ach_A": "70", "eq_kw": "200", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0", "ow_t": "5", "ffu_topology": "獨立FFU循環（MAU直接入室）"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 8、待後續 1）
- 警告：壓損 CHW、DCCW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 3,000 | 3,000 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 210,000 | 210,000 | 0 |  |
| G2 FFU count = ceil(circulation / unit airflow); unit 1000 CMH  | L1 | PASS | 210 | 210 | 0 |  |
| G3 MAU outdoor air is listed apart from the FFU circulation and | L1 | PASS | OA 12000 / FFU circulation 210000 | OA 12000 / FFU 210000 | 0 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 269.942 | 269.942 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 773.696 | 773.696 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料8 待後續1 |

### CR-08｜夏季高濕無塵室

- 規格：{"area_m2": 1000, "height_m": 3.0, "room_t": 22, "room_rh": 45, "oa_cmh": 15000, "exhaust_cmh": 12000, "ach_kind": "循環", "ach": 120, "equip_kw": 300, "focus": "夏季外氣35°C/75%RH；除濕再熱"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "MAU+FFU+DCC (全外氣/無塵室)", "en_L_A": "40", "en_W_A": "25", "en_H_A": "3", "ra_rh": "45", "oa_rh": "75", "en_manual_oa": "15000", "gex_q": "12000", "exhaust_margin_pct": "0", "en_ach_A": "120", "eq_kw": "300", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0", "ffu_topology": "獨立FFU循環（MAU直接入室）"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 8、待後續 1）
- 警告：壓損 CHW、DCCW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 3,000 | 3,000 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 360,000 | 360,000 | 0 |  |
| G2 FFU count = ceil(circulation / unit airflow); unit 1000 CMH  | L1 | PASS | 360 | 360 | 0 |  |
| G3 MAU outdoor air is listed apart from the FFU circulation and | L1 | PASS | OA 15000 / FFU circulation 360000 | OA 15000 / FFU 360000 | 1.81899e-12 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.9e-08, RH 2.6e-13 | 2.86936e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 409.487 | 409.487 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 1,173.65 | 1,173.65 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料8 待後續1 |

### H-01｜醫院正壓手術室

- 規格：{"area_m2": 50, "height_m": 3.0, "room_t": 21, "room_rh": 50, "oa_cmh": 900, "exhaust_cmh": 750, "ach_kind": "送風", "ach": 20, "equip_kw": null, "focus": "換氣、外氣、正壓與濕度"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_L_A": "10", "en_W_A": "5", "en_H_A": "3", "ra_t": "21", "oa_rh": "65", "en_manual_oa": "900", "gex_q": "750", "exhaust_margin_pct": "0", "en_ach_A": "20", "eq_kw": "0", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 5、待後續 0）
- 警告：壓損 CHW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。
- BLOCKED 面向：手術室正壓值與感染控制（未給壓差值與漏風資料；規範未對應）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 150 | 150 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 3,000 | 3,000 | 0 |  |
| G2 FFU count | L1 | NOT APPLICABLE |  |  |  | system is not MAU+FFU+DCC |
| G3 outdoor air equals the stated OA; supply airflow is at least | L1 | PASS | OA 900; supply >= 3000 | OA 900; supply 3,000 | 0 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 7.1e-15, v 2.5e-08, RH 3.3e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 28.2363 | 28.2363 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 80.9296 | 80.9296 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料5 待後續0 |

### H-02｜醫院負壓隔離病房

- 規格：{"area_m2": 30, "height_m": 3.0, "room_t": 23, "room_rh": 50, "oa_cmh": 450, "exhaust_cmh": 600, "ach_kind": "送風", "ach": 12, "equip_kw": null, "focus": "負壓、排風與補風"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_L_A": "6", "en_W_A": "5", "en_H_A": "3", "ra_t": "23", "oa_rh": "65", "en_manual_oa": "450", "gex_q": "600", "exhaust_margin_pct": "0", "en_ach_A": "12", "eq_kw": "0", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**BLOCKED**（第 2 層：BLOCKED）— engine refuses; the cause is verified independently | 負壓、轉移風量與排風大於外氣
- 引擎訊息：指定外氣 450 低於補償下限 600.0 CMH

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| R1 refusal states a cause (an infeasible case is not silently a | L1 | PASS |  |  |  | 指定外氣 450 低於補償下限 600.0 CMH |
| R1b refusal text names the limit it hit | L1 | PASS |  |  |  | OBS-2: the message is not labelled 未達條件 (it does give the numbers) |
| R2 compensation floor = exhaust + leakage (leakage 0: no pressu | L1 | PASS | 600 | 600 | 0 |  |
| R3 outdoor air below the exhaust: make-up must come from transf | L2 | BLOCKED | OA >= exhaust (600 CMH) | OA 450 CMH |  | not a defect: the plan case needs a transfer-air / negative-pressure model |

### H-03｜醫院保護性環境病房

- 規格：{"area_m2": 35, "height_m": 3.0, "room_t": 22, "room_rh": 45, "oa_cmh": 500, "exhaust_cmh": 350, "ach_kind": "送風", "ach": 12, "equip_kw": null, "focus": "正壓與潔淨送風"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_L_A": "7", "en_W_A": "5", "en_H_A": "3", "ra_rh": "45", "oa_rh": "65", "en_manual_oa": "500", "gex_q": "350", "exhaust_margin_pct": "0", "en_ach_A": "12", "eq_kw": "0", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 5、待後續 0）
- 警告：壓損 CHW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。
- BLOCKED 面向：保護性環境正壓值（未給壓差值與漏風資料；規範未對應）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 105 | 105 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 1,260 | 1,260 | 0 |  |
| G2 FFU count | L1 | NOT APPLICABLE |  |  |  | system is not MAU+FFU+DCC |
| G3 outdoor air equals the stated OA; supply airflow is at least | L1 | PASS | OA 500; supply >= 1260 | OA 500; supply 1,260 | 0 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 15.1945 | 15.1945 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 43.5498 | 43.5498 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料5 待後續0 |

### H-04｜醫院檢驗實驗室

- 規格：{"area_m2": 150, "height_m": 3.0, "room_t": 23, "room_rh": 50, "oa_cmh": 2500, "exhaust_cmh": 3000, "ach_kind": "送風", "ach": 12, "equip_kw": null, "focus": "排風櫃與補風"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_L_A": "15", "en_W_A": "10", "en_H_A": "3", "ra_t": "23", "oa_rh": "65", "en_manual_oa": "2500", "gex_q": "3000", "exhaust_margin_pct": "0", "en_ach_A": "12", "eq_kw": "0", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**BLOCKED**（第 2 層：BLOCKED）— engine refuses; the cause is verified independently | 排風櫃補風與轉移風量；排風大於外氣
- 引擎訊息：指定外氣 2500 低於補償下限 3000.0 CMH

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| R1 refusal states a cause (an infeasible case is not silently a | L1 | PASS |  |  |  | 指定外氣 2500 低於補償下限 3000.0 CMH |
| R1b refusal text names the limit it hit | L1 | PASS |  |  |  | OBS-2: the message is not labelled 未達條件 (it does give the numbers) |
| R2 compensation floor = exhaust + leakage (leakage 0: no pressu | L1 | PASS | 3000 | 3,000 | 0 |  |
| R3 outdoor air below the exhaust: make-up must come from transf | L2 | BLOCKED | OA >= exhaust (3000 CMH) | OA 2500 CMH |  | not a defect: the plan case needs a transfer-air / negative-pressure model |

### P-01｜無菌藥品灌裝背景區

- 規格：{"area_m2": 200, "height_m": 3.0, "room_t": 20, "room_rh": 45, "oa_cmh": 3000, "exhaust_cmh": 2500, "ach_kind": "送風", "ach": 40, "equip_kw": null, "focus": "背景環境及局部ISO 5分開驗證"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_W_A": "10", "en_H_A": "3", "ra_t": "20", "ra_rh": "45", "oa_rh": "65", "en_manual_oa": "3000", "gex_q": "2500", "exhaust_margin_pct": "0", "en_ach_A": "40", "eq_kw": "0", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**BLOCKED**（第 2 層：BLOCKED）— engine refuses; the cause is verified independently | the plan omits the data the case needs (assumption A-CHW)
- 引擎訊息：未達條件：盤管最低可達含濕量 6.656 g/kg（冰水供水＋ADP 裕度 8.00°C）不低於室內含濕量 6.528 g/kg（露點 7.72°C），任何風量都無法除濕；冰水供水溫度須低於 6.72°C，或提高室內相對濕度目標
- BLOCKED 面向：局部 ISO 5（背景 ACH 不能推定局部 ISO 5；引擎沒有局部潔淨區模型）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| R1 refusal states a cause (an infeasible case is not silently a | L1 | PASS |  |  |  | 未達條件：盤管最低可達含濕量 6.656 g/kg（冰水供水＋ADP 裕度 8.00°C）不低於室內含濕量 6.528 g/kg（露點 7.72°C），任何風量都無法除濕；冰水供水 |
| R1b refusal text names the limit it hit | L1 | PASS |  |  |  | labelled 未達條件 |
| R2 room humidity ratio below the saturation humidity at the ADP | L1 | PASS | w_adp 6.656 >= w_room 6.528 g/kg | 未達條件：盤管最低可達含濕量 6.656 g/kg（冰水供水＋ADP 裕度 8.00°C）不低於室內含濕量 6.528 g/kg（露點 7.72°C），任何風量都無法除濕；冰水供水溫度須低於 6.72°C，或提高室內相對濕度目標 | 0.127753 |  |
| R3 the case needs chilled water the plan does not give | L2 | BLOCKED |  |  |  | chilled-water supply below 6.72 C (room dew point 7.72 C - 1 K approach) |

### P-02｜藥廠潔淨走廊

- 規格：{"area_m2": 300, "height_m": 3.0, "room_t": 22, "room_rh": 50, "oa_cmh": 2000, "exhaust_cmh": 1600, "ach_kind": "送風", "ach": 20, "equip_kw": null, "focus": "壓差梯度、門開啟影響"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_L_A": "30", "en_W_A": "10", "en_H_A": "3", "oa_rh": "65", "en_manual_oa": "2000", "gex_q": "1600", "exhaust_margin_pct": "0", "en_ach_A": "20", "eq_kw": "0", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 5、待後續 0）
- 警告：壓損 CHW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。
- BLOCKED 面向：壓差梯度與門開啟影響（未給門縫、開門次數與壓差值）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 900 | 900 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 18,000 | 18,000 | 0 |  |
| G2 FFU count | L1 | NOT APPLICABLE |  |  |  | system is not MAU+FFU+DCC |
| G3 outdoor air equals the stated OA; supply airflow is at least | L1 | PASS | OA 2000; supply >= 18000 | OA 2000; supply 18,000 | 0 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 79.8003 | 79.8003 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 228.72 | 228.72 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料5 待後續0 |

### P-03｜生技細胞培養室

- 規格：{"area_m2": 120, "height_m": 3.0, "room_t": 22, "room_rh": 50, "oa_cmh": 1500, "exhaust_cmh": 1200, "ach_kind": "送風", "ach": 20, "equip_kw": null, "focus": "潔淨送風與溫濕度"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_L_A": "12", "en_W_A": "10", "en_H_A": "3", "oa_rh": "65", "en_manual_oa": "1500", "gex_q": "1200", "exhaust_margin_pct": "0", "en_ach_A": "20", "eq_kw": "0", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 5、待後續 0）
- 警告：壓損 CHW、HW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 360 | 360 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 7,200 | 7,200 | 0 |  |
| G2 FFU count | L1 | NOT APPLICABLE |  |  |  | system is not MAU+FFU+DCC |
| G3 outdoor air equals the stated OA; supply airflow is at least | L1 | PASS | OA 1500; supply >= 7200 | OA 1500; supply 7,200 | 0 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 49.871 | 49.871 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 142.938 | 142.938 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料5 待後續0 |

### D-01｜資料中心伺服器機房

- 規格：{"area_m2": 500, "height_m": 3.5, "room_t": 24, "room_rh": 45, "oa_cmh": 1500, "exhaust_cmh": 1200, "ach_kind": null, "ach": null, "equip_kw": 600, "focus": "高顯熱、設備備援"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "RCU (機房空調箱+外氣)", "en_L_A": "25", "en_W_A": "20", "en_H_A": "3.5", "ra_t": "24", "ra_rh": "45", "oa_rh": "65", "en_manual_oa": "1500", "gex_q": "1200", "exhaust_margin_pct": "0", "en_ach_A": "0", "eq_kw": "600", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 5、待後續 1）
- 警告：FCU／RCU 採外氣於入口混入的等效控制體；實際外氣另接 MAU 時需另設系統拓樸。
- 警告：壓損 CHW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。
- BLOCKED 面向：設備備援（N+1）（引擎沒有備援欄位；台數是無備援需求值）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 1,750 | 1,750 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 0 | 0 | 0 | ACH not specified: no floor |
| G2 FFU count | L1 | NOT APPLICABLE |  |  |  | system is not MAU+FFU+DCC |
| G3 outdoor air equals the stated OA; supply airflow is at least | L1 | PASS | OA 1500; supply >= 0 | OA 1500; supply 184,270 | 184,270 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 686.155 | 686.155 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 1,966.62 | 1,966.62 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料5 待後續1 |

### D-02｜UPS／電池設備室

- 規格：{"area_m2": 100, "height_m": 3.0, "room_t": 25, "room_rh": 50, "oa_cmh": 1000, "exhaust_cmh": 900, "ach_kind": null, "ach": null, "equip_kw": 60, "focus": "UPS散熱；電池安全通風另核"}
- 對映到引擎的輸入（只列與預設不同者）：`{"sys_type": "RCU (機房空調箱+外氣)", "en_L_A": "10", "en_W_A": "10", "en_H_A": "3", "ra_t": "25", "oa_rh": "65", "en_manual_oa": "1000", "gex_q": "900", "exhaust_margin_pct": "0", "en_ach_A": "0", "eq_kw": "60", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 5、待後續 1）
- 警告：FCU／RCU 採外氣於入口混入的等效控制體；實際外氣另接 MAU 時需另設系統拓樸。
- 警告：壓損 CHW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。
- BLOCKED 面向：電池安全通風（引擎沒有電池化學種類、充放電與氫氣排放模型；顯熱不能證明通風安全）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 300 | 300 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 0 | 0 | 0 | ACH not specified: no floor |
| G2 FFU count | L1 | NOT APPLICABLE |  |  |  | system is not MAU+FFU+DCC |
| G3 outdoor air equals the stated OA; supply airflow is at least | L1 | PASS | OA 1000; supply >= 0 | OA 1000; supply 18,534 | 18,533.7 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 81.6007 | 81.6007 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 233.88 | 233.88 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料5 待後續1 |

### F-01｜一般電子製造廠

- 規格：{"area_m2": 2000, "height_m": 5.0, "room_t": 26, "room_rh": 55, "oa_cmh": 20000, "exhaust_cmh": 18000, "ach_kind": null, "ach": null, "equip_kw": 500, "focus": "工業負荷與空調選型"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_L_A": "50", "en_W_A": "40", "en_H_A": "5", "ra_t": "26", "ra_rh": "55", "oa_rh": "65", "en_manual_oa": "20000", "gex_q": "18000", "exhaust_margin_pct": "0", "en_ach_A": "0", "eq_kw": "500", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 5、待後續 1）
- 警告：壓損 CHW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 10,000 | 10,000 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 0 | 0 | 0 | ACH not specified: no floor |
| G2 FFU count | L1 | NOT APPLICABLE |  |  |  | system is not MAU+FFU+DCC |
| G3 outdoor air equals the stated OA; supply airflow is at least | L1 | PASS | OA 20000; supply >= 0 | OA 20000; supply 155,379 | 155,379 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 2.1e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 822.903 | 822.903 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 2,358.56 | 2,358.56 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料5 待後續1 |

### F-02｜精密量測恆溫室

- 規格：{"area_m2": 200, "height_m": 3.0, "room_t": 22, "room_rh": 50, "oa_cmh": 1500, "exhaust_cmh": 1200, "ach_kind": null, "ach": null, "equip_kw": 30, "focus": "小溫差、精度及控制穩定性（22±0.5）"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_W_A": "10", "en_H_A": "3", "oa_rh": "65", "en_manual_oa": "1500", "gex_q": "1200", "exhaust_margin_pct": "0", "en_ach_A": "0", "eq_kw": "30", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**PASS**（第 2 層：no engineering concern found by the independent checks）— calculation implementation only (layer 1); selection reasonableness is layer 2; code compliance is NOT VERIFIED
- 品質閘門：待補資料（未達 0、待資料 5、待後續 1）
- 警告：壓損 CHW、GEX 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。
- 警告：加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。
- BLOCKED 面向：±0.5°C 控制精度與穩定性（引擎是穩態需求計算，沒有控制回路模型）

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| G1 room volume = area x height | L1 | PASS | 600 | 600 | 0 |  |
| G1b circulation / supply airflow Q = V x ACH | L1 | PASS | 0 | 0 | 0 | ACH not specified: no floor |
| G2 FFU count | L1 | NOT APPLICABLE |  |  |  | system is not MAU+FFU+DCC |
| G3 outdoor air equals the stated OA; supply airflow is at least | L1 | PASS | OA 1500; supply >= 0 | OA 1500; supply 9,150 | 9,149.57 |  |
| G4 17 moist-air states against PsychroLib 2.5.0 (ASHRAE, same f | L1 | PASS | h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 % | h 0, v 2.5e-08, RH 3.3e-13 | 2.47245e-08 | validates the implementation; the applicable range is -60..90 C and 60..120 kPa |
| G5 coil air side = m x dh; water side = air side - condensate h | L1 | PASS | balances to 1e-6 kW | 0 violations |  |  |
| G6 design margin is applied once per loop (CHW = coil water loa | L1 | PASS | 60.6883 | 60.6883 | 0 | margin 10 % |
| G8a chilled-water flow = load / (rho cp dT) | L1 | PASS | 173.942 | 173.942 | 0 |  |
| G11 a physically / geometrically impossible result is 未達條件, not  | L1 | PASS | any | 待補資料 |  | no impossible condition found independently | items 未達0 待資料5 待後續1 |

### F-03｜高溫高濕工業製程區

- 規格：{"area_m2": 600, "height_m": 4.0, "room_t": 28, "room_rh": 60, "oa_cmh": 15000, "exhaust_cmh": 18000, "ach_kind": null, "ach": null, "equip_kw": 300, "focus": "高濕、排氣大於外氣、補風"}
- 對映到引擎的輸入（只列與預設不同者）：`{"en_L_A": "30", "en_W_A": "20", "ra_t": "28", "ra_rh": "60", "oa_rh": "65", "en_manual_oa": "15000", "gex_q": "18000", "exhaust_margin_pct": "0", "en_ach_A": "0", "eq_kw": "300", "eq_rt": "100", "ppl_A": "0", "light_lux": "0", "en_wall": "0", "en_floor": "0", "process_latent_kw": "0"}`
- 結論：**BLOCKED**（第 2 層：BLOCKED）— engine refuses; the cause is verified independently | 排氣大於外氣的補風來源
- 引擎訊息：指定外氣 15000 低於補償下限 18000.0 CMH

| 檢核 | 層 | 狀態 | 預期（獨立計算） | 引擎 | 誤差 | 備註 |
|---|---|---|---|---|---|---|
| R1 refusal states a cause (an infeasible case is not silently a | L1 | PASS |  |  |  | 指定外氣 15000 低於補償下限 18000.0 CMH |
| R1b refusal text names the limit it hit | L1 | PASS |  |  |  | OBS-2: the message is not labelled 未達條件 (it does give the numbers) |
| R2 compensation floor = exhaust + leakage (leakage 0: no pressu | L1 | PASS | 18000 | 18,000 | 0 |  |
| R3 outdoor air below the exhaust: make-up must come from transf | L2 | BLOCKED | OA >= exhaust (18000 CMH) | OA 15000 CMH |  | not a defect: the plan case needs a transfer-air / negative-pressure model |

### 非案例探針（明確標示，不是計畫案例）

- CR-05：dry-coil supply water raised to the advice (dew point 14.4 C + 1 K margin -> 15.5 C) → accepted（待補資料）。NOT the plan case: checks that the engine's stated remedy works
- P-01：chilled water lowered to the advice (below dew point 7.72 C - 1 K -> 6.5 C) → accepted（待補資料）。NOT the plan case: checks that the engine's stated remedy works

## 5. 五組非隨機邊界掃描

### S-01｜CR-08｜PASS

- 結果：12/16 accepted; edge 8.53 C; max airflow 15,000 CMH; MAU supply dT is 0 by design (mau_supply_t = room T), the airflow stays the stated OA
- 步階選取依據與實際步長：chilled-water supply 5.0-8.0 C in 0.5 K steps (usual operating range, one reset increment), then 0.1 K to 8.6 and 0.05 K near the predicted edge 8.53 C = room dew point 9.53 C - 1 K approach; 8.7 and 8.8 beyond it
- 先於引擎給出的預測：MAU: accepted while ADP <= supply dew point (chw <= edge); AHU search: accepted while the room humidity ratio is above the saturation ratio at the ADP (chw < edge)
- 預測與引擎不一致項：無

| 步階 | 預測 | 引擎 | 狀態 |
|---|---|---|---|
| chw 5 C | 接受 | 接受 | 待補資料 |
| chw 5.5 C | 接受 | 接受 | 待補資料 |
| chw 6 C | 接受 | 接受 | 待補資料 |
| chw 6.5 C | 接受 | 接受 | 待補資料 |
| chw 7 C | 接受 | 接受 | 待補資料 |
| chw 7.5 C | 接受 | 接受 | 待補資料 |
| chw 8 C | 接受 | 接受 | 待補資料 |
| chw 8.1 C | 接受 | 接受 | 待補資料 |
| chw 8.2 C | 接受 | 接受 | 待補資料 |
| chw 8.3 C | 接受 | 接受 | 待補資料 |
| chw 8.4 C | 接受 | 接受 | 待補資料 |
| chw 8.5 C | 接受 | 接受 | 待補資料 |
| chw 8.6 C | 拒絕 | 拒絕 | 冷卻盤管所需露點低於供水＋ADP 裕度；需增加可用除濕風量或降低供水溫度 |
| chw 8.65 C | 拒絕 | 拒絕 | 冷卻盤管所需露點低於供水＋ADP 裕度；需增加可用除濕風量或降低供水溫度 |
| chw 8.7 C | 拒絕 | 拒絕 | 冷卻盤管所需露點低於供水＋ADP 裕度；需增加可用除濕風量或降低供水溫度 |
| chw 8.8 C | 拒絕 | 拒絕 | 冷卻盤管所需露點低於供水＋ADP 裕度；需增加可用除濕風量或降低供水溫度 |

### S-01b｜CR-08 room in a mixed-air AHU (extra variant, not in the plan)｜PASS

- 結果：12/16 accepted; edge 8.53 C; max airflow 360,000 CMH; airflow rises smoothly, impractical steps are 未達條件
- 步階選取依據與實際步長：chilled-water supply 5.0-8.0 C in 0.5 K steps (usual operating range, one reset increment), then 0.1 K to 8.6 and 0.05 K near the predicted edge 8.53 C = room dew point 9.53 C - 1 K approach; 8.7 and 8.8 beyond it
- 先於引擎給出的預測：MAU: accepted while ADP <= supply dew point (chw <= edge); AHU search: accepted while the room humidity ratio is above the saturation ratio at the ADP (chw < edge)
- 預測與引擎不一致項：無

| 步階 | 預測 | 引擎 | 狀態 |
|---|---|---|---|
| chw 5 C | 接受 | 接受 | 待補資料 |
| chw 5.5 C | 接受 | 接受 | 待補資料 |
| chw 6 C | 接受 | 接受 | 待補資料 |
| chw 6.5 C | 接受 | 接受 | 待補資料 |
| chw 7 C | 接受 | 接受 | 待補資料 |
| chw 7.5 C | 接受 | 接受 | 待補資料 |
| chw 8 C | 接受 | 接受 | 待補資料 |
| chw 8.1 C | 接受 | 接受 | 待補資料 |
| chw 8.2 C | 接受 | 接受 | 待補資料 |
| chw 8.3 C | 接受 | 接受 | 待補資料 |
| chw 8.4 C | 接受 | 接受 | 待補資料 |
| chw 8.5 C | 接受 | 接受 | 待補資料 |
| chw 8.6 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 7.426 g/kg（冰水供水＋ADP 裕度 9.60°C）不低於室內 |
| chw 8.65 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 7.451 g/kg（冰水供水＋ADP 裕度 9.65°C）不低於室內 |
| chw 8.7 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 7.476 g/kg（冰水供水＋ADP 裕度 9.70°C）不低於室內 |
| chw 8.8 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 7.527 g/kg（冰水供水＋ADP 裕度 9.80°C）不低於室內 |

### S-02｜CR-06｜PASS

- 結果：6/10 accepted; engine refuses exhaust above the make-up (error, not a warning); leakage stays 0 CMH; with automatic OA the engine sets OA = exhaust
- 步階選取依據與實際步長：exhaust 40,000-70,000 CMH: 77 % to 135 % of the stated 58,000 CMH make-up; 6,000 CMH steps to the case value 52,000, then 3,000 to 1,000 CMH steps around the make-up limit, then 4,000-6,000 beyond
- 先於引擎給出的預測：accepted while exhaust <= stated outdoor air (compensation floor = exhaust + leakage; leakage 0 because no pressure / gap data); refusal must quote the floor; no pressure may be inferred
- 預測與引擎不一致項：無

| 步階 | 預測 | 引擎 | 狀態 |
|---|---|---|---|
| exhaust 40000 | 接受 | 接受 | 待補資料 |
| exhaust 46000 | 接受 | 接受 | 待補資料 |
| exhaust 52000 | 接受 | 接受 | 待補資料 |
| exhaust 55000 | 接受 | 接受 | 待補資料 |
| exhaust 57000 | 接受 | 接受 | 待補資料 |
| exhaust 58000 | 接受 | 接受 | 待補資料 |
| exhaust 58500 | 拒絕 | 拒絕 | 指定外氣 58000 低於補償下限 58500.0 CMH |
| exhaust 60000 | 拒絕 | 拒絕 | 指定外氣 58000 低於補償下限 60000.0 CMH |
| exhaust 64000 | 拒絕 | 拒絕 | 指定外氣 58000 低於補償下限 64000.0 CMH |
| exhaust 70000 | 拒絕 | 拒絕 | 指定外氣 58000 低於補償下限 70000.0 CMH |

### S-03｜CR-01｜PASS

- 結果：count follows ceil(Q/unit) on all 16 steps; 500 ACH accepted and not capped; the 1200x600 module fits (<=85 %) only at >= 1271 ... units, otherwise the engine reports 未達條件
- 步階選取依據與實際步長：effective airflow per FFU 600-1,400 CMH (60 %-140 % of the 1,000 CMH default: filter loading, fan derating, a higher-flow module) in 100-200 CMH steps; both nominal sizes
- 先於引擎給出的預測：count = ceil(1,500,000 / unit airflow); coverage = count x module area / 1,000 m2; status 未達條件 whenever coverage > 85 %; 500 ACH is never capped
- 預測與引擎不一致項：無
- BLOCKED：FFU resistance / operating point — the engine has one effective airflow per FFU, no resistance or fan curve
- BLOCKED：failed units and redundancy — no input; the external table above (computed by the tester, not the engine) shows the installed count and shortfall for k failed units

測試者以外部公式（非引擎）計算的故障台數表（安裝台數 = ceil(Q/單台)+故障台數）：

| 故障台數 | 需安裝台數 | 可用風量 CMH | 缺口 CMH |
|---|---|---|---|
| 0 | 1500 | 1,500,000 | 0 |
| 1 | 1501 | 1,499,000 | 1,000 |
| 2 | 1502 | 1,498,000 | 2,000 |
| 5 | 1505 | 1,495,000 | 5,000 |
| 15 | 1515 | 1,485,000 | 15,000 |
| 75 | 1575 | 1,425,000 | 75,000 |

| 步階 | 預測 | 引擎 | 狀態 |
|---|---|---|---|
| 1200x600  600 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x600  700 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x600  800 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x600  900 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x600  1000 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x600  1100 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x600  1200 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x600  1400 CMH/unit | 接受 | 接受 | 待補資料 |
| 1200x1200 600 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x1200 700 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x1200 800 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x1200 900 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x1200 1000 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x1200 1100 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x1200 1200 CMH/unit | 接受 | 接受 | 未達條件 |
| 1200x1200 1400 CMH/unit | 接受 | 接受 | 未達條件 |

### S-04｜H-02｜PASS

- 結果：4/9 accepted (exhaust <= 450); the stated case (exhaust 600 > OA 450) is refused with the shortfall; the engine never claims a negative-pressure Pa value
- 步階選取依據與實際步長：exhaust 300-700 CMH in 50 CMH steps (about 11 % of the 450 CMH outdoor air) around the stated 450 CMH make-up and the case value 600; supply fixed at 12 ACH x 90 m3 = 1,080 CMH
- 先於引擎給出的預測：accepted while exhaust <= outdoor air 450 CMH; refusal names the shortfall; no negative pressure, no Pa value, no leakage is inferred
- 預測與引擎不一致項：無
- BLOCKED：negative pressure and its direction — en_p_A accepts only >= 0 Pa against a common low-pressure area; there is no negative-pressure, transfer-air or door model
- BLOCKED：door opening — the plan gives no door size or opening frequency (the engine inputs exist but stay at 0)

| 步階 | 預測 | 引擎 | 狀態 |
|---|---|---|---|
| exhaust 300 | 接受 | 接受 | 待補資料 |
| exhaust 350 | 接受 | 接受 | 待補資料 |
| exhaust 400 | 接受 | 接受 | 待補資料 |
| exhaust 450 | 接受 | 接受 | 待補資料 |
| exhaust 500 | 拒絕 | 拒絕 | 指定外氣 450 低於補償下限 500.0 CMH |
| exhaust 550 | 拒絕 | 拒絕 | 指定外氣 450 低於補償下限 550.0 CMH |
| exhaust 600 | 拒絕 | 拒絕 | 指定外氣 450 低於補償下限 600.0 CMH |
| exhaust 650 | 拒絕 | 拒絕 | 指定外氣 450 低於補償下限 650.0 CMH |
| exhaust 700 | 拒絕 | 拒絕 | 指定外氣 450 低於補償下限 700.0 CMH |

### S-05｜F-02｜PASS

- 結果：24/30 accepted; airflow rises smoothly toward the edge for every load; beyond the edge the engine refuses with the cause
- 步階選取依據與實際步長：chilled-water supply 7.0-10.2 C (available dT = room 22 C - ADP: 14 K down to 2.8 K): 1 K steps, then 0.5 K, 0.2-0.3 K and 0.05 K approaching the predicted edge 10.11 C (room dew point 11.11 C - 1 K); sensible load 30 / 100 / 300 kW (x1, x3.3, x10)
- 先於引擎給出的預測：accepted while chw < edge; airflow never below Q = m cp dT for the sensible load; non-decreasing as the available dT shrinks and as the load rises; impractical airflow is 未達條件
- 預測與引擎不一致項：無
- BLOCKED：+-0.5 C control accuracy and stability — steady-state demand calculation; no control loop, sensor or valve model

| 步階 | 預測 | 引擎 | 狀態 |
|---|---|---|---|
| eq 30 kW, chw 7 C | 接受 | 接受 | 待補資料 |
| eq 30 kW, chw 8 C | 接受 | 接受 | 待補資料 |
| eq 30 kW, chw 9 C | 接受 | 接受 | 待補資料 |
| eq 30 kW, chw 9.5 C | 接受 | 接受 | 待補資料 |
| eq 30 kW, chw 9.8 C | 接受 | 接受 | 待補資料 |
| eq 30 kW, chw 10 C | 接受 | 接受 | 待補資料 |
| eq 30 kW, chw 10.05 C | 接受 | 接受 | 待補資料 |
| eq 30 kW, chw 10.1 C | 接受 | 接受 | 待補資料 |
| eq 30 kW, chw 10.15 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 8.246 g/kg（冰水供水＋ADP 裕度 11.15°C）不低於室 |
| eq 30 kW, chw 10.2 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 8.274 g/kg（冰水供水＋ADP 裕度 11.20°C）不低於室 |
| eq 100 kW, chw 7 C | 接受 | 接受 | 待補資料 |
| eq 100 kW, chw 8 C | 接受 | 接受 | 待補資料 |
| eq 100 kW, chw 9 C | 接受 | 接受 | 待補資料 |
| eq 100 kW, chw 9.5 C | 接受 | 接受 | 待補資料 |
| eq 100 kW, chw 9.8 C | 接受 | 接受 | 待補資料 |
| eq 100 kW, chw 10 C | 接受 | 接受 | 待補資料 |
| eq 100 kW, chw 10.05 C | 接受 | 接受 | 待補資料 |
| eq 100 kW, chw 10.1 C | 接受 | 接受 | 待補資料 |
| eq 100 kW, chw 10.15 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 8.246 g/kg（冰水供水＋ADP 裕度 11.15°C）不低於室 |
| eq 100 kW, chw 10.2 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 8.274 g/kg（冰水供水＋ADP 裕度 11.20°C）不低於室 |
| eq 300 kW, chw 7 C | 接受 | 接受 | 待補資料 |
| eq 300 kW, chw 8 C | 接受 | 接受 | 待補資料 |
| eq 300 kW, chw 9 C | 接受 | 接受 | 待補資料 |
| eq 300 kW, chw 9.5 C | 接受 | 接受 | 待補資料 |
| eq 300 kW, chw 9.8 C | 接受 | 接受 | 待補資料 |
| eq 300 kW, chw 10 C | 接受 | 接受 | 待補資料 |
| eq 300 kW, chw 10.05 C | 接受 | 接受 | 待補資料 |
| eq 300 kW, chw 10.1 C | 接受 | 接受 | 待補資料 |
| eq 300 kW, chw 10.15 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 8.246 g/kg（冰水供水＋ADP 裕度 11.15°C）不低於室 |
| eq 300 kW, chw 10.2 C | 拒絕 | 拒絕 | 未達條件：盤管最低可達含濕量 8.274 g/kg（冰水供水＋ADP 裕度 11.20°C）不低於室 |

## 6. 優先缺陷驗證

| 編號 | 項目 | 狀態 | 說明 |
|---|---|---|---|
| PD-1a | F-1 reproducer on the current branch is refused, not solved | PASS | current: {"ok": false, "msg": "未達條件：盤管最低可達含濕量 6.683 g/kg（冰水供水＋ADP 裕度 8.06°C）不低於室內含濕量 6.562 g/kg（露點 7.79°C），任何風量都無法除濕；冰水供水溫度須低於 6.79°C，或提高室內相對濕度目標"} |
| PD-1b | F-1 reproducer on the imported baseline (before the fix) | PASS | baseline: {"ok": true, "cmh": 7411601864.864676, "status": "待補資料"}  -> defect reproduced (> 1e9 CMH accepted) |
| PD-1c | the exact input behind the 7,412,540,040 CMH observation | BLOCKED | the plan gives the output but not the input; the recorded reproducer above is the same failure mode (limit point at infinity) |
| PD-2a | gate reaches 初估完成 when all user-suppliable data is given (D-01 inputs + latent/N | PASS | status=初估完成（待後續階段確認）; remaining=[('待後續', '設備同工況選型'), ('待後續', '配電候選覆核')] |
| PD-2b | with default data the gate says 待補資料 and lists the items | PASS | status=待補資料 pending=5 |
| PD-2c | 初估檢核通過 (the top status) with zero loads | BLOCKED | zero-load status=待補資料; with any load 設備同工況選型 is always 待後續 so the top status is not reachable in practice |
| PD-2d | DESIGN OBSERVATION: 初估檢核通過 is unreachable for any real room | NOT APPLICABLE | by design (quality.py: 設備同工況選型 is 待後續 whenever qs or ql is non-zero). The earlier 'never PASS' complaint is resolved as a label problem: the reachable top status is 初估完成（待後續階段確認）. Whether 初估檢核通過 should exist is a product decision, not a calculation fault. |
| PD-3a | margin arithmetic: coil load x sf = design load, applied once per loop (check G6 | PASS | G6 results: 15 cases, ['PASS']; sf=10.0, CR-03 CHW load 323.684 kW (run run_scenarios.py first) |
| PD-3b | report labels loads before / after the margin and states the margin percentage ( | PASS | 未加餘裕 / 含餘裕 / '10%' all present |
| PD-3c | report labels the margin and its percentage (en) | PASS | [Selection target]  Target with margin 323.68 kW / 92.04 US RT;  Actua / [Calculated requirement]  Seasonal coincident cooling peak (before saf |
| PD-4a | wall load follows the selected U-value unit (hand calc: U x A x dT) | PASS | kcal/(h·m²·K): engine 0.6978 vs 0.697800 kW; W/(m²·K): engine 0.6 vs 0.600000 kW |
| PD-4b | the U-value field itself shows its unit | FAIL | FIELDS['wall_u'] unit='', label='外牆 U 值'; the unit lives in a separate selector (u_unit, default 'kcal/(h·m²·K)'). Entering a W/(m2.K) value while the default kcal unit is selected under-states the load by 14 % (1/1.163) with no warning. |
| PD-4c | the report prints the U-value unit next to the wall load | FAIL | the report prints the wall load in kW but never the U value or its unit, and FIELD_HELP has no hint for wall_u / floor_u / u_unit |
| PD-5a | field envelope covers the per-unit ranges | PASS | field 0.133322..1013.25; per unit 1-760 Torr = 0.1333-101.325 kPa = 1.333-1013.25 mbar |
| PD-5b | per-unit boundary values are accepted / refused consistently (12 values) | PASS | all 12 boundary checks as expected |
| PD-5c | the field hint states the per-unit ranges | PASS | 全部為絕對壓力；150 Torr ≈ 20.00 kPa ≈ 199.98 mbar。允許範圍依所選單位：1～760 Torr ≈ 0.1333～101.325 kPa ≈ 1.333～1013.25 mbar。 |

## 7. 三層結論

| 層 | 結論 |
|---|---|
| 1 計算實作 | 15 案 PASS：幾何、風量、FFU 台數、濕空氣狀態（PsychroLib）、盤管能量收支、餘裕只加一次、水力（Colebrook）、冬季加濕收支（CR-07）、中英文報告數字一致；5 案引擎拒絕（原因經獨立驗算）→ BLOCKED；5 組掃描與預測一致 |
| 2 工程選型合理性 | CR-01 在預設 FFU 下覆蓋率 108 % → 不可行（引擎已標示）；H／P 4 案缺負荷資料，選型合理性**無法判斷**；D／F 案在預設 7 °C 冰水下有除濕，資料中心實務常用較高水溫，屬待確認；其餘 CR 案未發現獨立檢核能指出的問題。不等於合理，只是這些檢核沒找到問題 |
| 3 規範符合性 | **NOT VERIFIED**。未對照任何規範版本、設計輸入與審核證據，不得宣稱符合 FEED、醫院感染控制、藥廠 GMP、無塵室等級或電氣法規 |

## 8. 整體問題清單

### ISS-1｜U 值單位易誤解｜嚴重度 M｜FAIL
- 來源：PD-4b, PD-4c
- 說明：預設單位 kcal/(h·m²·K)；欄位本身無單位、無提示文字，報告只列牆體負荷 kW，不列 U 值與單位。把 W/(m²·K) 的數值填進預設單位，牆／樓板負荷會少算 14 %（1/1.163）且完全沒有警告。計算本身正確（PD-4a，兩種單位皆與手算一致）。
- 最小重現：最小重現：en_wall=100, wall_u=0.5, 其餘同 CR-03，u_unit 維持預設 → 外牆 0.6978 kW；若使用者意圖是 W/(m²·K) 則應為 0.6000 kW。
- 可能根因：欄位與單位選擇器分離，且 FIELD_HELP 沒有 wall_u／floor_u／u_unit 條目，報告不回印輸入。
- 修正建議：把單位直接顯示在 U 值欄位標籤；加 FIELD_HELP；報告在負荷組成中回印 U 值與單位；單位切換時提示是否換算數值。

### ISS-2｜拒絕訊息未標示為「未達條件」，且 CR-05 無數字｜嚴重度 L｜FAIL
- 來源：OBS-1 (CR-05), OBS-2 (H-02, H-04, F-03)
- 說明：外氣低於補償下限與乾盤管進水未達露點的拒絕，以輸入錯誤顯示，不是「未達條件」；CR-05 訊息只有「乾盤管進水未達露點＋安全裕度」，不含水溫、露點與需要值。原因經獨立驗算皆正確（R2 PASS），所以是呈現問題，不是計算問題。
- 最小重現：CR-05 輸入（見 results.json）→ ValidationError 14 字訊息；H-02 → 「指定外氣 450 低於補償下限 600.0 CMH」。
- 可能根因：這幾條檢核早於 F-1 防護，訊息格式沒有統一。
- 修正建議：統一訊息格式：未達條件＋原因＋實際值／需要值＋可調整的欄位（P-01 的訊息已是這個格式，可作範本）。

### ISS-3｜「初估檢核通過」對任何有負荷的房間都到不了｜嚴重度 L｜NOT APPLICABLE
- 來源：PD-2a, PD-2c, PD-2d
- 說明：只要顯熱或潛熱不為 0，「設備同工況選型」永遠是待後續，所以最高只到「初估完成（待後續階段確認）」。這已是刻意設計，且 PD-2a 證明補齊使用者能補的資料後可以到達該狀態；原本『永遠無法 PASS』的疑點在標示上已解決。是否保留「初估檢核通過」屬產品決策。
- 最小重現：D-01 輸入＋latent_mode=沒有額外產濕、e_np_fan=5、ffu_w=200、c2_bf_min=0.15、各管路已知設備壓差 → 初估完成（待後續階段確認）。
- 可能根因：quality.py 的狀態階層設計。
- 修正建議：產品決策：保留並在說明中講清楚，或移除這個永遠到不了的狀態。

### ISS-4｜H／P 類案例沒有負荷輸入時，供風量只由下限決定，顯熱選型未被驗證｜嚴重度 L｜FAIL
- 來源：H-01, H-03, P-02, P-03
- 說明：規格沒有給人員、照明、圍護與設備負荷，引擎照實算出 qs=0，供風溫差為 0。結果只證明『下限風量×盤管』的算術，不證明房間顯熱選型。這是規格缺料，不是引擎錯誤，但報告若被讀成『手術室已驗證』就是誤導。
- 最小重現：H-01：50 m²×3 m = 150 m³，送風 20 ACH = 3,000 CMH，引擎 qs = 0 kW、供風 3,000 CMH（全由下限決定）；P-02 同理（18,000 CMH）。
- 可能根因：計畫案例未給負荷。
- 修正建議：待補人員、照明、設備、圍護資料後重跑（見待補資料表）。

### ISS-5｜合成案例 CR-01：500 ACH 在預設 FFU 與天花板模組下裝不下｜嚴重度 M｜FAIL
- 來源：CR-01 E1
- 說明：1,500,000 CMH ÷ 1,000 CMH/台 = 1,500 台 × 0.72 m² = 1,080 m²，超過 1,000 m² 地板（覆蓋率 108 %，引擎上限 85 %）。引擎正確標示「未達條件」，所以引擎行為正確；這是工程選型層的結論：要嘛提高單台風量，要嘛縮小循環 ACH，要嘛改用大尺寸模組（S-03 顯示 1200×600 模組需單台 ≥ 約 1,271 CMH 才裝得下）。
- 最小重現：CR-01 如規格輸入。
- 可能根因：規格 + 預設 FFU 的幾何不可行。
- 修正建議：這是案例結論而非程式缺陷；請業主提供實際 FFU 型號。

### ISS-6｜既有 GUI 測試 9 項失敗（simple_gui 5、v554_gui 4）與下拉選單選取文字遮擋｜嚴重度 L｜FAIL
- 來源：上一輪完整測試
- 說明：與本輪無關、本輪未改程式；上一輪完整測試在 Linux/Xvfb 的結果與 F-1 修補前相同。屬於測試過時或 GUI 排版問題，Windows 原生外觀未驗證。
- 最小重現：tests/simple_gui_checks.py、tests/v554_gui_checks.py
- 可能根因：測試對應舊 UI 版面／字型度量。
- 修正建議：在 Windows 實機重跑並更新測試期望值。

### ISS-7｜乾燥外氣下的保守誤拒｜嚴重度 L｜FAIL
- 來源：F-1 修補報告
- 說明：F-1 修補後在 4,000 個隨機 AHU 情境中 1 例因外氣含濕量低於室內而被拒絕（保守方向，不會多給風量）。
- 最小重現：見 tests/fixtures/feed_stress_20261031/after_f1_fix/F1_FIX_REPORT.md
- 可能根因：可達性判準採嚴格 BF ≥ 0。
- 修正建議：列為已知限制，待討論是否放寬。

## 9. 待補工程資料表

| 資料 | 影響案例 | 目前處理 | 取得來源 |
|---|---|---|---|
| 圍護結構（牆面積、U 值、樓板、日射） | 全部 20 案 | 牆／樓板／日射皆設 0（A-ENV）→ 低估靠外牆房間負荷 | 建築圖與熱工資料 |
| 人員數與人體散熱、照明功率 | 全部 20 案 | 人員、照明設 0（A-PPL）→ H／P 類 qs=0 | 業主 URS／平面配置 |
| 設備顯熱的同時率與入室比例 | 全部 | 規格的『設備顯熱 kW』直接當入室熱，PCW／排氣帶走熱比例 0（A-EQ） | 設備清單與冷卻方式 |
| 製程水氣／潛熱 | CR、H、P、D、F | latent_mode 未指定，製程水氣設 0（A-LAT） | 製程資料 |
| 洩漏／門縫／開口與壓差目標值 | CR-05, CR-06, H-01..04, P-02 | en_p_A=0、洩漏 0（A-PRS）；不得由風量差推定 Pa | 漏風測試或洩漏模型、URS 壓差 |
| 轉移風量與負壓／排風櫃補風路徑 | H-02, H-04, F-03 | 引擎無此模型 → BLOCKED | 新增模型或另用外部工具 |
| 局部 ISO 5 區 | P-01 | 背景 ACH 不能推定局部潔淨度；引擎無此模型 | RABS／隔離器廠商資料與確效計畫 |
| FFU 型號、有效風量、阻力曲線、備援與故障台數 | CR-01..08 | 預設 1,000 CMH、0.72 m²、無阻力與備援欄位（A-CHW） | FFU 廠商性能表 |
| 盤管性能（BF 下限、排數）、冰水／乾盤管供水溫度與溫差 | 全部含除濕案 | 冰水 7 °C、乾盤管水 14 °C、approach 1 K 為引擎預設（A-CHW）；BF 下限未提供 → 排數能力待資料 | 盤管廠商選型書 |
| 設備備援（N+1） | D-01, D-02, CR-01..08 | 引擎無備援欄位 | 業主可用性要求 |
| 風機曲線、管徑、設備壓降、水力實際長度 | 全部 | 只有管路小計，設備阻力待資料（A-HYD） | 管路圖、設備資料 |
| 電氣：電壓、線纜、保護、敷設條件 | 全部 | G9 NOT APPLICABLE：未指定電氣條件（A-ELE） | 電氣設計輸入與適用規範版本 |
| 電池化學種類與氫氣／排氣量 | D-02 | 顯熱不能證明通風安全 → BLOCKED | 電池廠商資料與安全分析 |
| 控制精度 ±0.5 °C、穩定性 | F-02 | 穩態需求計算，無控制回路模型 → BLOCKED | 控制設計與感測器規格 |
| 冬季條件下的室內加熱設備與熱源 | CR-07 | W1 檢核只驗證空氣側加濕／再熱收支；NP 電力待資料 | 加熱設備資料 |
| 適用法規與版本（潔淨度、醫院、GMP、電氣） | 全部 | L3 NOT VERIFIED，本報告不作任何符合性宣稱 | 業主指定的規範與版本 |

## 10. 重現

```bash
cd Source/windows
python tests/engineering_scenarios/run_scenarios.py            # 20 案 + 5 掃描 → results.json
python tests/engineering_scenarios/run_scenarios.py --case CR-02
python tests/engineering_scenarios/priority_defects.py --baseline-src <git archive 2c46056 的 Source/windows>
python tests/engineering_scenarios/make_report.py             # 重建本報告
```

## 11. 未驗證項目

- Windows 原生 GUI、EXE、MSI 安裝程式；Linux 虛擬顯示不等同。
- 第 3 層全部（規範符合性）。
- 計畫中 7,412,540,040 CMH 的確切輸入未提供，F-1 以記錄的重現案例驗證同一失效模式。
- 以上未列為 PASS 的項目均為 BLOCKED／NOT APPLICABLE／待確認。
