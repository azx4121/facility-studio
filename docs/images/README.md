# 圖解與截圖來源 / Diagram and screenshot provenance

<a id="v573-v22-r3"></a>
## 5.7.3 v22 r3：真實 macOS 候選畫面 / Actual macOS candidate

**狀態 / Status: UNVALIDATED-COMPILE-ONLY candidate.** 已完成原生啟動及部分畫面檢視，不是全功能、全部數值、英文排版、完整匯出或正式 FEED 驗收。 / Native launch and selected screens were checked; full functional, numerical, English-layout, complete export and formal FEED acceptance remain incomplete.

- 平台 / Host: macOS 27.3 (26C5035r), Apple Silicon arm64；bundle 的 Tk script 要求 / bundled Tk script requirement: 9.0.4。
- App 身份 / Identity: CFBundleShortVersionString `5.7.3`；CFBundleVersion `5.7.3.2`；CFBundleIdentifier `com.facilitystudio.diagnostic.compileonly.v22`。
- 執行檔 / Executable SHA256: `d5cdf2e018ff5836cbd69b9d3faf893afee77962eb5250fbcc0115749b8ac0e5`。已與交付 ZIP 內同檔核對 / Matched against the same executable inside the delivered ZIP。
- 候選封裝 / Candidate ZIP: `FACS-v22-r3-UNVALIDATED-COMPILE-ONLY-macOS-arm64.zip`；SHA256 `26dcbac483b5c039486af1d88b750ba7dda5f11dbb9965e88fabc08d0236643a`。這是成品身分記錄，不是公開下載連結 / This identifies the artifact; it is not a public download link。
- v22 source inventory SHA256: `7c3ef3f66382fa44e5ba6e57f11f04083295c506c4da6a8e2036e730d7c1914f`。尚無已核對的 Git commit 對應；不得標示本倉庫 main 為此候選的編譯來源 / No verified Git commit mapping is available; do not identify repository main as this candidate's build source。

檔案格式已核對 JPEG 標頭與影像解碼。兩張繁中擷取交付檔名原為 `.png`，此處只更正為 `.jpg`，保留原始 bytes 與 SHA256，未重新編碼。 / JPEG signatures and decoding were verified. The two supplied Traditional Chinese captures had `.png` filenames; only the repository extension was corrected to `.jpg`. Original bytes and SHA256 are unchanged, with no re-encoding.

**擷取方式 / Capture method:** 在原生 Mac 上開啟上述精確 App，直接擷取其應用程式視窗。三張均為 2880 × 1716 原始 JPEG，兩張繁中、一張英文，使用內建範例與測試輸入，未裁切、重繪、覆蓋字樣或更改版本；已目視檢查無私人桌面或檔案路徑。 / Direct native application-window capture of the identified App. The three original JPEGs show two Traditional Chinese screens and one English screen with built-in samples and test inputs. No cropping, repainting, overlays or version-label changes were applied. Visual review found no private desktop or file paths.

| 原圖 / Original | Bytes | SHA256 |
| --- | ---: | --- |
| [facs-5.7.3-v22-macos-arm64-electrical-zh-Hant.jpg](facs-5.7.3-v22-macos-arm64-electrical-zh-Hant.jpg) | 613544 | `1df86f13d74399cc8d73ebda4831eb1bc630919f29ca37fe84dba304ffdd7e86` |
| [facs-5.7.3-v22-macos-arm64-workbench-zh-Hant.jpg](facs-5.7.3-v22-macos-arm64-workbench-zh-Hant.jpg) | 460804 | `e111aec436ea4c424513c98291f4f9ef1b1e8d931435196e994b7f341507e645` |
| [facs-5.7.3-v22-macos-arm64-vacuum-en.jpg](facs-5.7.3-v22-macos-arm64-vacuum-en.jpg) | 565086 | `e4dff050894057c8e8264d0eda781c5ac007c9b4c5906b75c9fbfa03f4ffb464` |

JPEG 存檔時間 / JPEG save times (UTC): electrical `2026-11-08T09:28:35.998Z`；workbench `2026-11-08T09:33:37.182Z`。實際擷取略早，不把存檔時間當成精確擷取時間 / Capture occurred shortly before saving; these are not exact capture timestamps。

英文 PV 圖的實際擷取區間 / English PV capture interval (UTC): `2026-11-08T09:44:49.653Z` to `2026-11-08T09:44:49.711Z`。在 App 介面切換 English 後擷取，PV 流量為測試輸入 100 SLPM / Captured after switching to English through the App UI, with a 100 SLPM PV test input.

