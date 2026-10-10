"""Publish only verified win.1 assets; preserve every existing published release."""

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
TAG = "v5.5.8-win.1"
FILENAMES = (
    "Facility_Studio_V5_5_8_Windows_Offline.exe",
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
    asset_data = prepare_public_assets(folder, FILENAMES[:-1])
    digests = {
        name: hashlib.sha256(data).hexdigest() for name, data in asset_data.items()
    }
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
        # Visitor-facing notes are maintained with the documentation.
        body = (
            Path(__file__).resolve().parents[2] / "docs/releases" / (TAG + ".md")
        ).read_text(encoding="utf-8")
        payload = {
            "tag_name": TAG,
            "target_commitish": commit,
            "name": "Facility Studio V5.5.8｜Windows 離線直接執行版 win.1",
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
        data = asset_data[name]
        asset = uploaded.get(name)
        if asset is None:
            asset = request(
                upload + "?" + urllib.parse.urlencode({"name": name}),
                data,
                "POST",
                "application/octet-stream",
                180,
            )
        if (
            asset["size"] != len(data)
            or asset.get("digest") != "sha256:" + digests[name]
        ):
            raise ValueError("Uploaded file SHA256 or size mismatch: " + name)
    release = request(release["url"], b'{"draft":false}', "PATCH")
    print("Published native-tested offline revision: " + release["html_url"])


if __name__ == "__main__":
    main()
