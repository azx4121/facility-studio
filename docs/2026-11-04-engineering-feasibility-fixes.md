# C2、真空、停用水洗欄位及 NP 馬達構成修復

## 修復範圍

此修訂以 `35d32014ce7c959382c039395ab6d1606a8930df` 加上既有配光及 Combobox 修正的精確候選為基底；不修改既有冷量、額定裝機或服務群組界線。

1. **C2 可行性。** 單機兩條計算路徑保留 solver 的 `feasible_adp`、`path`、`reason`。主要路徑的 ADP 必要條件必須同時通過 solver，可行性失敗不再被需求佔位點掩蓋。品質、段落表、文字報告及圖表標明不可達的需求點。合法的 `reheat_required` 仍是盤管可行，另由再熱／送風條件檢核，不把需要再熱誤判成盤管不可行。
2. **真空抽速。** 全部流態先檢查指定氣載需求 `S_req = Q_actual / 60` 是否大於所填泵入口抽速。被動管路不會增加有效抽速，因此此必要條件不依賴尚未計算的黏滯／過渡導通率。分子流模型適用時仍檢查更嚴格的有效抽速；避免同一不足重複報兩次。確定不足列入結構化 failures，報表列需求抽速。低於泵入口抽速不代表管路或泵曲線已通過。
3. **停用欄位。** 不含水洗的加濕模式將 `pump_air_fraction` 列為停用。保留原始草稿，計算使用安全預設，重新選水洗後非法草稿仍拒絕並定位該欄。
4. **NP 馬達構成。** 自動加總的內部計算分開保留原手動 HP 與其餘 kW，不把新增 kW 當成馬達 HP。保留已驗證的馬達旗標、HP 合計、最大馬達及手動設計電流。合併設計下限仍為「原手動設計電流＋新增運轉電流×1.25」；中英報告另列其組成，避免只有最大馬達公式而看不出較高的保守下限。使用者原負荷欄位及來源分類不改寫。

## 明確不變的邊界

- PCW-A／PCW-B 是各自供應迴路，不無條件合成主管。同群組設備仍合計。
- 已選用但當季旁通的水洗設備，運轉功率為零，額定裝機及需求回傳仍保留。永久不配置須取消設備選用，不能用季節旁通刪除配電容量。
- 原 NP 反例有設計電流下限保護；本修復不宣稱過去例子曾證實線徑或保護容量低估。
- 不改單位換算流程、不建置、不發布、不改既有版本或公開安裝檔。

## 新回歸與 CI

分別啟動程序，避免 Python 匯入快取混用兩平台來源：

```sh
FACILITY_TEST_PLATFORM=macos python -m pytest integration/test_engine_review_guardrails.py -q
FACILITY_TEST_PLATFORM=windows python -m pytest integration/test_engine_review_guardrails.py -q
python tools/verify_platform_sync.py
```

新回歸每平台 51 個測試，使用獨立 ASHRAE 飽和壓／含濕比式、理想氣體抽速式和三相電流式。涵蓋 BF 不可行、base 分支、合法／未知 BF、需再熱、各流態、12 組流量與壓力單位、低／零需求、停用草稿及重啟、旁通額定、NP 不同負載類型／混合單位／未知最大馬達／額外設計下限與候選電纜不退步。工程儀表板 CI 已加入此回歸，使用各 job 的來源平台。

## 本次來源驗證結果與限制

- 新回歸兩平台各 51 通過。
- 獨立覆核每平台：C2／真空／停用欄位 140 斷言、NP 180 斷言、PCW 8 斷言，皆通過。NP 的 11 組情境與修復前快照比較，電纜／保護候選整筆相同。
- `regression`、`simple_features`、`v557_inactive`、`v558_review`、`v559_resilience`、`bilingual`、`panel_demand_checks`、`optional_inputs_checks`、`winter_terminal_heat_checks`、`ahu_link_boundary_checks`、`audit_regressions`、`report_regressions`，兩平台均通過。
- `verify_engineering_dashboard`、`verify_dashboard_reports`、`verify_gemini_review`，兩平台均通過。
- C2 舊有 solver 密集掃描兩平台各 29 檢核通過，各涵蓋 1,500 組可行／再熱／不可行工況。
- 結合既有候選及 Combobox 測試：95 通過、16 因顯示環境跳過。
- 完整 `integration` 實跑：459 通過、19 跳過；83 項 GUI 測試因未提供 DISPLAY 而無法建立 Tk 視窗，其中21項標為失敗、62項為fixture錯誤。全部83項均核對為此環境原因，沒有宣稱完整套件全綠。
- 明確排除上述83項後，以指定macOS來源重跑headless子集：459通過、19跳過、83取消選取；不將被排除的GUI測試算為通過。
- 8 張中英可行／不可行圖表使用真實生產繪圖方法和 Matplotlib Agg，非計算的 Tk 接收器替代標籤／表格。不可行圖已目視檢查警語，但不是原生 GUI 事件或整體視窗驗收。
- 兩平台共享115個程式／資源檔核對無非預期差異，修改的 Python 均可編譯。

上述為 Linux 上兩份來源的測試，不是 macOS App／Windows EXE 原生驗收、原廠性能確認、保護協調／法規審查或完整 FEED。獨立測試及詳細本次證據另附於交付的 evidence 與 independent 目錄。
