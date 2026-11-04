# 2026-11-04：AHU 對照、設計規範與 DI 範本修正

本輪限定四項已重現的缺陷，Windows／macOS 共用來源同步修改。未改公開版本、舊 installer payload、工程主引擎公式或已發布二進位檔。

## 修正範圍

1. **AHU 分季模型對照**：`主案分季需求` 使用各季的 `summer_flow`／`winter_flow` 及各季目標送風狀態重新算乾空氣質量流率。停用的共同 `flow`／`flow_basis` 不參與。獨立模式仍沿用原來的共同風量基準；對照器沒有直接照抄主引擎質量流率。
2. **可編輯規範保留原文**：設計審查的規範輸入使用原生 Text，不使用報告文字翻譯器。完整名稱、條號、範圍、來源及全形 `｜` 分隔符不因英文顯示／切換語系而改寫。設計審查視窗也掛接語系標題更新。
3. **連動 AHU 邊界失效保護**：編輯既有邊界、使用送風／盤管預設、或帶入氣候，不再自動改成獨立設計。保留來源專案識別，連動標記加上一次 `stale:`，重算、重複編輯與整案存取後仍禁止回傳。重新連動或經確認「設為本案獨立設計」才解除；取消確認不解除，復原可回到過期狀態。原本未連動的獨立設計及純額定值修改維持原語意。
4. **DI Excel 預覽**：兩平台內嵌範本的 DI!L6:M105 納入每台持續循環量。全開量為製程流量加循環量，同時量只對製程流量乘使用率。I 欄固定 LPM，先換回 H 欄原單位後加總，涵蓋 LPM／US GPM／m³/h／L/s。保留無 ID 空白、停用零、缺流量提示、既有表格樣式及驗證。

流量 10 LPM、2 台、50% 使用率、每台循環 2 LPM 的範本預覽與設備引擎均為全開 24 LPM、同時 14 LPM；0% 使用率仍保留 4 LPM 循環。

已有舊案若曾被舊版清為「尚未連動」，不能從缺失的資料可靠還原原來源，本輪不猜測或自動重建其關係。

## 可重現檢查

每個平台各用新的 Python 程序，從倉庫根目錄執行：

```sh
FACILITY_TEST_PLATFORM=macos python -m pytest integration/test_reviewed_ui_defects.py integration/test_di_template.py -q -ra
FACILITY_TEST_PLATFORM=windows python -m pytest integration/test_reviewed_ui_defects.py integration/test_di_template.py -q -ra
python tools/verify_platform_sync.py
```

需要真實 Tk 顯示服務時，設定 `FACILITY_REQUIRE_DISPLAY=1`；缺顯示服務將失敗而非跳過。Linux CI 使用 Xvfb，既有 preview workflow 已加入雙平台獨立程序執行上述測試。Windows／macOS 應在各自原生環境另跑。

針對性測試涵蓋各季風量／停用草稿、獨立風量基準、20 個 AHU 邊界欄位、原已過期來源、預設與氣候帶入、重新連動、明確獨立與取消、復原、整案檔案重開、英文規範原文存取及語系切換，以及 DI 四單位／0、50、100% 使用率／首中末列與缺資料邊界。DI 測試使用小型白名單公式解譯器讀取實際範本並與設備引擎交叉比對，不用 eval，也不新增產品依賴。

## 本次驗證界線

- Linux 上兩份來源的針對性檢查各 **124 passed、2 skipped**。跳過的是兩項真實 Tk 視窗測試。
- 擴大回歸各 **289 passed、19 skipped、4 deselected**，包含既有 design-basis、fusion、language-lifecycle、candidate-acceptance、combobox 與可無畫面執行的 feed-sandbox 檢查。跳過／排除均為需顯示服務的 GUI 路徑。既有部分測試寫死匯入平台；本次 runner 預先載入並驗證指定來源根目錄，避免把同一份來源誤算為兩平台。
- 平台同步 **115 共用檔，0 問題**；Python 編譯、差異空白檢查及 workflow YAML 語法解析通過。
- DI 最終檔另外經 Artifact Tool 重匯入與 **84 個回算情境**，並檢視修改前後及 24／14 合成案例的渲染。只有 DI worksheet 的 200 個公式文字節點改變，其他 ZIP 成員內容及非目標 XML bytes 完全保留。
- 本機無 DISPLAY，隔離 Xorg 亦因本機 socket 建立受限而無法啟動。因此未完成原生 Tk 視窗執行、Windows EXE／macOS App、Excel／LibreOffice 原生重算或封裝驗收，也未執行公開 CI。方法層與來源測試不能取代這些驗收。
