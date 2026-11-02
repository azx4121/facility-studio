# Facility Studio 工程驗證沙盒：Windows x64

以 Mac 已驗收提交 `8e791a21dc8207d703a57f48a468835723436e18` 為基礎，同步相同工程驗證功能至 Windows，保留正式版與既有專案。版本 `5.6.1-win-sandbox.1`／檔案版本 `5.6.1.1`。

提供兩種交付：

- `Facility_Studio_FEED_Sandbox_5_6_1_Setup.exe`：繁中、每位使用者、離線安裝程式，使用獨立目錄與捷徑，不要求系統管理員權限。
- `Facility_Studio_FEED_Sandbox_5_6_1_Portable.zip`：解壓縮後執行內附 EXE；已包含 Python、Tk、PsychroLib、CoolProp、Pint、fluids 及相依套件。

執行時使用 `%LOCALAPPDATA%\Facility Studio FEED Sandbox\Data`，與原正式版的設定、專案與日誌分離。安裝程式拒絕寫入非空目錄；移除只刪除本版列明的程式檔，保留使用者另存檔案及資料目錄。沒有停用防毒、SmartScreen 或系統安全機制。本測試版未取得 Authenticode 商業簽章。

新增功能：AHU 目前輸入快照／品質原因／數值對照、同徑等分並聯純水管路、九類單位換算，以及不覆寫既有檔案的 TXT／HTML／JSON 匯出。工程條件與軟體數值通過分開；完整範圍見 [FEED 沙盒說明](feed-sandbox.md)。

`tools/verify_platform_sync.py` 確認 Mac／Windows 共用程式一致，只有平台版本與教學資源允許不同。字型依平台選擇；Cocoa 原生選單檢查僅在 macOS 執行，Windows 則驗證其原生 Tk 繁中選單。

GitHub `feed-windows-sandbox.yml` 在原生 Windows Server 2022 建置與執行，第二個 Windows Server 2025 驗證同一份 EXE／安裝程式／ZIP 的 SHA-256。這些是實際 CI 平台，不冒稱已在使用者的 Windows 10／11 實機操作。

驗收涵蓋：34 項新增測試與 300 組 Hypothesis 性質案例、既有數值與 GUI 回歸、實際 NSIS 安裝、中文路徑、拒絕覆寫既有目錄、移除後使用者資料保留、免安裝 ZIP 與已安裝 EXE 一致，以及在空白工作目錄、外部 Python 不在 PATH、出站網路受阻擋時執行封裝後完整 GUI／工程／匯出檢查。所有通過數以當次 CI 證據為準，不在此預先宣稱成功。

依賴來源與雜湊固定於 `windows/winrelease/requirements_sandbox.lock.txt` 和 `sandbox_runtime_manifest.json`。僅建置階段下載官方依賴；runtime 不需網路。PyInstaller 與 NSIS 分別使用原生打包及離線安裝；不從 Mac 產生假 Windows EXE。

GitHub 工作流程不發布 Release、不合併 main、不使用付費模型或公司資料。通過後才將安裝包、免安裝包、核對碼與說明上傳至使用者已連接的私人 Google Drive，不調整分享權限。

來源：[PyInstaller 官方封裝模式](https://pyinstaller.org/en/stable/operating-mode.html)、[NSIS 腳本參考](https://nsis.sourceforge.io/Docs/Chapter4.html)、[GitHub Windows 2022 runner](https://github.com/actions/runner-images/blob/main/images/windows/Windows2022-Readme.md)。

保留的 win.10 線上安裝包未改寫。一般來源 CI 對它採 `packaging_checks.py --legacy-assets-only`，保留 manifest、CRC、完整解壓與 embedded bytes 檢查，明確不計為新沙盒來源一致性。正式發布流程不帶此參數，仍強制原本的來源一致性；新沙盒則由 build manifest、交付 SHA-256 及兩個 Windows 原生安裝／執行 gate 驗證，不能用歷史包測試取代。
