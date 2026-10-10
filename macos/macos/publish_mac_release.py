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
    # Visitor-facing notes are maintained with the documentation.
    body = (
        Path(__file__).resolve().parents[2] / "docs/releases" / (TAG + ".md")
    ).read_text(encoding="utf-8")
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
