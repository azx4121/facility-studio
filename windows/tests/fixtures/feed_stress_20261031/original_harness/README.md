# Facility Studio 系統壓力測試包

可重現本次壓力測試。受測版本：基線 `Codex_winter_candidate_source_20261030.zip`（SHA-256 `efba573c…e202efe70`）＋補丁 01～06。

## 需求
- Python 3.12、`pip install psychrolib==2.5.0`（獨立的濕空氣參考）
- 不需要 tkinter 或顯示（只測計算與報告，不測 GUI）

## 執行（在被測的 `Source/windows` 目錄下）
```bash
python /path/to/feed_stress/stress_d.py  3000 d.json    # D 強健性：邊界、非法值、隨機多欄位
python /path/to/feed_stress/stress_ab.py 2000 ab.json   # A/B 濕空氣對 PsychroLib、守恆與水力獨立重算
python /path/to/feed_stress/stress_c.py       c.json    # C 單因子變化的物理方向與比例、停用欄位不影響結果
python /path/to/feed_stress/stress_e.py  1500 e.json    # E 報告數字對計算結果、物理硬限制
python /path/to/feed_stress/stress_f.py       f.json    # F 負荷項手算、設備不得選小、配電不變量
FS_SRC=$PWD python /path/to/feed_stress/mutate.py       # 突變測試：植入 11 種工程錯誤，測試必須抓到
```
全部使用固定亂數種子，結果可重現。每支腳本以 `FAIL` 行或非空的 findings 表示失敗。

## 檔案
| 檔案 | 內容 |
|---|---|
| `fs_lib.py` | 共用：呼叫 `api.calculate`、分類結果（ok／reject／crash）、找出所有濕空氣狀態點 |
| `stress_d.py` | D：每個有效欄位頂邊界與超邊界、15 種亂碼、隨機多欄位組合 |
| `stress_ab.py` | A／B：獨立裁判（PsychroLib、能量／水氣守恆、Darcy–Weisbach／Colebrook） |
| `stress_c.py` | C：變因測試 |
| `stress_e.py` | E：報告交叉比對、熱力學硬限制 |
| `stress_f.py` | F：手算與「不可選小」不變量 |
| `mutate.py` | 突變測試驅動 |
| `results/` | 本次最終結果（JSON 與文字輸出） |

## 使用注意
- 這些測試檢查**計算是否正確且自洽**，以及**不會選小**；不檢查模型假設是否適合你的廠房。
- 每支檢查都附容許值；容許值是我依物理與數值精度設定的，不是產品規格。
- 裁判可能寫錯：本次至少有 7 處是我的裁判或測試寫錯，而不是引擎有問題（見報告第 7 節）。新增檢查時請先對照原始碼確認假設。
