# Windows win.1：離線直接執行版

> **歷史紀錄：**以下保留當時版本與提交的測試、限制及雜湊，不代表目前下載狀態。現行版本為 **V5.5.5 中英雙語版**，見[最新下載](../README.md#下載)、[雙語原生驗收](2026-10-07-bilingual.md)及[目前授權](../LICENSE_GUIDE.md)。
> Historical record; see [current English downloads](../README.en.md#download-and-run) and [V5.5.5 verification](2026-10-07-bilingual.en.md).

舊 Windows 懶人包是在使用者電腦下載 Python、pip 套件後編譯 EXE。
本版改由原生 Windows 建置並事先驗收，交付的 EXE 已包含 CPython 3.13.15、
Tk、Matplotlib、NumPy、Pillow 與全部應用程式資源。下載後可直接執行，
不需另裝 Python、不需安裝套件、不需連網、不需管理員權限。

完整 ZIP 另包含設備需求 Excel 範本、原始碼、授權文件與本機診斷腳本。
FY 圖示、七種獨立工具、設備表彙整及完整工程工作台全部保留。
未變更工程公式；包含既有安全、數值與現行授權維護。既有專案及歷史 Release 保留。

## 原生驗收

[修訂驗收工作流程](https://github.com/azx4121/facility-studio/actions/runs/37561048244)
使用同一份 EXE，SHA256 `ecfd8bd233e59d7249dc21387db8c3d1d602c2b52b4b5cc3f0eecdc75d81f6c7`。
此為修訂分支的驗收檔；main 發布流程會重新建置與重驗，正式下載檔雜湊以 Release 的 SHA256SUMS 為準。

| 原生環境 | 單檔 EXE | ZIP 解壓縮 | 中文／空格 EXE 路徑 |
| --- | --- | --- | --- |
| Windows Server 2022 x64 | 53項通過 | 53項通過 | 53項通過 |
| Windows Server 2025 x64 | 53項通過 | 53項通過 | 53項通過 |

53項涵蓋封裝執行環境及授權資源、原生 NumPy／Pillow、完整預設工程計算、
七種工具、七種設備 CSV 分析、Excel 範本輸出／讀取、範例停用防呆、
Tk原生GUI、全部工具頁、工作台八頁、UI事件回應及Matplotlib繪圖。
重複執行同一組檢查不算新增不同工程條件。

每種交付方式另驗證七種 CLI 報告／JSON、Unicode模板路徑、預設專案與完整報告。
啟動 EXE 的 PATH 移除外部 Python，工作目錄為空資料夾。
單檔／ZIP測試同時由 Windows 防火牆禁止該 EXE 對外連線，及 audit hook 禁止socket連線；
中文EXE路徑的額外測試使用audit hook，不宣稱該額外路徑也套用防火牆。
測試使用暫時應用程式資料，保留原有使用者專案。

原生驗收記錄永久保留於：

- [Windows 2022](../windows/evidence/windows-native-win1/Windows_2022_Acceptance.json)
- [Windows 2025](../windows/evidence/windows-native-win1/Windows_2025_Acceptance.json)

## 數值與安全回歸

建置前在原生 Windows 成功執行以下既有測試：

| 測試 | 成功結果 |
| --- | --- |
| regression.py | 52情境、1,247獨立檢查、7預期拒絕 |
| v55_features.py | 20數值條件、93檢查 |
| v552_core.py | 305檢查 |
| simple_features.py | 42情境、375數值／報告檢查 |
| v554_features.py | 49情境、646計算／匯入／報告／線圖檢查 |
| maintenance_checks.py | 90空氣／報告條件、1,129檢查 |
| security_checks.py | 55輸入安全案例 |

## 交付及限制

建置套件17個版本及SHA256鎖定；下載發生在建置端，不是使用者電腦。
Python、Tcl/Tk及各套件授權保留，專案自身現行授權與歷史MIT全文一併提供。
只有兩個Windows原生驗收成功後，main流程才建立新的 `v5.5.4-win.1` Release。
發布前核對檔案大小與GitHub資產SHA256；不覆寫既有公開Release或標籤。

修復過程中，驗收腳本在Windows暫存路徑新增防火牆規則曾回傳錯誤87；
已將規則中的程式路徑正規化、ZIP驗收置於完整工作路徑，並實際重驗通過。
這是驗收腳本的路徑處理，與應用程式計算功能分開處理。

Windows10／11 Intel／AMD x64為支援目標；未冒稱已在使用者MSI筆電、
Windows10／11實體電腦、Windows ARM或32位元完成驗收。
商用程式碼簽章、SmartScreen、企業管理政策及實體輸入裝置仍須現場確認。
`Verify_on_Windows.cmd`可在本機離線診斷，不設定防火牆、不上傳資料、不覆寫專案。
一鍵 EXE 首次展開內建套件可能稍需等候。

