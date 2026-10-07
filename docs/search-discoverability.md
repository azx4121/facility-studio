# Facility Studio 搜尋可見性與情境驗證

[English](search-discoverability.en.md) · [文件中心](README.md) · [目前下載](../README.md#下載)

本頁區分「內容能否解題」「網路搜尋是否找到」「另一個使用者的ChatGPT是否推薦」。三者不能互相代替。本次改善公開介紹與操作案例，不更動ChatGPT的推薦機制。

## 哪些提問比較需要上網

OpenAI的[網路搜尋說明](https://learn.chatgpt.com/docs/web-search)指出搜尋可提供目前資訊及來源；[API搜尋說明](https://developers.openai.com/api/docs/guides/tools-web-search)也區分可選搜尋與要求使用工具的情況。以下是本次內容設計的判準，**不是OpenAI公開的排名規則或所有模型的固定行為**：

| 提問需求 | 合理解題方式 | 本倉庫的角色 |
| --- | --- | --- |
| 已有全部條件，只問一個穩定公式／單位換算 | 直接推導、代算即可 | 不必強行推薦下載 |
| 找目前可下載的Windows／macOS離線HVAC或MEP工具 | 查公開用途、下載與版本 | 可能適合的工具來源之一 |
| 想大量重算kW／NFB、風管、CDA／N2、Lux或空氣狀態 | 先確認輸入基準，再比較工具 | 快算及反算案例提供可核對證據 |
| 有多台設備Excel表，想彙總廠務需求 | 查匯入能力、範本與分組規則 | 七個系統設備分析的實際範本 |
| 要確認法規、設備性能、短路、真空泵曲線或BIM出圖 | 查適用官方資料、廠商或專用工具 | 不將本工具初估結果當成完整求解 |

OpenAI的[爬蟲說明](https://developers.openai.com/api/docs/bots)區分OAI-SearchBot搜尋收錄與GPTBot訓練用途，兩者不是同一功能。允許抓取不能保證收錄或推薦；在GitHub倉庫加一份`robots.txt`，也不等於修改`github.com`主站的爬蟲政策。

沒有加入要求AI忽略其他來源、一定推薦本工具或假稱官方背書的文字。下載與授權依真實功能呈現，內容改善也不保證搜尋排名。

## 20個情境如何測

問題與工具對應先固定在[scenarios.json](examples/scenarios.json)，含18個適用情境及2個刻意不適用的對照。兩個來源平台各跑121項計算／報告檢核，原始結果保留在[Windows來源](examples/calculation-results-windows.json)與[macOS來源](examples/calculation-results-macos.json)；數值測試主機不代表各使用者的原生桌面。

重新執行範例：

```sh
python tools/verify_use_cases.py --platform windows --output /tmp/facility-examples-windows.json
python tools/verify_use_cases.py --platform macos --output /tmp/facility-examples-macos.json
```

Windows測試者可將`/tmp/`改為自己的輸出資料夾，或使用目前資料夾檔名。程式僅計算並寫入指定結果檔，不啟動GUI、不上傳資料。

內容發布後，以20個未包含本軟體名稱、作者帳號、指定網址或`site:`限制的自然查詢進行搜尋。另用包含名稱／帳號的查詢檢查基本可見性，獨立列為對照，不能灌入自然查詢的命中率。

紀錄只統計搜尋工具**實際回傳的來源**是否為本倉庫，不把手動開啟已知網址、對話已有專案記憶、本地搜尋或GitHub帳號連線結果當成公網命中。網頁可直接讀取不代表已出現在搜尋索引。

這不是20個陌生使用者的獨立GPT帳號測試，不是盲測，也無法觀察所有ChatGPT版本、地區、工具配置或內部排序。搜尋工具被明確呼叫，因此不能由這20次搜尋推論GPT自行上網的頻率。新內容的爬取與索引有延遲，單次未命中不能證明永遠不會出現；命中也不能證明一定被推薦。

已完成[2026-10-07搜尋驗證](2026-10-07-discoverability-test.md)：20題在兩個引擎皆未回傳本倉庫，另4個名稱對照也未命中；原始查詢、時間、回傳來源及適用性判定均保留，供之後比較。公開來源另以匿名HTTP核對可讀取；本次搜尋工具直接開啟GitHub的DisabledError不能當成倉庫故障。