**觀察範圍 / Observation scope:** 原生啟動、About 5.7.3、電力預設頁、風管工具切換、工作台及英文報告頁開啟、單一 PV 案例核對、英文 TXT 匯出、取消後重開匯出、工作區 JSON 保存、內建 MAU/AHU 練習案載入及 AHU 管理開啟。電力圖保留配線選型暫停；工作台與英文圖保留「未達條件」。 / Partial checks covered native launch, About 5.7.3, default electrical screen, duct navigation, workbench and English report opening, one PV case, English TXT export, cancelling/reopening export, saving workspace JSON, loading the built-in MAU/AHU practice case and opening the AHU manager. Wiring selection remains suspended; the workbench and English screen retain the conditions-not-met state.

**已知限制 / Known limitations:** 英文側欄長標籤在本次尺寸有截斷；AHU 管理視窗預設高度下的底部按鈕文字亦觀察到裁切，尚未縮放覆核。工作區重新開啟與單機 AHU 細測尚未完成。不得推論全功能、全部數值、英文排版或完整匯出已驗收。 / Long English sidebar labels are clipped at the captured size. Bottom-button text was also observed clipped in the default-height AHU manager, with resizing unreviewed. Workspace reopening and detailed individual-AHU checks remain incomplete. These observations are not full functional, numerical, English-layout or complete export acceptance.

