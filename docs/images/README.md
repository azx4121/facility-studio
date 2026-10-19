# 介面截圖來源 / Screenshot provenance

首頁目前使用 win.8 的原生英文電力頁，標題含 win.8，首頁有 PV 真空按鈕。歷史圖片保留各自來源版本；不得將 Linux 原始碼畫面或舊版畫面當成新版交付檔。[win.8 驗收與畫面觀察](../2026-10-18-windows-report-audit.md)。

Current homepage image: native win.8 English electrical page, with the PV vacuum button and win.8 caption. Historical captures retain their original provenance. See the current acceptance report for capture/repaint limits.

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
