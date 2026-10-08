Facility Studio V5.5.6｜Windows 離線直接執行版 win.2

1. 完整解壓縮 ZIP 到桌面或您自己的資料夾。
2. 雙擊 Facility_Studio_V5_5_6_Windows_Offline.exe。
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

V5.5.6：主畫面右上可選繁體中文 / English；切換保留輸入與結果，語言偏好會保存。
Language: choose Traditional Chinese / English at the top right. Inputs and calculations stay unchanged. Your language preference is saved.
English Excel / CSV templates are exported when English is selected; both template languages can be imported.


V5.5.6 revision 2 / 署名與新手教學修訂
簡易工具左下角持續顯示 DESIGNED BY ANDY HUANG ©。
簡易工具、完整工程工作台及單台空調箱的「新手教學」可開啟離線中英逐步教學。
完整 ZIP 的 Beginner_Tutorial/START_HERE.html 也可直接閱讀。
先複製改名練習 JSON，再由完整工作台「開啟」；原廠選型與設備阻力等待補資料仍需補。
Revision 2 adds persistent author credit, bundled offline walkthroughs, two practice workspaces and reference reports.
No additional Python installation or internet is needed for the tutorial.

V5.5.6 使用流程
・簡易工具的「本工具教學」直接開啟對應離線章節。
・完整工作台先用基本模式與「空調與熱負荷」；其他分頁可展開。
・「另存新檔」保留案件身分換檔；「複製為新方案」建立新案，原案保留。
・設備表先分析、選群組，再「預覽帶入主案」；儲存整案保留需求來源。
・同台空調箱重複回傳更新原來源；不同台才加總。水路依季節及工況分組。
・「待重算」是上次有效結果，不能當作目前輸入結果匯出。
