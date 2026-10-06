#!/bin/bash
# Optional per-user installation. No admin password or network downloads.
set -euo pipefail

TASK_PACKAGE_DIR="$(cd "$(/usr/bin/dirname "$0")" && pwd -P)"
TASK_APP_SOURCE="$TASK_PACKAGE_DIR/Facility Studio.app"
TASK_APP_FOLDER="$HOME/Applications"
TASK_DESTINATION="$TASK_APP_FOLDER/Facility Studio V5.5.4.app"
TASK_STAGE=""

cleanup() {
    if [[ -n "$TASK_STAGE" && -d "$TASK_STAGE" ]]; then
        /bin/rm -rf "$TASK_STAGE"
    fi
}
trap cleanup EXIT

printf '\nFacility Studio V5.5.4 — macOS 安裝\n\n'
if [[ ! -d "$TASK_APP_SOURCE" ]]; then
    printf '請先完整解壓縮懶人包，讓此檔案與 Facility Studio.app 放在同一個資料夾。\n'
    exit 2
fi
printf '檢查 App 的完整性…\n'
if ! /usr/bin/codesign --verify --deep --strict "$TASK_APP_SOURCE"; then
    printf 'App 未通過 macOS 原生完整性檢查。請勿繼續安裝；請執行 Verify_on_Mac.command 並回傳顯示的結果。\n'
    exit 2
fi
/bin/mkdir -p "$TASK_APP_FOLDER"
if [[ -L "$TASK_DESTINATION" ]]; then
    printf '安裝位置是連結，已停止安裝。可直接開啟懶人包內的 App。\n'
    exit 2
fi
if [[ -e "$TASK_DESTINATION" ]]; then
    TASK_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$TASK_DESTINATION/Contents/Info.plist" 2>/dev/null || true)"
    if [[ "$TASK_ID" != 'com.facilitystudio.desktop' ]]; then
        printf '相同名稱的位置已有其他檔案，已保留原檔。可直接開啟懶人包內的 App。\n'
        exit 2
    fi
fi
TASK_STAGE="$(/usr/bin/mktemp -d "$TASK_APP_FOLDER/.FacilityStudio554.XXXXXX")"
/usr/bin/ditto "$TASK_APP_SOURCE" "$TASK_STAGE/Facility Studio.app"
/usr/bin/codesign --verify --deep --strict "$TASK_STAGE/Facility Studio.app"
if [[ -e "$TASK_DESTINATION" ]]; then
    TASK_BACKUP="$TASK_APP_FOLDER/Facility Studio V5.5.4 Backup $(/bin/date +%Y%m%d-%H%M%S).app"
    if [[ -e "$TASK_BACKUP" ]]; then
        printf '備份檔名已存在，已停止以保留原安裝。\n'
        exit 2
    fi
    /bin/mv "$TASK_DESTINATION" "$TASK_BACKUP"
    printf '原 App 已保留為：%s\n' "$TASK_BACKUP"
fi
/bin/mv "$TASK_STAGE/Facility Studio.app" "$TASK_DESTINATION"
printf '\n已安裝至：%s\n' "$TASK_DESTINATION"
printf '第一次若被系統攔下，請在「系統設定 → 隱私權與安全性 → 仍要打開」允許此 App。\n'
/usr/bin/open "$TASK_DESTINATION"
printf '\n日常使用可從使用者「應用程式」資料夾開啟，也可以把 FY 圖示固定在 Dock。\n'
