# 2026-10-16 修正與驗收證據

公開版本為 V5.6.0：Windows win.4／Mac mac.6。[原生執行、受測提交、公開下載與 SHA256 核對](native-release-verification.json)。

| 真實原生環境 | 交付路徑與逐項紀錄 |
| --- | --- |
| Windows Server 2022 | [三條路徑，每次 248 項](native/windows-2022/summary.json) |
| Windows Server 2025 | [同一 EXE／ZIP 重驗，三條路徑，每次 248 項](native/windows-2025/summary.json) |
| Apple Silicon macOS 15 | [App、系統啟動、ZIP、DMG，四條路徑，每次 241 項](native/macos-arm64/summary.json) |
| Intel macOS 15 | [同一 ZIP／DMG 重驗，兩條路徑，每次 241 項](native/macos-intel/summary.json) |

Linux 來源檢查與上述原生驗收分開記錄：[目前來源 CI](ci-source-summary.json)、[win.4 受測來源 CI](ci-source-win4-summary.json)。每套來源包含 4,432 項獨立公式檢查、6,977 項欄位／報告檢查與 314 項真實 Tk 儀表板檢查。

固定 100 組物理情境各重算 20 次：[Windows](windows-cleanroom100-schema12-repeat20.json)／[Mac](macos-cleanroom100-schema12-repeat20.json)，每套 18,451 項檢查；89 組可計算、11 組正確拒絕不成立條件。JSON 所指的 gzip 保存完整逐項紀錄。

[Windows 182 項](windows-native-sequence-source.json)／[Mac 187 項](macos-native-sequence-source.json)為 Linux 上的連續 UI 來源測試。語系檢查是其中的子集，不能加算為另一輪獨立檢查。[Mac 驗收工具的 Linux 自測](macos-host-selftest-source.json)中，237 項可核對項目通過，四項只能在原生 Mac 判定的條件正確回報不可驗證；該檔不代表原生 Mac 通過。

線上 Setup 的 CRC、解壓與內容雜湊檢查屬封裝完整性證據，與公開離線 EXE 的原生執行驗收分開。原生單次互動 5 秒、初次繪製 20 秒及整輪 300 秒限制均保留；先前失敗與取消的候選列在原生核對紀錄中。
