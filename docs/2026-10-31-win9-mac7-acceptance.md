# win.9／mac.7 驗收紀錄（2026-10-31）

範圍：F-1 荒謬風量防護、品質閘門、報告、單位與兩個平台的程式碼同步。這是**計算實作與選型合理性**的驗證；規範符合性（FEED、醫院感染控制、藥廠 GMP、電氣法規）**未驗證**，也不宣稱。

## 原生驗收（同一份程式碼 `b3c263b`）

| 平台 | 結果 | 連結 |
| --- | --- | --- |
| Windows Server 2022 建置＋原生執行（斷網、隱藏外部 Python） | 通過 | [run 41191097873](https://github.com/azx4121/facility-studio/actions/runs/41191097873) |
| Windows Server 2025 重驗相同 EXE／ZIP | 通過 | 同上 |
| macOS 15 Apple Silicon 建置、簽章、啟動 | 通過 | [run 41191097271](https://github.com/azx4121/facility-studio/actions/runs/41191097271) |
| macOS 15 Intel 執行相同 ZIP／DMG | 第一次自我測試逾時（300 秒），重跑通過 | 同上（attempt 2） |

原生驗收之後，我又做了只影響發布內容的更動（修訂標示由 `win.9-local` 改為 `win.9`、教學內容重新產生、安裝程式載量重建、發布流程新增測試）。發布流程在 main 上會再跑一次相同閘門，兩個平台都通過才建立 Release。

驗收中發現並修正的問題：Windows 原生字型下最小視窗的 A／B 圖表標示重疊（`text_clipping_checks` 88/90）；`winrelease/verify.py` 的延伸稽核數量為舊值（2182／405，現為 2188／406，兩者都是實測值，仍是精確比對）。

## 20 組情境與 5 組掃描

可重現腳本與逐案結果在 [`windows/tests/engineering_scenarios/`](../windows/tests/engineering_scenarios/)，報告見其中的 `SCENARIO_REPORT.md`。第 1 層（計算實作）15 案通過、5 案因引擎拒絕或無法表達而標 BLOCKED（不算通過）；5 組掃描與事先寫下的預測一致。CR-01 在預設 FFU 下覆蓋率 108％，引擎已正確標「未達條件」。H／P 類案例沒有給負荷，通過只代表算術與規格一致。

優先缺陷：F-1 在匯入基準版可重現（約 7.41×10⁹ CMH），本版被明確拒絕；品質閘門補齊資料後可到「初估完成」；冰水餘裕標示一致；PV 範圍檢查一致；U 值單位已補在欄位、說明與報告。

## 為讓既有檢核適用於 win.9 所做的調整

這些都是更新檢核方式，不是放寬：`tools/cleanroom100_stress.py`（FFU 冬季運轉比例、新的「需再熱」拒絕字樣）、`tools/verify_use_cases.py` 與 `tools/verify_100x_all_fields_and_reports.py`（舊預設值下寫成的案例，改為明列各段設定與欄位啟用條件）、`tests/airflow_guard_checks.py`（基準快照比對容許 1e-9 相對誤差，因 Apple Silicon 與 Linux 的浮點尾數不同；真實變動至少大六個數量級）。教學的練習檔連結雜湊與參考報告已重新產生並通過 `verify_tutorial.py`（兩個平台各 93 項）。

## 已知限制

- 原生驗收不等於實體 Windows 10／11 或實體 Mac；Intel 的自我測試接近 300 秒上限。
- 空調箱預設值已改，舊範例須明列各段設定。
- 拒絕訊息格式不一致（例如乾盤管進水不足的訊息沒有數字）；乾燥外氣下有 1／4,000 的保守誤拒。
- 「初估檢核通過」對有負荷的房間到不了，這是設計。
- 首頁圖片仍是 win.8／mac.6 的原生畫面；新版原生畫面在各次原生驗收的證據包內，尚未複製進 `docs/images/`。
