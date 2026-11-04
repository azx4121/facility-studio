# C2 BF／出風可達條件納入自動風量搜尋

這是 C2 可行性傳遞、真空抽速、停用水洗欄位與 NP 馬達構成四項修復之後的獨立追加修訂。沒有改寫原四修復 patch 或安裝檔。

## 根因與變更

原混風 AHU／FCU／RCU 自動搜尋只用最低 ADP、送風含濕比、乾球與露點作停止條件；搜尋停止後，最終盤管求解器才加入指定 BF 下限。因此某些有較高風量可行解的輸入，被低風量候選的正常 ValidationError 提早拒絕。另有含濕條件雖符合，但該 BF 下盤管最低可達乾球高於送風目標的漏解，不能只補 BF 含濕公式。

- 抽出共用的 C1 出口及 C2 求解函式，讓每個搜尋候選與最後 condition_air 使用相同混風、實際預冷出口、BF／ADP、乾球可達範圍與再熱設定。
- 禁止再熱時，reheat_required 不能作為可接受候選，錯誤定位 allow_reheat；最後實際盤管、再熱、加濕及熱量守恆檢核保留。
- 保留原 F-1 固定總產濕判據及解析無有限解檢查。額外防止巨大風量把含濕比差稀釋到 C2 helper 的 1e-10 kg/kg 閾值以下，卻仍有高於固定解析度的淨 kg/s 除濕需求。
- 以實際 C2 約束導致增風時，報告主導條件為 C2 ADP／BF 與出風可達條件。原解析降水溫建議沒有納入 BF／C1，故這類案件不再提供看似保證能解決問題的單一溫度。
- 原 160 步、每步 ×1.08 的有界搜尋保留。二分只細化局部 false／true 區間，保留可行上端，不聲稱完整可行域全域單調。耗盡時只表示搜尋範圍內未找到，不宣稱任何風量都不可能。

## 重現與物理結果

共同輸入為一般混風 AHU、室內22°C，沿用其他預設。

1. RH40%、30人、CHW6.5°C、BFmin=.1，自動風量現在為9.2705776586 kg/s，BF=.10000000000014。原案例雖填製程8kW，未選「已知潛熱 kW」，實際只計人員1.65kW潛熱；不能誤稱已計8kW製程負荷。
2. 同案真正啟用8kW製程潛熱後，風量36.2304271909 kg/s、BF=.10000000000491。風量是原基準5.92倍，既有工程品質仍判未達；找到盤管解不等於設備或整體設計合格。
3. RH45%、5人、CHW5°C、BFmin=.3，現在找到6.6121249445 kg/s、不需再熱。獨立10,001點ADP掃描重建原12.1933°C目標低於最低可達13.1934°C的問題。

單一 C2、無預冷、淨除濕且 w_room>w_ADP 時，可獨立以質量守恆取得必要風量下界：

`m_min = [G + B*m_oa*(w_oa - w_room)] / [(1-B)*(w_room - w_ADP)]`

它不是一般雙盤管或禁止再熱的充分條件；修復實際使用完整盤管模型。獨立驗證另核對混風、C1/C2 的含濕量與焓混合、露點／不過飽和、再熱與整體空氣側能量守恆。

## 回歸

```sh
FACILITY_TEST_PLATFORM=macos python -m pytest integration/test_c2_airflow_search.py integration/test_engine_review_guardrails.py -q
FACILITY_TEST_PLATFORM=windows python -m pytest integration/test_c2_airflow_search.py integration/test_engine_review_guardrails.py -q
python macos/tests/airflow_guard_checks.py
python windows/tests/airflow_guard_checks.py
python tools/verify_platform_sync.py
```

新增BF回歸32個案例，包含F03兩種潛熱模式、8個F04反例、BF邊界、實際C1出口、F-1、不允許再熱、允許的直接解、3種極小產濕量的禁止／允許再熱對照；與前四修復51個案例合計每平台83測試。已加入工程儀表板CI。

獨立覆核每平台56個案例（40接受、16受控拒絕）數值一致；3個普通BF0案例與修復前完整summer結果相同。最小含濕差4.27e-15 kg/kg仍沒有逃過淨除濕保護。F04邊界的最大獨立C2焓殘差約5.13e-7 kJ/kg，來自原solver明列5e-7 K乾球容差，並非嚴格零；此修訂沒有放寬solver容差。

來源測試及有限域抽樣不能證明搜尋必定找到每個狹窄／孤立可行區間。沒有原生App／EXE、GUI、原廠能力、法規或完整FEED驗收，沒有公開推送或發布。
