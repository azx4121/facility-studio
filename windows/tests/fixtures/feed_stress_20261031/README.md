# 原始壓力測試紀錄（2026-10-31）

這是修正 F-1 之前、對基線＋補丁 01～06（commit `63c9f2b`）所做壓力測試的**原始紀錄，保持原樣**。

| 檔案 | 內容 |
|---|---|
| `FEED_stress_report_20261031.md` | 原始評估報告（結論、發現 F-1 與 O-1～O-4、可信度分項、方法學備註） |
| `results/d_final.json`、`d_final.txt` | D 強健性：3,000 組隨機、8,645 次邊界與亂碼 |
| `results/ab_final.json`、`ab_final.txt` | A／B：34,000 個空氣狀態對 PsychroLib、守恆與水力重算（2,000 個案例） |
| `results/c.json` | C 變因 |
| `results/e.json` | E 報告與熱力學硬限制 |
| `results/f.json` | F 手算與「不可選小」 |
| `results/mutation_final.txt` | 突變測試：11／11 被抓到 |
| `original_harness/` | 當時交付的測試腳本（`feed_stress.zip` 的內容） |

注意：這份紀錄寫於修正之前。報告中「整體狀態永遠不會是通過」「F-1 靜默輸出荒謬風量」「冰水餘裕標示不一致」「PV 欄位提示不一致」
等發現，已在其後的修正中處理；修正前後對照見分支上的 commit 說明與 `tests/airflow_guard_checks.py`。
最高狀態的實際名稱是「初估檢核通過」（報告中簡稱「通過」）。

可執行的版本在 `tests/feed_stress/`，由 `tests/feed_stress_checks.py` 驅動。
