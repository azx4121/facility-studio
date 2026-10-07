"""Publish only verified win.2 assets; preserve every existing published release."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "azx4121/facility-studio"
TAG = "v5.5.5-win.2"
FILENAMES = (
    "Facility_Studio_V5_5_5_Windows_Offline.exe",
    "Facility_Studio_V5_5_5_Windows_Offline_OneClick.zip",
    "SHA256SUMS.txt",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Only the tested main-branch workflow may publish")
    commit = os.environ["FACILITY_RELEASE_COMMIT"]
    headers = {
        "Authorization": "Bearer " + os.environ["FACILITY_GITHUB_TOKEN"],
        "User-Agent": "FacilityStudio-Windows-offline-release",
        "Accept": "application/vnd.github+json",
    }

    def request(
        url, data=None, method="GET", content_type="application/json", timeout=30
    ):
        call = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={**headers, "Content-Type": content_type},
        )
        with urllib.request.urlopen(call, timeout=timeout) as response:
            return json.load(response)

    folder = args.assets.resolve()
    digests = {}
    for name in FILENAMES:
        path = folder / name
        if not path.is_file():
            raise ValueError("Missing native-tested distribution file: " + name)
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = {
        line.split()[1]: line.split()[0]
        for line in (folder / "SHA256SUMS.txt").read_text().splitlines()
    }
    if any(expected.get(name) != digests[name] for name in FILENAMES[:2]):
        raise ValueError("Distribution changed after native testing")
    base = "https://api.github.com/repos/" + REPOSITORY + "/releases"
    try:
        release = request(base + "/tags/" + TAG)
        if not release["draft"]:
            print("Existing published release retained: " + release["html_url"])
            return
        if release["target_commitish"] != commit:
            raise ValueError("Existing draft from another commit retained")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = None
    if release is None:
        body = (
            "本修訂補上簡易工具左下角 DESIGNED BY ANDY HUANG ©，七種工具共用並持續顯示。\n\n"
            "新增離線中英新手教學入口：簡易工具、完整工作台及單台空調箱可直接開啟逐步教學；另含兩份可開啟的合成練習專案與對照報告。\n\n"
            "Revision 2 adds persistent author credit to simple tools and bundled offline beginner tutorials, practice projects and reference reports. Native acceptance checks the credit at minimum window size, local tutorial buttons and actual practice loading. Existing engineering formulas and projects are retained.\n\n"
            "V5.5.5 中英雙語版：主畫面右上角選擇 English／繁體中文，欄位、提示、圖表、報告及設備範本同步切換。已填數值與舊專案保留，語言偏好會保存。\n\n"
            "Bilingual interface: select English in the top-right language selector. Forms, guidance, charts, reports and exported equipment templates are translated. Stored engineering data remains unchanged.\n\n"
            "Windows 離線直接執行版 win.2；已含 Python、Tk、Matplotlib、NumPy 與 Pillow。\n\n"
            "下載 EXE 可直接開啟，或完整解壓縮 ZIP 後雙擊 EXE；不需安裝 Python、pip，也不需連網。"
            "保留 FY 圖示、七種簡易工具、設備表匯入與完整工程工作台。ZIP 另含設備範本、原始碼、授權及本機診斷腳本。\n\n"
            "同一份交付 EXE 和 ZIP 已在 Windows Server 2022／2025 x64 原生雲端環境驗證："
            "外部 Python 從 PATH 移除、EXE 對外連線由防火牆封鎖，仍通過原生 Tk 與工程計算驗收。"
            "Windows 10／11 為支援目標，使用者實機、實體數字鍵盤、企業政策仍須個別確認。\n\n"
            "本版尚無商用程式碼簽章，可能出現 Windows 安全性提示；請核對官方來源與 SHA256，勿關閉防毒。"
            "包含目前安全與授權修正；公司內部正常工程使用許可詳 LICENSE_GUIDE.md。"
            "既有 Release、標籤、提交紀錄及歷史 MIT 權利完整保留。"
        )
        payload = {
            "tag_name": TAG,
            "target_commitish": commit,
            "name": "Facility Studio V5.5.5｜Windows 離線直接執行版 win.2",
            "body": body,
            "draft": True,
            "prerelease": True,
        }
        release = request(base, json.dumps(payload).encode(), "POST")
    upload = release["upload_url"].split("{", 1)[0]
    if urllib.parse.urlparse(upload).hostname != "uploads.github.com":
        raise ValueError("Unexpected GitHub upload host")
    uploaded = {asset["name"]: asset for asset in release.get("assets", [])}
    for name in FILENAMES:
        path = folder / name
        asset = uploaded.get(name)
        if asset is None:
            asset = request(
                upload + "?" + urllib.parse.urlencode({"name": name}),
                path.read_bytes(),
                "POST",
                "application/octet-stream",
                180,
            )
        if (
            asset["size"] != path.stat().st_size
            or asset.get("digest") != "sha256:" + digests[name]
        ):
            raise ValueError("Uploaded file SHA256 or size mismatch: " + name)
    release = request(release["url"], b'{"draft":false}', "PATCH")
    print("Published native-tested offline revision: " + release["html_url"])


if __name__ == "__main__":
    main()
