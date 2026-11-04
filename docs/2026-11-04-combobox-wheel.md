# 下拉欄滾輪安全與頁面捲動修正

基底：`35d32014ce7c959382c039395ab6d1606a8930df`。本修正只修改來源，沒有修改 main、推送、建立公開 Release 或重打包 EXE／DMG。

## 行為

- 游標位於收合的下拉欄時，向上／向下滾輪不切換選項，不觸發模型變數或 `<<ComboboxSelected>>`。聚焦、不聚焦、唯讀、可輸入及停用欄位使用同一安全規則。
- 事件繼續交給既有頁面捲動。簡易工具的 `ScrollableFrame`、完整工作台、AHU 與進階工程設定不再把下拉欄排除在頁面捲動之外。
- 下拉欄仍保有原生鍵盤／點擊 bindings；不清除焦點，不以失焦避開問題。已展開的原生 popup 列表仍能捲動瀏覽，再以點擊／Enter 確認選項。
- Windows／Mac 的 `MouseWheel`（含修飾鍵）、X11 的 Button-4/5 均不再透過下拉欄 class binding 改值。Tk 9 的 `TouchpadScroll` 解出垂直 delta，轉送相同欄位的 `MouseWheel`，由既有頁面 handler 處理；純水平精準手勢不誤觸垂直捲動。
- 無可捲內容或已達邊界時，下拉選項仍保持不變。Text／Treeview 的原生內容捲動保留。

## 實作範圍

兩平台 `ui_common.install_combobox_wheel_guard` 建立 `FacilityCombobox` 專屬 bindtag，複製該 Tk 執行環境的原生鍵盤與滑鼠點擊 scripts，排除改變選項的 wheel scripts；原生 `TCombobox` class bindings 不被修改。由 `app_icon` 初始化，在 Map／FocusIn 處理後續產生的本地化與原生下拉欄，也處理已存在的欄位。Tk 自行建立、沒有 Python wrapper 的 popup 不被替換。

`ScrollableFrame` 將自身捲動 tag 放在 class tag 前。其他頁面維持既有處理順序；已處理的 wheel 回傳 `break`，防止再被外層處理一次。

此修正不更動工程計算、專案 schema、光度匯入、輸出報表語意或公開版本身分。

## 本次已執行

主機為 Linux；**下列不是 Windows EXE 或 macOS App 的原生驗收**。

- 指定基底的獨立來源重現：MainView／AHUView 的下拉欄 wheel 原本回傳 None，頁面沒有任何捲動呼叫。
- 新增 `integration/test_combobox_wheel.py`：Windows 與 macOS 來源分開執行，每份 **33 passed、16 skipped**。通過部分包含 class-tag 複製與隔離、重複安裝、動態控制項、Windows／Mac delta 方向及大小、零 delta、Main／AHU／Simple handler 路由、Text／Treeview 保留，另有 8 組以真正 Tcl interpreter 執行的 Tk 9 精準 delta relay 測試。
- 每平台既有 regression：1,247 checks；simple_features：375；bilingual：7,144；keypad：64。兩平台均通過。
- 來源同步：115 shared files，0 problems。語法／未定義名稱檢查及 `git diff --check` 通過。

33 項新測試使用 Python 3.13.5／Tk 8.6；完整既有回歸使用現成 Python 3.12.14／Tk 9.0 與工程依賴，沒有冒稱是建置鎖定的 Python 3.12.16。初次較精簡環境缺 psychrolib／fluids，換用現成完整測試環境後重跑成功。

## 尚未完成的原生驗收

本執行環境沒有 DISPLAY；現成 Xvfb 嘗試（包含核准後重試）仍無法建立本機 socket，因此 16 個真實 GUI cases 跳過。不得將來源單元測試或 Tcl relay 測試當成實體滾輪／觸控板驗收。

在有顯示的 Windows／Mac，分別設定對應來源並執行：

```powershell
$env:FACILITY_TEST_PLATFORM = 'windows'
$env:FACILITY_REQUIRE_DISPLAY = '1'
python -m pytest integration/test_combobox_wheel.py -q -ra --junitxml=wheel-windows.xml
```

```sh
FACILITY_TEST_PLATFORM=macos FACILITY_REQUIRE_DISPLAY=1 \
  python3 -m pytest integration/test_combobox_wheel.py -q -ra --junitxml=wheel-macos.xml
```

需依賴含 Tk 與 pytest 的開發環境；工程依賴使用倉庫目前建置要求。`FACILITY_REQUIRE_DISPLAY=1` 會將缺少顯示變成失敗，不會把 skips 誤當完整通過。

GUI cases 包含原生／本地化欄位、聚焦／未聚焦、readonly／normal／disabled、頁面實際位移、沒有變更事件、動態加入的 ScrollableFrame 控制項、簡易工具與進階設定頁。Windows／X11 另用真實 Tk 事件測試展開、方向鍵／Enter 和點擊選擇。Aqua 版本可能使用 OS 原生選單，該部分只比對保留的原生 bindings，仍須人工確認：

1. 在簡易工具、完整工作台、AHU 與進階設定頁，以一般滑鼠與觸控板各試上下滾動；分別讓下拉欄取得焦點及只把游標停在上面。數值不改，正確頁面只捲動一次。
2. 測試零內容、頂部／底部邊界、長表單、切頁、關閉重開、切換語言與重新建立表單。
3. 在下拉欄以鍵盤展開，方向鍵選擇並 Enter；以滑鼠展開／點選；在展開列表滾動後選擇；Esc 取消。確定可正常選擇且沒有意外改值。
4. Mac 測 Option+滾輪、自然捲動／反向設定、觸控板小量連續手勢；Tk 9 另測 precision trackpad 垂直及純水平手勢，確認連續手勢捲動速度合適（本輪無實機手感證據）。
5. 確認 Text／Treeview 自身捲動仍正常。完成來源驗收後才重建並驗證實際 EXE／App；本 patch 不授權發布。

## 整合注意事項

新增測試獨立於 IES 格式修正。應一次套用兩份平台來源與本測試，再跑來源同步。改動 ui_common、industrial_theme、main_view、ahu_view、fusion_settings、simple_desktop；未動 photometry.py、lighting_direct_checks.py 或既有 IES 文件。既有測試會重寫 evidence 內的歷史輸出；本 patch 已排除那些生成差異，這次測試記錄另外保存。