[繁中真實畫面](../visual-tour.md#screenshots) · [Actual screens with English captions](../visual-tour.en.md#screenshots)

## 現行文件圖解 / Current documentation illustrations

2026-11-08 新增六張 SVG：功能入口、六步流程、AHU 需求與容量邊界，各有繁體中文及英文。內容對照來源提交 `01e0a3239e1dc962e76d8c23a91a2f623eaebe95` 的 README、workbench 與 AHU 指南。圖解為可閱讀的向量文件，非介面截圖，不是原生成品或 FEED 驗收證據。無外部字型下載、外部圖片或腳本；使用系統字型。原始 SVG 已以 Inkscape 渲染並目視檢查。

Six SVG illustrations were authored on 2026-11-08 against the named source commit: overview, six-step workflow and AHU boundaries, each in Chinese and English. They are explanatory diagrams, not UI screenshots or native/FEED acceptance. They contain no scripts, external images or font downloads. They use system fonts and were rendered with Inkscape for visual review.

[繁中圖解導覽](../visual-tour.md) · [English visual tour](../visual-tour.en.md)

| 圖解 / Diagram | SHA256 |
| --- | --- |
| [ahu-boundary.en.svg](diagrams/ahu-boundary.en.svg) | `7d54373df0b2118b617c437b180b45f0d7a65a612ac7f736612529eb5f5f6c8b` |
| [ahu-boundary.zh.svg](diagrams/ahu-boundary.zh.svg) | `c58316d5d5854bcd0bc2778ce7c81de644a117337ee2dc16b120e7446d8b75e2` |
| [overview.en.svg](diagrams/overview.en.svg) | `951913256ea149a92bbef3a4650641c609761ed8de44122820fd3b803212915d` |
| [overview.zh.svg](diagrams/overview.zh.svg) | `126259558e077e63b20e722177500607c1e9fcf0946a09280bc9fc092349df35` |
| [workflow.en.svg](diagrams/workflow.en.svg) | `81e12da4e7e627e93696e94853d1e7be59ff0015ba5d0f1f6872877d026bc21c` |
| [workflow.zh.svg](diagrams/workflow.zh.svg) | `de11fba07a22cd2a30bf31aa2c03673043f0f41de9ae295f75731db0e0b983fe` |

<a id="historical-screenshots"></a>
## 歷史介面截圖 / Historical screenshots

**歷史圖片 / Historical images.** Each image below belongs to its named version/host/source. The 5.7.3 candidate is documented separately above. Do not relabel these historical pixels as current acceptance. [5.7.3 status](../verification/5.7.3-release-acceptance.md).

## 歷史首頁圖片：win.10／mac.8 開啟後的原生畫面（2026-11-01）

- `v560-win10-native-zh.png` SHA256 `0885812517b5fcbbe111d9a103d683fc5f103995645964169be44c35c1395de2`
- `v560-win10-native-en.png` SHA256 `079302504860ba83b3d1aa1be65ecd8e58370a85465280025d3ff00c6d2fee15`
- `v560-mac8-native-zh.png` SHA256 `d470f6a92b4f344f5ede892a4f384652cc782d145e402fd0b16c415369f36f03`
- `v560-mac8-native-en.png` SHA256 `a40901854a329f54991860735898048da6632d8b7537fcf9756ba370a61dd861`

來源：Actions 流程 [Capture native UI screenshots（run 41278438651）](https://github.com/azx4121/facility-studio/actions/runs/41278438651)。流程下載**已發布**的 v5.6.0-win.10 EXE 與 v5.6.0-mac.8 DMG，核對 SHA256SUMS，各在 Windows Server 2022、macOS 15 的原生桌面上用 `tools/capture_native_ui.py` 啟動（僅預先寫入語言偏好檔，未改程式、未操作畫面），等視窗出現並再等 8 秒後擷取該視窗，未裁切、未重繪。畫面為第一個工具（電力配線）的預設輸入。

限制：這是 GitHub 託管的虛擬桌面，不是實體電腦；Windows 為 100% 縮放；macOS 視窗標題列呈未取得焦點的灰色，為擷取當下狀態。兩平台字型（Windows：Microsoft JhengHei UI／Consolas；macOS：PingFang TC／Menlo）與視窗外框由系統提供，所以不會逐像素相同；已知的小差異：Windows 的文字換行位置略不同、語言選單與選取項目的字重不完全相同。

English: these historical homepage images show the published win.10 EXE and mac.8 DMG started on native desktops (GitHub Actions run 41278438651: Windows Server 2022, macOS 15) with `tools/capture_native_ui.py`, which only pre-sets the language preference file, waits for the window plus 8 s and captures that window, uncropped and unretouched, default inputs (SHA256 values above). Limits: hosted virtual desktops, not physical machines; Windows at 100 % scaling; the macOS title bar is grey because the window had no focus. Fonts and window frames come from each system, so the two platforms are not pixel-identical; known small differences: line-wrap positions on Windows and the weight of the language selector and selected navigation item.

## 歷史：win.9／mac.7 開啟後的原生畫面（2026-11-01，文字大小與 mac.7 不同）

- `v560-win9-native-zh.png` SHA256 `808801baed04e1cc012936349c6e574f532fbc3953ba5531a3f9f61399992cc7`
- `v560-win9-native-en.png` SHA256 `82c9588fc3eabf78b48905d0414dbdcbbd47a089d1371b9659fcf04cc11d43a9`
- `v560-mac7-native-zh.png` SHA256 `13585315b87bed455aaa0e50c3afe9b857fb6ea6efefe1151366bd9ca3531358`
- `v560-mac7-native-en.png` SHA256 `5a6d6bf4c0af98027f5f5d250aa96ece904a9951c848a59b38269753232f6af3`

## V5.6.0 介面示意：win.4／mac.6 來源

- `v560-dashboard-source-zh.png`（繁體中文）：SHA256 `38c2e46f6e5684d425527b3951fbb6677ac827ef27614daa252fbb436abd06fb`。
- `v560-dashboard-source-en.png`（English）：SHA256 `9f355848884bcb84c05dfacbfa54ec150e6c549cd7d7abbef86bbf18b09ef01a`。

2026-10-16 覆核後 Windows 來源樹的真實畫面，於 Linux x86_64／Tk 8.6.14／1360×960 擷取。十項快算直接列於左側，使用合成潔淨室資料。未以此圖冒充原生 Windows／Mac 交付檔；首頁圖說亦標示來源。

These are actual Windows-source screenshots on Linux/Tk, with ten sidebar calculators and synthetic data. Native binary acceptance is recorded separately in the [integration review](../2026-10-16-gemini-integration-review.md).

## V5.6.0 win.4 原生驗收

- `v560-win4-native-en.png`：SHA256 `931e915ed4d992eb5c401ed582b6ceebd315985bc90f62d141c9e5fa816d11f8`。

來自 [Windows win.4 原生驗收](https://github.com/azx4121/facility-studio/actions/runs/38910619703)第二環境（Server 2025）standalone 的 `English_Electrical.png`，直接複製、未裁切或重畫；使用合成資料。背後視窗與桌面是驗收環境的一部分。受測與公開 EXE SHA256 均為 `49a04498b8353f4ef1f0d202de48576af925502dff202c232d2356b02a48a802`。

## V5.6.0 mac.6 原生驗收

- `v560-mac6-native-en.png`：SHA256 `5e1970608078d24d93ee0885b49217394ca7ba6b46057b380901cd56f76cfe31`。

來自 [Mac mac.6 原生驗收](https://github.com/azx4121/facility-studio/actions/runs/38922689461)Apple Silicon 建置的 `English_Electrical.png`，直接複製、未裁切或重畫；使用合成資料。受測 Mac 來源為 `4eabd9ce7cb6c275f588309ab0faf39ef0ea9b91`，與 Windows 來源／Linux 圖分開標示。

## 歷史 V5.6.0 win.3

- `v560-win3-electrical.png`：SHA256 `8dcb6168fbaabe691707731ea8e704f0938d72e9bbabac126f230393ce8ca233`。
- `v560-win3-electrical-en.png`：SHA256 `43a589025f52105e90a3cd22c5c9b71747bc28605687322d1151d2d501c23875`。

來源為[實際Windows原生驗收](https://github.com/azx4121/facility-studio/actions/runs/38287263700)的standalone截圖，直接複製，沒有裁切、重畫或修改。畫面顯示V5.6.0及七個直接快算；桌面與後方視窗為測試環境。

These are unmodified screenshots of the deliveredV5.6.0 win.3EXE. Earlier images retain their historical provenance below.

## 歷史V5.5.8

- `v558-windows-electrical.png`：Windows 中文電力工具，SHA256 `20373db19ff6deb87b7a7da1109d6078a40878e881412698c2a10ecbd9d1131c`。
- `v558-windows-electrical-en.png`：同版英文介面，SHA256 `0f3a8ae3118096dfd45aa6f44e3baa1137b206d68cb6e9eb5c58ab16e1a661ee`。

兩張都是 [Windows 原生驗收](https://github.com/azx4121/facility-studio/actions/runs/38024376406) 的 `native/standalone` 實際截圖，原檔直接複製，未裁切、重畫或修改畫面。教學使用合成資料；系統桌面與背後其他視窗屬當時測試環境。

Both are unmodified screenshots from the released V5.5.8 Windows native-acceptance run, rather than interface mockups. Earlier images in this folder retain their original version context.

## V5.6.0 win.5 原生驗收

- `v560-win5-native-en.png`：Windows Server 2022 實際執行 win.5 的英文電力頁，使用合成資料；直接複製原始截圖，保留驗收桌面與背景視窗。
- 來源：[win.5 Windows 原生驗收](https://github.com/azx4121/facility-studio/actions/runs/39050546260)，build-evidence 的 `standalone/English_Electrical.png`。
- 圖片 SHA256：`a585574af10bb9b72e7252e679a99d4eb9843443c269f38e1d198f193b9e8080`。
- 受測 EXE SHA256：`0b308ba4195ffd50a7c6f3341fa7ad72b07b60ae3ea67bc5e443a256f3b3e65f`。

## V5.6.0 win.7 原生驗收

- `v560-win7-native-en.png`：Windows Server 2022 的實際 win.7 EXE，English 電力頁、合成 10 kW 資料；直接複製，保留桌面與背景視窗，未裁切或重畫。
- 來源：[win.7 原生流程](https://github.com/azx4121/facility-studio/actions/runs/39114093849)，build-evidence 的 `standalone/English_Electrical.png`。
- 圖片 SHA256：`28a339419d07143c96a6e5683990476c3826f79de63a164b4e3937bd7bcac109`。
- 受測 EXE SHA256：`f9e3b30fb3f3feb581212822e13cebb9e115ca3893d818f876159c4db3a8e4b9`。
- 結尾 `Windows_Electrical.png` 曾出現空白表單／結果區；這張內容完整的較早英文擷取與結尾重繪觀察分開記錄，見[完整驗收與限制](../2026-10-18-windows-audit-six.md)。

`v560-win7-capture-observation.png` 保存同次 Server 2022 `standalone/Windows_Electrical.png` 的結尾空白區觀察，未修改；SHA256 `55ddf2a5ec704d29b572824cccaa42b3b968d02b9638cdc4fb7512877d8ecfc5`。此圖用於問題記錄，與首頁內容完整的英文擷取分開。Server 2025 同樣觀察見[記錄](../evidence/2026-10-18-audit-six/capture-observations.json)。

## V5.6.0 win.8 原生驗收

來自 [Windows 原生流程 39222780789](https://github.com/azx4121/facility-studio/actions/runs/39222780789) 的 Server 2022、提交 `c121cd872af8f52e3ef8963d138b54b2e7fa8333`；內含 Windows win.8 EXE SHA256 `c91509784295e5c0a42a2148cec6a2aa12108e47203113e7c86eb37eb24d3d56`。所有圖片直接複製原檔，未裁切、重畫或修改，保留桌面與背景視窗，使用合成資料。

- `v560-win8-native-en.png`：`windows-2022/standalone/English_Electrical.png`；SHA256 `303a4b5c7ba7a9afac104ffdcc5b6737095c65d5e490c100a24614965cdc65d1`。
- `v560-win8-native-zh.png`：`windows-2022/standalone/Windows_Electrical.png`；SHA256 `76c8f8a168ee2b18dc14cfeeacfad882b763a2d101da3b21ee8a313542e69660`。
- `v560-win8-native-air-zh.png`：`windows-2022/unicode-executable-path/Windows_Air.png`；SHA256 `11bffd4469d4be1048e7b0d951620d3bb6b8b07198f11ff8153d79a34bf7588b`。

電力與空氣頁是在還原／切換後取得連續可見畫面的最終原圖。更早的取樣與所有時間、映射、像素結果保留在原生 JSON，與 win.7 的歷史空白畫面分開。[完整記錄](../2026-10-18-windows-report-audit.md)
