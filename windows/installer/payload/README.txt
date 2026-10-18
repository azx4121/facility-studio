Facility Studio V5.6.0｜Windows 廠務工程初估工具
DESIGNED BY ANDY HUANG ©

本版修訂：V5.6.0 · Windows win.6
十項快算包含潔淨室風量、熱負荷初估與冰水泵浦，支援上游帶入、KPI與HTML總覽。
舊案以schema 12移轉並保留原假設；FFU氣流路徑／ACH基準須明確選擇。
照明使用型錄利用係數U與實際長寬的室指數K；不以幾何公式取代燈具配光資料。
工程覆核、測試與目前發布狀態：
https://github.com/azx4121/facility-studio/blob/main/docs/2026-10-16-gemini-integration-review.md

用途
單項快算：電力配線、風管、CDA／特氣、照明（型錄 U 與室指數 K 檢核）、冷熱水、空氣線圖、單位換算、潔淨室風量、熱負荷初估與冰水泵浦。
多設備：用 Excel／CSV 彙整電力與廠務需求。
完整工作台：整理空調方案、夏冬空調箱分段需求與報告。
繁體中文／English 可即時切換；計算與專案保存可離線完成。
十個快算直接列於左側；水管自動選型至30吋，先選符合水速的單管。
氣體快算與工作台共同提供50種廠務氣體及自訂／混合氣，新增氣體需填設計流速。
本修訂保留重選同種製程氣體的已填流速；切換到不同新增氣體須重新填寫。

下載與開啟
目前公開下載為 EXE：
https://github.com/azx4121/facility-studio#readme
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
獨立空調箱可確認保存無效草稿，修正後才能計算或匯出。
V5.6.0 保留數字鍵盤 Del／小數點辨識；一般 Delete 保留刪除功能。
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
All ten calculators are direct sidebar buttons; automatic water sizing extends to 30 inches.
The calculator and workbench share 50 factory gases plus custom mixtures.
Added gases require an entered design velocity; reselecting the same gas preserves it.
Download the EXE above and double-click. The runtime and offline help are included.
Choose English at the top right. No separate Python installation is needed.
V5.6.0 accepts the keypad decimal/Del key; dedicated Delete still deletes.
The EXE is unsigned. Support targets are Windows 10/11 x64; native acceptance used Server 2022/2025.
Results are preliminary estimates. Company use and paid engineering reports follow LICENSE;
software commercialization requires separate permission.

Current downloads, source/build guidance and verification:
https://github.com/azx4121/facility-studio/blob/main/README.en.md
https://github.com/azx4121/facility-studio/blob/main/docs/development.md
Historical platform instructions:
https://github.com/azx4121/facility-studio/blob/main/docs/history/windows-v5.5.6-readme.txt

win.6：修正水管 ΣK 報告、同迴路電力候選、W／kVA 帶入、夏冬 RCU／FCU 容量、泵浦單位切換及換算溢位；保留 win.5 照明修正。
舊版已錯存的電力來源會標示未達條件，請移除本盤已納入電力來源，再用原始資料重新帶入。僅有主案而無來源記錄的舊檔，請核對原始 W／kVA；不自動猜改已存 kW。
win.6 fixes F01–F06; historical W/kVA source adoptions must be removed and reimported from original data. Main-only legacy files require manual comparison with original values.
