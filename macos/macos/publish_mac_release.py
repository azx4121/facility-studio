"""Publish a new, tested Mac revision; never replace previous release assets."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.public_release_policy import prepare_public_assets

REPOSITORY = "azx4121/facility-studio"
TAG = "v5.5.8-mac.1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ["FACILITY_GITHUB_TOKEN"]
    commit = os.environ["FACILITY_RELEASE_COMMIT"]
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError(
            "Only a tested main-branch workflow may publish this release."
        )
    folder = args.assets.resolve()
    filenames = (
        "Facility_Studio_V5_5_8_macOS_mac1.dmg",
        "SHA256SUMS.txt",
    )
    asset_data = prepare_public_assets(folder, filenames[:-1])
    digests = {
        name: hashlib.sha256(data).hexdigest()
        for name, data in asset_data.items()
    }
    headers = {
        "Authorization": "Bearer " + token,
        "User-Agent": "FacilityStudio-native-release",
        "Accept": "application/vnd.github+json",
    }
    existing = urllib.request.Request(
        "https://api.github.com/repos/" + REPOSITORY + "/releases/tags/" + TAG,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(existing, timeout=30) as response:
            release = json.load(response)
        if not release["draft"]:
            print("Existing published release retained: " + release["html_url"])
            return
        if release["target_commitish"] != commit:
            raise ValueError(
                "A draft from another commit exists; it has been retained."
            )
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = None
    body = (
        'V5.5.8 修正獨立空調箱無效草稿的保存、重新開啟與關閉前保存；確認後保留原始輸入，計算與報告匯出仍受驗證限制。取消不覆存，修正後回復普通專案並保留備份。旁通因子對不一致內部狀態增加明確錯誤，不採任意 beta=0。\n\nV5.5.8 fixes standalone AHU invalid-draft save/reopen while retaining calculation and export validation. Source regressions cover draft structure, backups and cancellation, with ten additional real native Tk workflow checks.\n\n'
        'V5.5.8 修正停用欄位洩漏：最大馬達與負載類型同步互鎖，停用效率不阻擋計算，單機報告只列啟用熱水／水洗設備，選用名目電力統一。新增 970 項完整輸出、報告、獨立公式與壓損檢核；安裝檔內另含原生控制項驗收。\n\n'
        'V5.5.8 fixes inactive-input leakage, largest-motor activation, disabled heater efficiency, selected-power totals and AHU report scope. 970 reproducible checks compare complete outputs and reports, with independent current/pressure balances and native GUI interlocks.\n\n'
        'V5.5.8 修正新手操作與需求範圍：基本模式依任務收合分頁，共同氣候放在圖前，另存／複製方案不覆蓋原案。設備表支援百分比格式辨識及選取群組預覽帶入；多台空調箱依來源彙整，同台更新不重算一次，水路依季節與供回水／流體分開，各迴路物性獨立。改輸入後保留已標示過期的圖表作對照，匯出及回傳停用至重新檢核。離線繁中／英文教學同步 18 個章節，前六步進度為手動閱讀記錄。\n\nV5.5.8 clarifies beginner navigation, project saving and source ownership. Equipment imports normalize explicit Excel percentages and offer scoped preview transfers. Repeated AHU IDs replace their contribution; separate included units add, with seasonal and incompatible water circuits kept distinct. Stale plots/reports remain marked for comparison while export and transfer are disabled. Bilingual offline help covers 18 chapters and six required reading steps.\n\n'
        "V5.5.8 中英雙語版 mac.1，保留全部工程功能、macOS 啟動修復與 FY 圖示。\n\n"
        "主畫面右上角選擇 English／繁體中文，欄位、提示、圖表、報告及設備範本同步切換；已填數字與舊專案保留。語言偏好會保存。\n\n"
        "Bilingual interface: select English in the top-right language selector. Forms, guidance, charts, reports and exported equipment templates are translated. Stored engineering data remains unchanged.\n\n"
        "修正 Tcl/Tk 資源封印不符合 Apple 原生檢查，以及第一次字型快取建立時的無時限外部查詢。"
        "使用 Apple codesign 重新封裝；同一份 Universal App 與 ZIP 已在 Apple Silicon、Intel macOS 15 原生環境驗證。\n\n"
        "下載 DMG，打開後把 Facility Studio 拖到 Applications。原始碼、設備範本與驗證記錄請至本倉庫查閱。"
        "不需另裝 Python。首次若提示開發者無法驗證，請依 Apple 官方「隱私權與安全性 → 仍要打開」流程。\n\n"
        "本版仍是 ad-hoc 簽章，沒有 Developer ID／Apple 公證；使用者 macOS 27 Beta 與企業管理政策仍須另行確認。"
        "新修訂採公司內部工程使用附加許可；完整條款隨包提供。原 MIT 版本權利、v5.5.4-beta.1 與 Windows 舊包保持原樣。"
    )
    if release is None:
        data = json.dumps(
            dict(
                tag_name=TAG,
                target_commitish=commit,
                name="Facility Studio V5.5.8｜macOS 中英雙語離線版 mac.1",
                body=body,
                draft=True,
                prerelease=True,
            )
        ).encode()
        request = urllib.request.Request(
            "https://api.github.com/repos/" + REPOSITORY + "/releases",
            headers={**headers, "Content-Type": "application/json"},
            data=data,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
    upload = release["upload_url"].split("{", 1)[0]
    if urllib.parse.urlparse(upload).hostname != "uploads.github.com":
        raise ValueError("Unexpected GitHub upload host.")
    uploaded = {asset["name"]: asset for asset in release.get("assets", [])}
    for filename in filenames:
        data = asset_data[filename]
        asset = uploaded.get(filename)
        if asset is None:
            url = upload + "?" + urllib.parse.urlencode({"name": filename})
            request = urllib.request.Request(
                url,
                headers={**headers, "Content-Type": "application/octet-stream"},
                data=data,
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                asset = json.load(response)
        if asset["size"] != len(data):
            raise ValueError("Uploaded asset size mismatch: " + filename)
        if asset.get("digest") != "sha256:" + digests[filename]:
            raise ValueError("GitHub uploaded asset SHA-256 mismatch: " + filename)
    request = urllib.request.Request(
        release["url"],
        headers={**headers, "Content-Type": "application/json"},
        data=b'{"draft":false}',
        method="PATCH",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        published = json.load(response)
    print("Published verified revision: " + published["html_url"])


if __name__ == "__main__":
    main()
