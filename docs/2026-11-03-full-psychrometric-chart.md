# 完整空氣線圖候選功能

本變更只更新 Windows 與 macOS 來源，尚非新的已驗收 EXE／App。

- 主頁保留原本簡圖。「放大空氣線圖」改開完整計算線圖。
- RH 10–100%、等焓、等濕球、等比容、乾球與含濕比網格均依實際絕對壓力計算。
- 提供右側含濕比軸、外側焓刻度、濕球／比容標示與獨立 A／B 狀態摘要。
- 曲線與網格截在飽和邊界及圖界內。預設 −10 至 55°C、35 g/kg；必要時擴展範圍以包含 A／B，仍受既有物性模型限制。
- 支援滾輪縮放、拖曳平移、雙擊適合視窗、工具列放大／縮小／重設、最大化與關閉。線條、文字及狀態點使用同一等比例座標轉換。
- 視窗是開啟當下的快照，主表輸入變更不會移動舊快照。重新開啟會先取得有效結果；無效輸入不開舊結果。
- A／B 連線只比較端點，不保證設備可沿該路徑運行。沒有加入未驗證的 SHR 過程量角器。

## 計算依據

公式與既有計算器一致，採乾空氣基準。等濕球使用冰／液水分段能量平衡，不以等焓線代替。比容為：

`v = 0.287042 × (T + 273.15) × (1 + w / 0.621945) / P`

其中 P 為 kPa(abs)，w 為 kg/kg乾空氣。參考 [PsychroLib SI API 與 ASHRAE 方程說明](https://psychrometrics.github.io/psychrolib/api_docs.html)。非常短的低溫等焓／比容區間以精確乾軸交點加入取樣，避免跨樣點遺漏。

## 重現驗證

在已具專案建置依賴的 Python 執行：

```
python tools/verify_full_air_chart.py --platform windows --output windows-chart.json
python tools/verify_full_air_chart.py --platform macos --output macos-chart.json
python windows/tests/v554_features.py
python macos/tests/v554_features.py
python windows/tests/bilingual.py
python macos/tests/bilingual.py
python tools/verify_platform_sync.py
```

完整線圖測試包含 60／80／101.325／120 kPa、−60／90°C 邊界、冰區、RH 0／100%、相同 A／B、超出預設範圍、各線族反算、曲線裁切、縮放錨點、平移、重設、快照複製及無效狀態原子更新。

`--preview chart.png` 可產生來源 Canvas 幾何的 Pillow 預覽，需 Pillow 與 Noto CJK 字型。這不是原生 Tk 截圖，字型度量為近似。`--gui` 另啟實際 Tk，檢查滾輪、拖曳、重開、輸入無效、快照保持與關閉；需要可用顯示服務。

本次雲端環境無 DISPLAY，已安裝的 Xorg 因 socket 權限限制無法啟動，因此實際 Tk 與 Windows／macOS 原生顯示、DPI、封裝執行尚未驗收。來源／幾何通過不可視為原生驗收。

歷史 `windows/installer/payload` 與 manifest／Setup 是固定雜湊的已發布組，刻意保留不改。候選安裝程式須在後續完整重建時納入新來源，並重新驗證封裝及原生執行，不可混用新 payload 與舊 manifest 或宣稱舊二進位包含此功能。
