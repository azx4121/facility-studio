#!/bin/bash
# Optional real-Mac acceptance. The installed app has no external dependencies.
set -uo pipefail
TASK_PACKAGE_DIR="$(cd "$(/usr/bin/dirname "$0")" && pwd -P)"
TASK_APP="$TASK_PACKAGE_DIR/Facility Studio.app"
TASK_LOG_FOLDER="$HOME/Library/Logs/Facility_Studio_V5_5"
/bin/mkdir -p -- "$TASK_LOG_FOLDER"
finish() {
    TASK_STATUS=$?
    trap - EXIT
    printf '\n驗證記錄位置：%s\n' "$TASK_LOG_FOLDER"
    if [[ "$TASK_STATUS" -ne 0 && -t 0 ]]; then
        read -r -p '驗證未通過；請保留以上訊息。按 Enter 結束。' TASK_REPLY || true
    fi
    exit "$TASK_STATUS"
}
trap finish EXIT
printf '\nFacility Studio V5.5.6 — Mac 實機驗證\n\n'
if [[ ! -d "$TASK_APP" ]]; then
    printf '找不到 Facility Studio.app；請先完整解壓縮懶人包。\n'
    exit 2
fi
if ! /usr/bin/codesign --verify --deep --strict --verbose=2 "$TASK_APP" >"$TASK_LOG_FOLDER/Mac_Signature_Check.txt" 2>&1; then
    /bin/cat "$TASK_LOG_FOLDER/Mac_Signature_Check.txt"
    printf '\nApp 未通過 Apple 原生簽章檢查；請將以上訊息提供給製作者。\n'
    exit 2
fi
/bin/cat "$TASK_LOG_FOLDER/Mac_Signature_Check.txt"
"$TASK_APP/Contents/MacOS/FacilityStudio" --self-test >"$TASK_LOG_FOLDER/Mac_SelfTest_Console.txt" 2>&1
TASK_STATUS=$?
/bin/cat "$TASK_LOG_FOLDER/Mac_SelfTest_Console.txt"
printf '\n結果儲存於：%s\n' "$TASK_LOG_FOLDER"
if [[ "$TASK_STATUS" -ne 0 ]]; then
    printf '此 Mac 的驗證未通過，請提供 Mac_Acceptance.json 或 Mac_SelfTest_Console.txt。\n'
else
    printf '此 Mac 的原生執行、數值、匯入與介面驗證通過。\n'
fi
exit "$TASK_STATUS"
