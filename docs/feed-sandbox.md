# Facility Studio 工程驗證沙盒 5.6.1-1

以公開 main `2c7f37c3957d77fa37f88564fd05d4f287171404`／mac.8 工程核心為基礎，在獨立分支新增功能。未納入原本機 main 領先的兩筆提交，不合併 main、不建立 Release；GitHub Actions 只產出 14 天保留的沙盒測試證據與安裝包，不使用付費模型 API、帳戶密鑰或公司資料。

## 使用

- 主畫面的「工程驗證沙盒」：液態水管分析、九類單位換算及合成 AHU 案例。
- 冷熱水快算填完條件後，可在沙盒帶入其水量、選定內徑與管路資料。水溫、絕對壓力和系統邊界需明確確認；不從缺少的原資料猜測。
- 每個 AHU 視窗的「工程驗證沙盒」：擷取該 AHU 目前輸入。之後修改原 AHU，必須重新讀取；匯出會拒絕過期快照。
- 可另存 TXT、HTML、JSON。既有目的檔案會被拒絕覆寫；JSON 保留輸入、雜湊、版本、門檻與結果，HTML 會跳脫外來文字。
- 新 App 名稱、識別碼及版本號與正式版分開；預設資料在 `~/Library/Application Support/Facility Studio Sandbox`，原版設定與專案不受影響。

## 工具擇優結果

| 工具 | 本版選用 |
| --- | --- |
| PsychroLib 2.5.0 | 從 T/RH/P 重算含濕比與焓，對照 AHU 節點及空氣側段落熱量；乾空氣流量亦依同一設計風量基準獨立重算，另列空氣側熱量／水量平衡 |
| CoolProp 8.0.0 | 第二種濕空氣模型；單相純水密度、黏度與比熱 |
| fluids 1.3.1 | Darcy 摩擦因子、Reynolds 數與管路壓損新分析；保留原關聯式同物性結果供比較 |
| Pint 0.26.2 | 體積流量、熱功率、壓力、長度、溫度、質量流量、能量、密度及動力黏度 |
| Hypothesis 6.170.14 | 開發與 CI 的單位往返、管長與壓損性質測試；不嵌入執行 App |
| python-hvac 固定 commit | 獨立 Python 3.12／Pint 0.24.4 參考測試。其濕空氣物性使用 CoolProp，不重複放入 App，也不算獨立於 CoolProp 的第三套結果 |

原工程核心 ahu_engine.py、engine.py、utils.py、winter.py 保持原樣；新方法在沙盒中提供比較與新計算，避免在尚無原廠性能資料時改寫舊設計輸出。氣體可壓縮流、冷媒設備設計、混合液與管網求解未列入此純水功能。

## 數值驗證與工程狀態

AHU 報告分開呈現「原模型工程品質」及「內部數值比較」。原版預設合成情境本來就有未達條件，不會修改狀態來湊通過數；報告會列出未達／待資料的原因與欄位。

濕空氣門檻為**專案內部回歸／模型差異篩檢**，不是法規、業主要求或 FEED 設計驗收值：

| 比較 | 絕對門檻 | 相對門檻 |
| --- | --- | --- |
| PsychroLib 含濕比 | 1e-8 kg/kg 乾空氣 | 0.02% |
| PsychroLib 焓 | 0.001 kJ/kg 乾空氣 | 0.02% |
| CoolProp 含濕比 | 1e-6 kg/kg 乾空氣 | 1% |
| CoolProp 焓 | 0.15 kJ/kg 乾空氣 | 1% |

門檻為絕對值＋相對值×參考值。PsychroLib 與原模型接近同一理想氣體公式；CoolProp 考量不同的濕空氣模型，因此另列差異。超限必須保留報告，不直接判工程通過。平衡核對仍使用原模型段落熱量與加除濕量，不等同完整設備能量模型；設備能力、凝結水能量與加濕熱源仍須另行驗證。

水管分析限單相純水與明確圓管內徑。2040≤Re<4000 標為過渡流需覆核；閉式循環不允許直接加入樓高。低壓高溫蒸發情況會被拒絕，不把水蒸氣當液水計算。

工程依據與工具來源：[PsychroLib API](https://psychrometrics.github.io/psychrolib/api_docs.html)、[CoolProp 濕空氣](https://coolprop.org/fluid_properties/HumidAir.html)、[fluids Darcy 摩擦因子](https://fluids.readthedocs.io/fluids.friction.html)、[Pint](https://pint.readthedocs.io/)、[python-hvac 原始碼](https://github.com/TomLXXVI/python-hvac/tree/94247560a667905bfbf67e45a58965a58254fce8)。

## 可重現測試與封裝

`macos/tests/test_feed_sandbox.py` 涵蓋 Hagen–Poiseuille 層流解析解、Colebrook 隱式方程殘差、獨立單位固定值、原計算結果保留、16 個 AHU 合成情境、NaN/Infinity/錯誤相態拒絕、快照過期、錯誤後修正、報告不覆寫及 HTML 跳脫。Hypothesis 每個性質各 100 例。實際通過數以當次 CI／本機日誌為準。

`.github/workflows/feed-integration-sandbox.yml`：Linux 合成數值與 Tk 虛擬畫面、隔離 python-hvac、macOS 原生 Universal 打包／完整自測，以及在 Intel 執行相同交付 ZIP。未使用 `pull_request_target`、不讀 secrets、權限限 `contents: read`，沒有 publish 工作。

`macos/macos/feed_runtime_manifest.json` 固定官方 PyPI 下載 URL 與 SHA-256，兩架構同版本；最低 macOS 12 是新 SciPy arm64 wheel 的條件。建置器驗證雜湊後才放入 App。App 使用 ad-hoc 完整性簽章，尚未取得 Developer ID 或 Apple 公證，正常首次開啟仍可能被 Gatekeeper 阻擋；不會關閉安全機制。Apple 信任、公證、工程簽核與 ChatGPT／Claude／Gemini 審查各自列為不同門檻，不能由 CI 綠燈取代。

Claude、Gemini 依使用者指示暫停，不會自動重試或消耗模型用量。三平台評閱可在恢復用量後針對這個草稿 PR、固定 commit、案例與報告進行。此工作流程不虛稱已完成三方審查。

本沙盒新增介面依需求採繁體中文；既有雙語功能保留。bilingual.py 對既有模組的檢查保留，明確排除新增繁中專用模組，其介面另由沙盒測試覆蓋。

作者標示保留 ANDY HUANG ©，繁中呈現為「設計」。文字裁切與原生驗收以作者姓名辨識，不再依賴英文 DESIGNED 定位。

Tk 8.6 自動附加的原生應用程式選單亦以 AppKit 的公開 title 屬性繁中化；僅改本 App 的標籤，保留動作、快捷鍵與系統服務，不更動 macOS 設定。原生自測會核對該子選單，而非只檢查頂層選單。
