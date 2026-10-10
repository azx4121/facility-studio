Facility Studio V5.5.8｜macOS 廠務工程初估工具
DESIGNED BY ANDY HUANG ©

用途
獨立快算電力、風管、CDA／特氣、照明、冷熱水、空氣線圖與單位；
匯入 Excel／CSV 彙整設備需求；以完整工作台比較空調方案與夏冬空調箱各段需求。
繁體中文／English 可即時切換；計算、專案保存與內建教學可離線使用。

下載與安裝
目前公開下載為 DMG：
https://github.com/azx4121/facility-studio/releases/download/v5.5.8-mac.1/Facility_Studio_V5_5_8_macOS_mac1.dmg
1. 打開 DMG。
2. 把 Facility Studio 拖到「Applications／應用程式」。
3. 從「應用程式」開啟。安裝完成後可退出 DMG。

內含執行環境，不需另裝 Python 或 Homebrew。
Universal App 支援 Apple Silicon／Intel，封裝目標 macOS 11+；
原生驗收為兩種架構的 macOS 15，其他版本與實機仍須確認。
本版只有 ad-hoc 完整性簽章，沒有 Developer ID／Apple 公證。
首次開啟或被安全政策阻擋，請先看：
https://github.com/azx4121/facility-studio/blob/main/docs/signing.md

第一次使用
先選一個工具 → 填數值與單位 → 看採用條件 → 計算 → 複製／匯出。
「本工具教學」開啟對應的離線說明。
整案報告從「完整工程工作台 → 新手教學」的前六步開始。
「開啟練習新案」直接載入含分段空調箱的 MAU 範例。
設備表先匯出範本；要計算的設備將「啟用(1/0)」設為 1。

保存與更新
整案 JSON 可接續編輯；TXT／HTML 是供閱讀與分享的報告。
V5.5.8 獨立空調箱可確認保存無效草稿，修正後才能計算或匯出。
更新前先關閉舊 App 再替換；已儲存的專案與復原資料保留。
啟動記錄：~/Library/Logs/Facility_Studio_V5_5/
介面錯誤：~/Library/Application Support/Facility_Studio_V5_5/error.log

用途與授權
結果供工程初估、方案比較與需求整理；正式設計須依現場、設備資料與規範覆核。
公司內部工程工作、收費工程案與計算書交付許可詳 LICENSE／LICENSE_GUIDE.md。
軟體轉售、付費綁售及付費線上軟體服務需另行書面授權。
歷史 MIT 版本與第三方元件的原授權保留。

English
Independent calculators, equipment schedules and a full HVAC/AHU workbench are available.
Open the DMG, drag Facility Studio to Applications, then launch it there.
The runtime and help are bundled. Select English at the top right.
Apple Silicon/Intel macOS 15 passed native acceptance; macOS 11+ is the packaging target.
The app has ad-hoc integrity signing without Developer ID or notarization.
Results are preliminary estimates. See LICENSE for internal company use and paid engineering reports.

Current downloads and help:
https://github.com/azx4121/facility-studio/blob/main/README.en.md
https://github.com/azx4121/facility-studio/blob/main/docs/faq.en.md
Report problems with version, OS/CPU, inputs/units, steps and the full error. Remove client secrets:
https://github.com/azx4121/facility-studio/issues
Historical platform instructions:
https://github.com/azx4121/facility-studio/blob/main/docs/history/macos-v5.5.6-readme.txt
