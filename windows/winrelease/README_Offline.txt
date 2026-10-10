Facility Studio V5.5.8｜Windows 廠務工程初估工具
DESIGNED BY ANDY HUANG ©

用途
單項快算：電力配線、風管、CDA／特氣、照明、冷熱水、空氣線圖與單位換算。
多設備：用 Excel／CSV 彙整電力與廠務需求。
完整工作台：整理空調方案、夏冬空調箱分段需求與報告。
繁體中文／English 可即時切換；計算與專案保存可離線完成。

下載與開啟
目前公開下載為 EXE：
https://github.com/azx4121/facility-studio/releases/download/v5.5.8-win.1/Facility_Studio_V5_5_8_Windows_Offline.exe
儲存後雙擊開啟，第一次請等候內建環境展開。不需另裝 Python 或管理員權限。
Windows 10／11 Intel／AMD x64 為支援目標；原生驗收為 Windows Server 2022／2025 x64。
本版尚無正式發行者簽章。首次安全提示說明：
https://github.com/azx4121/facility-studio/blob/main/docs/signing.md

第一次使用
先選一個簡易工具 → 填數值與單位 → 查看採用條件 → 計算 → 複製／匯出。
「本工具教學」開啟對應的離線說明。
整案報告從「完整工程工作台 → 新手教學」的前六步開始。
「開啟練習新案」會直接載入含分段空調箱的 MAU 範例。
設備表先從程式匯出範本；欲納入計算的設備將「啟用(1/0)」設為 1。

保存與回報
整案 JSON 可接續編輯；TXT／HTML 是供閱讀與分享的報告。
V5.5.8 獨立空調箱可確認保存無效草稿，修正後才能計算或匯出。
啟動記錄：%LOCALAPPDATA%\Facility_Studio_V5_5\Logs。
更新前先關閉舊程式，替換 EXE 即可；已儲存的專案與復原資料保留。
回報問題請附版本、作業系統、輸入單位、步驟與完整錯誤，移除業主機密：
https://github.com/azx4121/facility-studio/issues

用途與授權
工程結果供初估、方案比較與需求整理；正式設計需依現場、設備資料與規範覆核。
公司內部工程工作、收費工程案與計算書交付許可詳 LICENSE／LICENSE_GUIDE.md。
軟體轉售、付費綁售及付費線上軟體服務需另行書面授權。
歷史 MIT 版本與第三方元件的原授權保留。

English
Use independent engineering calculators, import equipment schedules, or compare HVAC/AHU schemes.
Download the EXE above and double-click. The runtime and offline help are included.
Choose English at the top right. No separate Python installation is needed.
The EXE is unsigned. Support targets are Windows 10/11 x64; native acceptance used Server 2022/2025.
Results are preliminary estimates. Company use and paid engineering reports follow LICENSE;
software commercialization requires separate permission.

Current downloads, source/build guidance and verification:
https://github.com/azx4121/facility-studio/blob/main/README.en.md
https://github.com/azx4121/facility-studio/blob/main/docs/development.md
Historical platform instructions:
https://github.com/azx4121/facility-studio/blob/main/docs/history/windows-v5.5.6-readme.txt
