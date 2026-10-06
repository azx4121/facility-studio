"""Publish a new, tested Mac revision; never replace previous release assets."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "azx4121/facility-studio"
TAG = "v5.5.4-mac.2"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ["FACILITY_GITHUB_TOKEN"]
    commit = os.environ["FACILITY_RELEASE_COMMIT"]
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Only a tested main-branch workflow may publish this release.")
    folder = args.assets.resolve()
    filenames = ("Facility_Studio_V5_5_4_macOS_mac2_OneClick.zip",
                 "Facility_Studio_V5_5_4_macOS_mac2.dmg", "SHA256SUMS.txt")
    for filename in filenames:
        if not (folder / filename).is_file():
            raise ValueError("Missing verified asset: " + filename)
    digests = {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
               for name in filenames}
    expected = {line.split()[1]: line.split()[0]
                for line in (folder / "SHA256SUMS.txt").read_text().splitlines()}
    if any(expected.get(name) != digests[name] for name in filenames[:2]):
        raise ValueError("Release files changed after native acceptance.")
    headers = {"Authorization": "Bearer " + token,
               "User-Agent": "FacilityStudio-native-release",
               "Accept": "application/vnd.github+json"}
    existing = urllib.request.Request(
        "https://api.github.com/repos/" + REPOSITORY + "/releases/tags/" + TAG,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(existing, timeout=30) as response:
            release = json.load(response)
        print("Existing release retained: " + release["html_url"])
        return
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    body = (
        "macOS 專用修訂 mac.2，保留 V5.5.4 功能與 FY 圖示。\n\n"
        "修正 Tcl/Tk 資源封印不符合 Apple 原生檢查，以及第一次字型快取建立時的無時限外部查詢。"
        "使用 Apple codesign 重新封裝；同一份 Universal App 與 ZIP 已在 Apple Silicon、Intel macOS 15 原生環境驗證。\n\n"
        "建議下載 DMG，打開後把 Facility Studio 拖到 Applications。ZIP 則包含完整原始碼、設備範本與驗證記錄。"
        "不需另裝 Python。首次若提示開發者無法驗證，請依 Apple 官方「隱私權與安全性 → 仍要打開」流程。\n\n"
        "本版仍是 ad-hoc 簽章，沒有 Developer ID／Apple 公證；使用者 macOS 27 Beta 與企業管理政策仍須另行確認。"
        "新修訂採公司內部工程使用附加許可；完整條款隨包提供。原 MIT 版本權利、v5.5.4-beta.1 與 Windows 舊包保持原樣。"
    )
    data = json.dumps(dict(tag_name=TAG,target_commitish=commit,name="Facility Studio V5.5.4｜macOS 修正版 mac.2",
                           body=body,draft=True,prerelease=True)).encode()
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + "/releases",
                                     headers={**headers,"Content-Type":"application/json"},data=data,method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    upload = release["upload_url"].split("{",1)[0]
    if urllib.parse.urlparse(upload).hostname != "uploads.github.com":
        raise ValueError("Unexpected GitHub upload host.")
    for filename in filenames:
        path = folder / filename
        url = upload + "?" + urllib.parse.urlencode({"name":filename})
        request = urllib.request.Request(url,headers={**headers,"Content-Type":"application/octet-stream"},
                                         data=path.read_bytes(),method="POST")
        with urllib.request.urlopen(request,timeout=180) as response:
            asset=json.load(response)
        if asset["size"] != path.stat().st_size:
            raise ValueError("Uploaded asset size mismatch: " + filename)
        if asset.get("digest") != "sha256:" + digests[filename]:
            raise ValueError("GitHub uploaded asset SHA-256 mismatch: " + filename)
    request = urllib.request.Request(release["url"],headers={**headers,"Content-Type":"application/json"},
                                     data=b'{"draft":false}',method="PATCH")
    with urllib.request.urlopen(request,timeout=30) as response:
        published=json.load(response)
    print("Published verified revision: " + published["html_url"])


if __name__ == "__main__":
    main()
