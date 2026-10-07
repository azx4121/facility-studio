Facility Studio V5.5.4｜Windows 離線直接執行版 win.1

1. 完整解壓縮 ZIP 到桌面或您自己的資料夾。
2. 雙擊 Facility_Studio_V5_5_4_Windows_Offline.exe。
3. 開啟後即可使用；不需另裝 Python、不需安裝套件、不需連網。

也可單獨下載 EXE 直接執行。首次啟動需在暫存資料夾展開內建套件，請等候。
請使用 Windows 10／11 Intel／AMD 64 位元。Windows ARM、32 位元未驗收。
不需系統管理員權限；企業電腦若限制自行下載的程式，請洽 IT。
本版尚未取得商用程式碼簽章。請從 azx4121/facility-studio 的 GitHub Release 下載；
不要關閉防毒軟體。若被 Windows 安全性或公司政策攔下，請先確認來源及 SHA256。

內含電力、風管、氣體、照明、水系統、空氣線圖、單位換算、
設備表匯入與完整空調工作台，以及既有 FY 圖示。
設備需求範本.xlsx 內的範例預設停用；欲納入計算請設「啟用(1/0)」為 1。
也可在程式設備匯入功能匯出範本。

專案由您另存至指定位置；復原資料及診斷記錄位於：
%LOCALAPPDATA%\Facility_Studio_V5_5
更新時替換 EXE 即可，不必刪除舊專案或解除安裝 Python。

若無法開啟，可雙擊 Verify_on_Windows.cmd，完成本機自我檢查。
檢查記錄位於 %LOCALAPPDATA%\Facility_Studio_V5_5\Logs。
診斷不會上傳資料；不會覆寫既有專案。

Source 為本版完整應用程式原始碼。執行 EXE 不會使用 Source，也不需它才能啟動。
授權詳 LICENSE 與 LICENSE_GUIDE.md；第三方元件各自授權保留於 THIRD_PARTY_LICENSES.txt。
初估工具的工程適用範圍與參數假設詳程式報告，正式設計須依現場與設備資料覆核。
更新、問題回報：https://github.com/azx4121/facility-studio
