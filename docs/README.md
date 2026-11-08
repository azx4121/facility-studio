# Facility Studio 文件中心

[圖解導覽](visual-tour.md) · [安裝與起步](getting-started.md) · [工具索引](guides/README.md) · [離線教學](tutorial/README.md)

## 5.7.3 現行文件

[版本變更與發布契約](releases/v5.7.3.md) · [正式驗收證據格式](verification/5.7.3-release-acceptance.md) · [設計審查](guides/design-review.md) · [容量規劃](guides/capacity.md)

Windows x64 installer／portable、Mac ARM64 ZIP 均須最終成品驗收後才公開。下方日期與 win.10／mac.8 等連結是歷史證據，不能轉用為本次通過聲明。

[win.10／mac.8 畫面一致 / UI unification](2026-11-01-win10-mac8-ui-unification.md) · [win.9／mac.7 驗收紀錄 / Acceptance record](2026-10-31-win9-mac7-acceptance.md) · [Windows win.8 工程修正與原生驗收 / Corrections and acceptance](2026-10-18-windows-report-audit.md) · [win.4／mac.6 整合歷史](2026-10-16-gemini-integration-review.md)

[English](README.en.md) · [首頁與下載](../README.md) · [問題回報](https://github.com/azx4121/facility-studio/issues)

文件目標：**Facility Studio 5.7.3**。此版本的原生驗收與各平台發布狀態，以對應 commit 的 CI 紀錄及 Release 附件為準；只有對應 Release 已提供平台成品及 SHA256 時，該平台下載才有效。先依手上的任務選文件，需要完整工作台時再跟做練習案。

## 開始使用

| 你想做的事 | 從這裡開始 |
| --- | --- |
| 下載、安裝，確認自己的電腦是否適用 | [下載](../README.md#下載) · [相容性與首次開啟](faq.md#compatibility) |
| 解決一個電力、風管、水量等計算問題 | [依需求選工具](guides/README.md) |
| 做出第一份整案報告 | [工作台前六步](guides/workbench.md) |
| 整理整批設備 Excel／CSV | [設備表範本與匯入](guides/equipment.md) |
| 比較空調箱夏冬各段需求 | [單台空調箱指南](guides/ahu.md) |
| 遇到安全提示、開啟失敗或資料保存問題 | [常見問題](faq.md) · [系統安全提示](signing.md) |
| 確認公司使用與分享範圍 | [授權案例](../LICENSE_GUIDE.md) · [完整條款](../LICENSE) |

教學已內建：簡易工具按「本工具教學」，完整工作台按「新手教學」。也可[單獨閱讀／下載離線教學](tutorial/README.md)。

## 查公式、證據或原始碼

| 需求 | 文件 |
| --- | --- |
| 查看操作條件、公式與對照結果 | [20 個情境：18 個計算案例與 2 個範圍對照](guides/README.md) |
| 查歷史 V5.6.0 功能與來源 | [歷史功能與覆核](2026-10-16-gemini-integration-review.md) |
| 核對歷史 EXE／DMG 的原生測試、提交與 SHA256 | [Windows win.8 驗收與 SHA256](2026-10-18-windows-report-audit.md#原生發布結果) · [macOS mac.6](2026-10-16-gemini-integration-review.md#原生發布狀態) |
| 從原始碼執行、建置或測試 | [開發者入口](development.md) |
| 查以前版本的修訂、驗證與搜尋實驗 | [歷史紀錄](history/README.md) |

工程結果供初估與方案比較；正式選型與現場設計仍須覆核。文件中的「計算完成」「待補資料」「未達條件」含義見[常見問題](faq.md#results)。

**DESIGNED BY ANDY HUANG ©**
