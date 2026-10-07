# Windows V5.5.5 離線發行

[目前下載與英文安裝](../../README.en.md#download-and-run) · [雙語原生驗收](../../docs/2026-10-07-bilingual.en.md)

Developer build only: the shipping V5.5.5 EXE/ZIP already contains Python. Normal users do not run pip or these build commands. The current publisher targets v5.5.5-win.2 and must not overwrite its existing public assets. For a future release, update the builder, verifier, publisher and workflow version/output names together.

`entry.py` 為單檔 EXE 的視窗模式入口；日常使用不執行 pip、不尋找外部 Python、不下載元件。
主應用程式與完整計算邏輯仍使用 `windows/facility_studio`；不是另一套精簡計算版本。

在原生 Windows x64 使用官方 CPython 3.13.15，執行：

```powershell
python -m pip install --require-hashes --only-binary=:all: -r windows/winrelease/requirements.lock.txt
cd windows
python -m winrelease.build --output C:\FacilityStudioBuild
python -m winrelease.verify --assets C:\FacilityStudioBuild --output C:\FacilityStudioEvidence
```

連網只發生於開發者建置套件取得時。封裝17個套件版本及下載SHA256鎖定；
原始 CPython、第三方套件授權與專案現行／歷史授權資料一併保留。
發行輸出含獨立 EXE、完整 ZIP、SHA256SUMS；FY 圖示、版本資訊與設備範本均包含。

驗收腳本由開發者 Python 控制，啟動的 EXE 本身只使用內建執行環境。
驗收時 EXE 的 PATH 移除外部 Python，工作目錄為空白資料夾；
僅針對該 EXE 建立暫時對外封鎖防火牆規則，完成即刪除。
另使用 Python audit hook 禁止 socket 連線，檢查封裝資源、原生 Tk、
七種工具、七種設備分析、完整工作台八頁、原生繪圖、CLI報告與模板輸出。
相同檔案另在第二個 Windows runner 重複驗證，成功才允許 main 發布新 Release。
另在中文與空格的 EXE 路徑驗收；該額外路徑測試使用 socket audit hook，
不與 Windows 防火牆的程式路徑正規化混為一談。防火牆規則使用展開短路徑別名後的完整路徑。

本機一般使用者診斷 `Verify_on_Windows.cmd` 不需系統管理員、不更動防火牆、
不會上傳資料、不覆寫原有專案。CI防火牆設定只是開發者驗收。

原生runner為 Windows Server 2022／2025；不冒稱 Windows10／11實體電腦已完成驗收。
未取得商用程式碼簽章；Windows安全性、SmartScreen與企業管制需現場確認。
舊線上安裝器與歷史Release保留；它們不屬於新版離線啟動流程。



V5.5.5 revision 2 / 署名與新手教學修訂
簡易工具左下角持續顯示 DESIGNED BY ANDY HUANG ©。
簡易工具、完整工程工作台及單台空調箱的「新手教學」可開啟離線中英逐步教學。
完整 ZIP 的 Beginner_Tutorial/START_HERE.html 也可直接閱讀。
先複製改名練習 JSON，再由完整工作台「開啟」；原廠選型與設備阻力等待补資料仍需補。
Revision 2 adds persistent author credit, bundled offline walkthroughs, two practice workspaces and reference reports.
No additional Python installation or internet is needed for the tutorial.
