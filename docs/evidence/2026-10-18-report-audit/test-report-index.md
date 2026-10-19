# 測試報告索引

受測提交 `c121cd872af8f52e3ef8963d138b54b2e7fa8333`；同一 EXE SHA256 `c91509784295e5c0a42a2148cec6a2aa12108e47203113e7c86eb37eb24d3d56`。兩主機 × 三啟動路徑均通過；[完整原生摘要](native-summary.json)。

## 封裝 EXE：逐項原生報告

| 主機 | 啟動方式 | 核心 321 | 延伸 142＋數值 2,182＋語意 405＋匯出／PV 28 | 交付／CLI 10 |
| --- | --- | --- | --- | --- |
| Windows Server 2022 | standalone | [JSON](native/windows-2022/standalone/Windows_Acceptance.json) | [JSON](native/windows-2022/standalone/Windows_Audit_Acceptance.json) | [JSON](native/windows-2022/standalone/Delivery_Check.json) |
| Windows Server 2022 | zip-extracted | [JSON](native/windows-2022/zip-extracted/Windows_Acceptance.json) | [JSON](native/windows-2022/zip-extracted/Windows_Audit_Acceptance.json) | [JSON](native/windows-2022/zip-extracted/Delivery_Check.json) |
| Windows Server 2022 | unicode-executable-path | [JSON](native/windows-2022/unicode-executable-path/Windows_Acceptance.json) | [JSON](native/windows-2022/unicode-executable-path/Windows_Audit_Acceptance.json) | [JSON](native/windows-2022/unicode-executable-path/Delivery_Check.json) |
| Windows Server 2025 | standalone | [JSON](native/windows-2025/standalone/Windows_Acceptance.json) | [JSON](native/windows-2025/standalone/Windows_Audit_Acceptance.json) | [JSON](native/windows-2025/standalone/Delivery_Check.json) |
| Windows Server 2025 | zip-extracted | [JSON](native/windows-2025/zip-extracted/Windows_Acceptance.json) | [JSON](native/windows-2025/zip-extracted/Windows_Audit_Acceptance.json) | [JSON](native/windows-2025/zip-extracted/Delivery_Check.json) |
| Windows Server 2025 | unicode-executable-path | [JSON](native/windows-2025/unicode-executable-path/Windows_Acceptance.json) | [JSON](native/windows-2025/unicode-executable-path/Windows_Audit_Acceptance.json) | [JSON](native/windows-2025/unicode-executable-path/Delivery_Check.json) |

所有路徑均啟用 Python 網路審核封鎖，並移除外部 Python。standalone／zip-extracted 另有作業系統出站防火牆規則；中文路徑的 `firewall_outbound_blocked=false`，不宣稱該規則覆蓋，獨立驗證 Unicode 啟動與網路審核。各項布林值保留在交付 JSON。

## 同一 EXE 的十項 CLI 範例

下列為 Server 2022 standalone 的實際 CLI 輸出；其他主機／路徑的十項執行由各自交付記錄核對，不將重複執行算成不同設計案例。

| 工具 | 計算 JSON | 實際 TXT 報告 |
| --- | --- | --- |
| electrical | [JSON](native-cli-windows-2022-standalone/electrical.json) | [TXT](native-cli-windows-2022-standalone/electrical.txt) |
| duct | [JSON](native-cli-windows-2022-standalone/duct.json) | [TXT](native-cli-windows-2022-standalone/duct.txt) |
| gas | [JSON](native-cli-windows-2022-standalone/gas.json) | [TXT](native-cli-windows-2022-standalone/gas.txt) |
| lighting | [JSON](native-cli-windows-2022-standalone/lighting.json) | [TXT](native-cli-windows-2022-standalone/lighting.txt) |
| water | [JSON](native-cli-windows-2022-standalone/water.json) | [TXT](native-cli-windows-2022-standalone/water.txt) |
| air | [JSON](native-cli-windows-2022-standalone/air.json) | [TXT](native-cli-windows-2022-standalone/air.txt) |
| units | [JSON](native-cli-windows-2022-standalone/units.json) | [TXT](native-cli-windows-2022-standalone/units.txt) |
| cleanroom | [JSON](native-cli-windows-2022-standalone/cleanroom.json) | [TXT](native-cli-windows-2022-standalone/cleanroom.txt) |
| heat_loads | [JSON](native-cli-windows-2022-standalone/heat_loads.json) | [TXT](native-cli-windows-2022-standalone/heat_loads.txt) |
| pumps | [JSON](native-cli-windows-2022-standalone/pumps.json) | [TXT](native-cli-windows-2022-standalone/pumps.txt) |

## 來源與反算

- [兩個原生 Windows 來源主機：CP1252、UTF-8 mode 0](native-source-summary.json)
- [來源 preflight 索引：全欄位、工程覆核、18＋2 案例、壓力測試、教學](source-windows-2022-preflight-index.json)
- [Linux 來源檢查與本輪重跑範圍](source-local.json)
- [24 份中英文 TXT／HTML 範例與 SHA256](reports/index.csv)
- [PV 流量與補風 11 項反算](pv-flow-crosschecks.json)
- [來源文字 I/O 覆核](locale-io-review.json)
- [交付檔 SHA256／PE／ZIP 檢查](distribution-verification.json)
- [未發布候選與畫面／編碼失敗記錄](render-investigation.json)

原生報告保存所有個別檢查名稱、結果、案例與畫面取樣；來源報告及設計範例分別標示主機，不以 Linux 畫面充作 Windows EXE 證據。

[完整原生圖片清單與 SHA256](native-image-manifest.json)：保留六次啟動的所有原生擷取，包含畫面觀測的每一張嘗試與最終圖。
