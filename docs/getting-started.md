# 安裝與起步｜Facility Studio

[English](getting-started.en.md) · [圖解導覽](visual-tour.md) · [首頁](../README.md)

## 1. 先找到正確成品

到 [Releases](https://github.com/azx4121/facility-studio/releases)選擇您要的版本，展開 **Assets**。以該版列出的平台、架構、狀態及 SHA256 為準；教學 ZIP 和 GitHub 自動產生的 **Source code** 壓縮檔不是可直接執行的成品。

- **Windows x64：**選該版明列的 installer 或 portable ZIP。
- **Apple Silicon Mac：**5.7.3 的平台目標是 ARM64 `.app` ZIP，不是 Intel／Universal／DMG。
- **Prerelease／候選：**表示該附件仍依其說明限制使用，不把候選包當作正式全驗收版。
- 如果該版本尚無所需平台成品及 SHA256，就不要以文件標題推定已提供下載。舊版 win.10／mac.8 與新來源分開看。

## 2. 核對 SHA256

在下載資料夾開啟終端機，以實際檔名取代下方占位名稱，完整比較 Release 公布的 64 位十六進位 SHA256。這些指令只讀取檔案，不會安裝軟體。

Windows PowerShell：

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\下載檔名.zip'
```

macOS Terminal：

```sh
shasum -a 256 '/完整路徑/下載檔名.zip'
```

檔名相同不代表內容相同；若雜湊不符，停止使用，重新核對版本與來源。SHA256 只比對檔案身分，不等於可信發行者簽章或 Apple 公證。

## 3. 完整解壓或安裝

**Windows 安裝版：**選新的空目錄，不覆蓋舊程式或專案。**Portable：**完整解壓到新資料夾，再執行其中 EXE；不要只複製 EXE 或直接從 ZIP 開啟。

**Mac：**完整解壓 ZIP，保留 `.app` 套件內的所有內容，依附件說明開啟。包裝內若另有使用說明、證據或雜湊檔，也一起保留。首次啟動若遇安全提示，先核對[簽章與安全說明](signing.md)，不要關閉 Gatekeeper、防毒或系統保護。

成品包含 Python 執行環境，不需要另外安裝 Python。從原始碼開發則另看[開發文件](development.md)。

## 4. 用練習副本完成第一輪

1. 在程式內核對版本，切換繁體中文或 English。
2. 從[離線教學](tutorial/README.md)開第一案，先另存自己的副本。
3. 依[六步流程](visual-tour.md#workflow)填條件、重算並閱讀工程狀態。
4. 保存整案，再匯出報告。更改上游後，需明確重新帶入下游。

5.7.3 正式入口的預設資料目錄是使用者家目錄內的 `Facility Studio Data-5.7.3`。升級前另行備份舊資料，不假設較舊程式可讀新版格式。詳細見[資料保存與回退](faq.md#saving)。

## 5. 開不起來時，提供這些資料

在 [Issues](https://github.com/azx4121/facility-studio/issues)提供 Release 連結、完整附件檔名、SHA256、作業系統／CPU、程式版本、重現步驟與錯誤文字。先移除公司／業主資料、個人路徑與敏感資訊；不要公開原始專案。若是數值問題，另提供可公開的最小輸入、單位、預期公式與實際結果。

**DESIGNED BY ANDY HUANG ©**
