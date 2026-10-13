# Mac 自動驗收診斷修正、mac.5 發佈與驗證

mac.5 已於 2026-10-13（台灣時間）發佈。使用者明確同意後，[PR #6](https://github.com/azx4121/facility-studio/pull/6)已合併；[正式原生與發佈流程](https://github.com/azx4121/facility-studio/actions/runs/38418161842)在 Apple Silicon／Intel 全部通過，再新增公開修訂。Windows win.3 及 Mac mac.4 保留原檔。

公開 DMG：[Facility_Studio_V5_6_0_macOS_mac5.dmg](https://github.com/azx4121/facility-studio/releases/download/v5.6.0-mac.5/Facility_Studio_V5_6_0_macOS_mac5.dmg)，141,828,767 bytes；SHA256：bcd0854fa7f30b78d09ceaf0e53d285e5c75e6363800fc18a046f875eca70e9d。實際公開檔測試提交：aef83a683af66b4893d7e38d7ca910cf26831322。公開下載、GitHub asset digest、公開 SHA256SUMS.txt 與流程測試檔的位元組已獨立核對一致。

正式交付包另完成 6 次原生執行：Apple Silicon 首次、Launch Services、ZIP 解包及唯讀 DMG 共 4 次，Intel 同一 ZIP／DMG 共 2 次。每次 221 項原生驗收及 100 案／3,902 項壓測全通過，每案重算 20 次。逐案物理輸入和標準化工程輸出與先前四個 Windows／Mac 原生環境一致。下列候選、對照與失敗紀錄保留原測試時的版本與校驗碼。

原生取樣已確認加速背景診斷等待的原因；原始那次簽署 App 的 SIGSEGV 是否同一原因仍未證實。瀏覽器畫面驗收仍被工具拒絕，實際目視 0 頁。

## 發佈前的候選與診斷紀錄

候選階段核對日期：2026-10-13（台灣時間）。當時候選包完成、尚待發佈確認；發佈前 main 為 455bd02c3050e3948e657eeb178f7bf2edb21b55，公開版為 Windows win.3／Mac mac.4。

## 已定位的問題與修正

加速診斷在完成 100 次語言切換與視窗關閉後，有時無法退出。最後兩次 Apple Silicon 重現取得有效原生取樣：主執行緒在停止背景診斷時等待，背景診斷停在 Python 的 _PyFrame_SafeGetCode 堆疊讀取函式。此問題已定位到自動診斷，並非該次 Tk 主事件迴圈仍在操作圖表。

mac.5 將自動驗收的 25 秒背景診斷改成 Tk 主事件迴圈的同步診斷，關閉前取消排程。保留原有驗收判定、初次繪圖／互動時限及外部程序 300 秒時限；計算公式、工程表、專案格式和一般使用功能不變。若事件迴圈本身停住，同步回呼無法執行，外部程序時限仍負責判定。

這是對已重現背景診斷等待的修正。先前原簽署 App 的 SIGSEGV 沒有留下可定位的原生崩潰報告；這次使用外部 helper、1 秒加速診斷與事件追蹤，實際 Cocoa 程序身分不同。因此原 SIGSEGV 是否同一原因仍未證實，沒有宣稱所有間歇崩潰已消除。

## mac.5 原生候選驗收

[候選版原生流程](https://github.com/azx4121/facility-studio/actions/runs/38399687154)，實際測試提交 325397edf29996f9d131a155fe809783125bd333。

| 環境／交付路徑 | 執行次數 | 每次驗收 | 每次壓力測試 | 結果 |
| --- | ---: | --- | --- | --- |
| macOS 15.7.9 Apple Silicon：首次、Launch Services、ZIP 解包、唯讀 DMG | 4 | 221 項原生／GUI／資源檢查 | 同一 100 組物理情境、3,902 項檢查，每案重算 20 次 | 全通過 |
| macOS 15.7.9 Intel：相同 ZIP 及 DMG | 2 | 221 項原生／GUI／資源檢查 | 同一 100 組物理情境、3,902 項檢查，每案重算 20 次 | 全通過 |

這是 6 次執行相同的 100 組案例，沒有稱為 600 個不同設計，也不是 100 次 GUI 啟動。每次另有 2,400 次主案計算、200 次簡易氣體換算和 2 個預期工程拒絕。100 案物理輸入與標準化工程輸出，和已發布 win.3 的兩個 Windows 環境、mac.4 的兩個 Mac 環境逐案一致。工程狀態仍為待補資料，軟體通過與工程核定分開。

同步診斷在實際原生驗收中有執行：5 份程序主控台分別記錄 2、3、3、4、4 次同步 dump，背景 watchdog 的 Timeout 訊息為 0；另有通過的 Launch Services JSON。候選介面原生截圖已核對。原驗收呼叫與通過判定 AST 比對一致，排程生命週期測試通過。

候選 DMG：Facility_Studio_V5_6_0_macOS_mac5.dmg，141,501,603 bytes。

SHA256：0d62d01842522340f06494f01aa76809f2b78f140117ced963bc5da6c9efbbe8。

測試分支的 publish 工作已跳過，既有 mac.4 資產未覆寫。[修正 PR #6](https://github.com/azx4121/facility-studio/pull/6)已合併並保留程式與證據。

## 診斷對照與失敗紀錄

前兩輪共有 8 次原簽署 mac.4 啟動器成功對照，每次 221 項驗收與 100 案／3,902 項壓測通過。第二輪每架構的四種語言切換模式各完成 100 次驗證；ARM 加速模式在清理後逾時，其餘正常退出。第一輪外部 probe 選到已移除的執行檔而返回 125，屬診斷入口設定錯誤，沒有列為 App 崩潰。

第三輪 [38399687139](https://github.com/azx4121/facility-studio/actions/runs/38399687139)：ARM 三次分別正常退出、100 次完成後 cancel 等待逾時、正常退出；Intel 有一次只完成 99 次便到程序期限，另外兩次在完成 100 次與關閉後卡在 cancel。原生取樣返回成功，但報告路徑被 macOS 遮蔽而遭初版篩選拒留，不能把這些樣本稱作已取得 C 堆疊。

第四輪 [38414588699](https://github.com/azx4121/facility-studio/actions/runs/38414588699)，診斷提交 0e14eefbc70407120bf0d517c92b4401108ccf4d：ARM 第 1／3 次完成 100 次與關閉後卡住，第 2 次正常退出。兩份 3 秒取樣皆用 kernel executable path 前後核對、Popen 存活與 header PID 核對，確認僅收集本次 helper，才保留被遮蔽路徑的報告。9 項收集限制測試及本機真實 helper 取樣通過。

兩份樣本的主線程皆為 faulthandler_cancel_dump_traceback_later_py → cancel_dump_traceback_later → PyThread_acquire_lock_timed → _pthread_cond_wait；背景線程皆為 faulthandler_thread → _Py_DumpTracebackThreads → dump_traceback → dump_frame → _PyFrame_SafeGetCode。這是加速外部診斷等待的直接證據，沒有重現原 SIGSEGV。

第四輪 Intel 在第一個語言切換前，初始事件處理超過外部 probe 的 5 秒互動限制，返回 2，清理／cancel 皆完成；沒有原生訊號或程序卡住，不計入 100 次完成或根因重現。候選 App 的正式原生時限及驗收條件保持原值且全通過。

[機讀完整紀錄](evidence/2026-10-13-mac-diagnostics.json)、[原生樣本 1](evidence/2026-10-13-mac-watchdog-arm64-1.txt)、[原生樣本 3](evidence/2026-10-13-mac-watchdog-arm64-3.txt)。所有下載 artifact 均核對服務端與本地 SHA256。先前 SIGSEGV 與成功重跑保留在 [舊補充紀錄](evidence/2026-10-13-native-followup.json)。

## GitHub 畫面驗收

使用者已重新授權開啟 GitHub，但內建瀏覽器不可用，Chrome 電腦操作工具仍以目前網址不允許操作為由強制結束；未取得當時網址、AX 或截圖，目視頁數為 0。此為工具限制，本輪沒有改走其他方式繞過。先前完成的網頁內容、連結與錨點檢查仍有效，不能代替瀏覽器畫面驗收。

## English

Mac revision 5 has been published after explicit user approval and six additional native main-branch executions. Its public DMG SHA256 is bcd0854fa7f30b78d09ceaf0e53d285e5c75e6363800fc18a046f875eca70e9d. The public download, checksum file, GitHub asset digest and tested delivery bytes match. The following describes the earlier candidate stage. Six native executions across Apple Silicon and Intel passed the unchanged 221 acceptance checks and the same 100 physical stress recipes, with 3,902 stress checks and 20 repetitions per recipe. All normalized physical and engineering digests match the four previously published native environments. The exact candidate DMG and its SHA256 are recorded above.

Two accelerated external-probe native samples now locate the post-cleanup hang: the main thread waits in watchdog cancellation while the watchdog remains in _PyFrame_SafeGetCode. Revision 5 replaces the background acceptance watchdog with synchronous Tk-loop diagnostics cancelled before shutdown. This removes the reproduced background-diagnostic path, without proving that the earlier signed-App SIGSEGV had the same cause. External tracing, one-second acceleration and Cocoa identity differences remain explicit. The final Intel probe failed its initial interaction time budget before any switch, rather than reproducing this hang.

Publication was skipped on the earlier test branch; the approved main workflow subsequently published mac.5. Public mac.4 remains unchanged. Browser visual audit remains blocked by the tool after renewed consent, with zero pages visually inspected.
