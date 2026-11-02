# Facility Studio 5.7.1 測試版：本批實測紀錄

## 已查證事實

- 產品來源提交：`bc4e557810e7d85faef3c4bf036efcd9a4fc0fc9`。驗收修正提交：`dae2bf48c5f5c6f9b537d8b580020a12262e94af`。已用git diff確認產品、封裝程式、README及鎖檔沒有變更；後者僅修測試讀寫的UTF-8宣告，沿用已驗證Mac成品。
- 167項pytest通過；UTF-8測試讀取修正後，53項受影響pytest與電力GUI通過。原生Mac核心31項及簡易操作27項通過，最小視窗文字94項、來源工作台GUI362項通過。完整27套既有工程回歸通過。
- 每平台100回合欄位與報告各7898項檢查；獨立工程4434項；教學每平台20情境93項通過。新文案雙語檢查6373項通過。
- 最新Mac ZIP已移到新路徑、空白工作目錄，移除開發Python路徑並以稽核鉤阻擋網路，重新通過核心31與操作27項；另測正常GUI入口、液體CLI、PV CLI，以及非液態反例拒絕。六個實際程式命令皆符合預期退出碼；非法工況預期退出2且沒有產生報告，其餘退出0。
- Mac ZIP SHA256：`9874ffe8385e42485e24e7393f3f169f86bb2ef7f302d02aea706f852e4bac8e`。新交付App嚴格簽章檢查退出0，屬ad-hoc簽章，不冒稱Apple公證。
- Windows原生舊run失敗於測試Path.read_text使用cp1252讀UTF-8；產品模組沒有缺少encoding的read_text/write_text呼叫。新run `41533629312`三個job全部成功：Linux來源、Windows2022原生回歸／成品／安裝、Windows2025同一份雜湊的Portable及安裝。兩環境核心31項、簡易27項及安裝後31+27項均通過；安裝退出0、非空目錄保護退出2、移除退出0並保留自訂檔案。安裝與Portable下載後SHA256皆相符，兩平台102個來源檔案除平台版本與教學ZIP外沒有差異。
- 本機千問`qwen3.8:27b`已實際完成公開操作說明的文字審查，輸出587個token；主代理已核對採否，未採用其中兩項錯誤介面推論。未用付費API，沒有新增常駐服務。

## 實測命令與證據

Python為 `/Users/chaoi/Facility-Studio-Fusion-Env-20261102/bin/python`，3.12.16。

| 實際命令 | 結果／證據（位於 `/Users/chaoi/Facility-Studio-Simple-Evidence-20261102`） |
|---|---|
| `python -m pytest integration/test_simple_facilities.py integration/test_fusion.py integration/test_product_wording.py macos/tests/test_feed_sandbox.py -q` | 退出0，167 passed；complete-r21.xml及log |
| `python windows/tests/electrical_units.py --gui` | UTF-8修正後退出0；utf8-electrical-r22.log |
| `python -m pytest macos/tests/test_feed_sandbox.py integration/test_product_wording.py -q` | 退出0，53 passed；utf8-r22.xml及log |
| `python windows/winrelease/source_sandbox_checks.py --output .../Final-r17/Full` | 27套全部退出0；Full/Source_Suite_Results.json |
| `python tools/verify_dashboard_gui.py --platform macos --output .../Final-r17/Dashboard_GUI.json` | 退出0，362檢查；含真實Tk佈局與事件 |
| `python tools/verify_100x_all_fields_and_reports.py --platform macos --iterations 100 --output .../fields100-phase-r20.json` | 退出0，7898檢查 |
| `python tools/verify_platform_sync.py` | 退出0，102共用檔案、0問題；僅平台version及教學ZIP可異 |
| `python integration/build.py --output /Users/chaoi/Facility-Studio-5.7.1-Review-bc4e557` | 退出0；該目錄evidence/含封裝、簽章及frozen驗收 |
| `python .../verify_mac_delivery_r21.py` | 退出0；Mac-Offline-r21.log及建置目錄/移機離線驗收/Offline_Verification.json |
| `uv pip check --python <上述Python>` | 56個套件相容；未為檢查重複安裝 |

## 本輪修正

保溫外徑與選管條件失效、冷熱水到液體的流量帶入及遞迴過期保護、工況與警戒門檻追溯、長網址及英文導覽截斷、新工具離線教學、總送風ACH導致舊FFU基準失效的獨立壓損斷言、純液體手填物性相態防呆、原生說明殘留套件名稱，以及新工具CLI入口。

已測反例包括NaN/inf、無效外徑與管壁、化學液體缺供應商物性、變更操作條件後沿用舊來源、高流速／高壓損、100%RH保溫無解、PV表壓誤填／大於當地大氣壓、過期來源匯出，以及150°C/1kPa把純水當液體。

## 能力與後續

工程模型與資料適用邊界見FEED_GAPS.md及SOURCES.md；未宣稱通用FEED認證。Claude仍須在2026-11-03 13:05之後作獨立審查及最終發布。沒有合併main、公開Release、覆蓋既有App或專案；不能把本機千問文字檢查或三方AI審閱當工程簽核。
