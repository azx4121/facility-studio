# macOS 執行環境修訂｜mac.2

原 mac.1 在 Apple Silicon 與 Intel macOS 15.7.9 原生測試中都未通過
Apple `codesign --verify --deep --strict`。Tcl/Tk 的設定腳本沒有被跨平台
簽署工具正確納入資源封印；檔案雜湊正確，仍不足以表示 Apple 會接受封裝。

mac.2 保留已核對 SHA-256 的原 CPython framework、雙架構啟動器與第三方
wheel，更新本專案程式後，改由 Apple codesign 逐一簽署 Mach-O、內層
framework、外層 framework 與最後的 App。這是 ad-hoc 簽章，沒有冒充
Developer ID，也不表示已公證。

Matplotlib 原生啟動診斷停在第一次字型快取建立。其 font_manager.py 呼叫
system_profiler 與 fc-list 時沒有時限。本修訂對三個外部查詢加上 5 秒時限，
逾時採用原本的目錄字型搜尋，不取消中文字型支援。修改只在封裝副本發生，
原 wheel 雜湊、原始與修改後檔案雜湊記錄於建置資料；安裝後的 RECORD
同步修正。Matplotlib 的原授權、版權文件均保留，這是本專案的本機修訂，
不宣稱為 Matplotlib 官方修正。

GitHub 原生 Mac 測試與使用者電腦是不同環境。macOS 27 Beta、公司管理
政策與瀏覽器下載後的隔離標記，仍須在該電腦確認。首次開啟可能需要按
Apple 官方的「系統設定 → 隱私權與安全性 → 仍要打開」流程。

本修訂不關閉 Gatekeeper，不移除隔離標記，不改動使用者全域安全設定。
