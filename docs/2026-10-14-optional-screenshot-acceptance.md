# Facility Studio 2026-10-14 接續驗證

已找到並修正另一個會阻擋本機驗收的問題：無法取得螢幕畫面時，截圖指令的 CalledProcessError 中斷了其後驗收。這是正常退出 2，沒有重現原始 SIGSEGV。

目前公開下載仍為 Windows win.3／Mac mac.5；本次修正位於[草稿 PR #7](https://github.com/azx4121/facility-studio/pull/7)，尚未合併或公開發布。

## 使用者 Mac 實測

本機系統為 macOS 27.2（26B5101f）、Apple Silicon arm64。原公開 DMG 的 SHA256 與原生深度簽署核對通過；啟動後在第 74 個已開始檢查附近、收集英文介面截圖時停止，34.291 秒正常退出 2。該次沒有完成全套驗收，不能當作通過。

候選從同一公開 DMG 複製，僅修改語言／使用性驗收兩份程式並重新 ad-hoc 簽署；沒有修改公式、正式操作功能、已發布檔案或系統權限。明確停用可選截圖後，76.298 秒正常退出 0，221 項原生驗收與 100 組 ×20 重算、3,902 項檢查全通過。

同一百案的物理輸入與標準化工程輸出，與先前兩個 Windows、兩個 mac.4 及正式 mac.5 Apple Silicon 原生環境逐案一致；221 項檢查名稱也和正式 mac.5 驗收一致。這是修改候選的通過，沒有把它稱為未修改公開 DMG 的本機全套通過。

另在同一 Apple Silicon Mac 的 Rosetta x86_64 相容模式測試候選，101.130 秒正常退出0，221 項及100案×20／3,902項全通過；一百案輸入／工程輸出和先前兩個Windows、兩個mac.4及兩個mac.5原生環境一致。這是相容模式測試，不能替代實體 Intel Mac 雲端驗證。

沒有取得任何螢幕截圖；使用者原有軟體日誌／快取已還原，唯讀映像已卸載。一般從瀏覽器下載後的隔離標记與 Gatekeeper 首次啟動路徑尚未另驗。

## 修正與回歸

兩平台的可選截圖取得／存檔現在處理 OSError、RuntimeError 及 CalledProcessError，並記錄明確警告。驗收可設定 FACILITY_STUDIO_ACCEPTANCE_SCREENSHOTS=0，停止呼叫 ImageGrab；預設仍保留截圖取得。驗收 check／require／assert、Windows repaint 驗證、次數與時限皆保留。

6 項模擬回歸通過：拒絕截圖、明確停用、正常預設、非預期 AssertionError 傳出、拒絕後恢復語言、停用後仍執行 Windows repaint 驗證。測試沒有實際取得螢幕畫面。

Windows 2022／2025 兩環境均已完成，每環境分別執行 standalone、Unicode路徑、ZIP交付，共6次；每次233項、100案×20／3,902項全通過，frozen打包、外部Python隱藏與對外網路封鎖均驗證，逐案輸入／工程輸出與先前公開版一致。兩份證據ZIP的大小、GitHub artifact SHA256均已核對。Mac 雲端兩次均排隊15分鐘後取消，沒有執行任何步驟；整體工作流顯示 failure，Intel 驗證 skipped，原因没有可取得日誌確認。這不是新 App 測試失敗，也沒有取得新候選的實體 Mac ARM／Intel 雲端交付驗證，不再重複送出同一工作：[Mac ARM／Intel](https://github.com/azx4121/facility-studio/actions/runs/38429660726) · [Windows 2022／2025](https://github.com/azx4121/facility-studio/actions/runs/38429660604)。發布步驟僅限 main，修正分支不會發布或覆蓋現行下載。

## 仍未完成

本次候選仍缺實體 Mac ARM／Intel 的雲端交付驗證，並仍為草稿 PR #7。後續公開修正版需建立新的獨立修訂與核對交付，不能將此候選覆蓋現行下載。

GitHub 的實際網頁畫面驗收仍待使用者解除已儲存 github.com 瀏覽器封鎖；GitHub 連接器已正常可讀取與更新，兩項權限不同。沒有用其他途徑繞過瀏覽器封鎖。

原始 mac.4 單次 SIGSEGV 沒有完整原生崩潰報告，尚不能定因；本次截圖失敗也不能當作原始 SIGSEGV 原因。已發布 mac.5 的背景診斷等待修正與先前測試證據保留。
