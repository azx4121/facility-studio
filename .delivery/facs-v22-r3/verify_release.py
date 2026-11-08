import hashlib
import json
import os
from pathlib import Path
import subprocess

expected = "26dcbac483b5c039486af1d88b750ba7dda5f11dbb9965e88fabc08d0236643a"
release = json.loads(Path("release.json").read_text())
assets = release["assets"]
assert release["tag_name"] == "facs-v22-r3-macos-arm64-unvalidated" and release["prerelease"] is True
assert len(assets) == 1, "Exactly one complete ZIP must be attached"
asset = assets[0]
assert asset["name"] == "FACS-v22-r3-UNVALIDATED-COMPILE-ONLY-macOS-arm64.zip" and asset["size"] == 78519839
assert asset["state"] == "uploaded" and asset["digest"] == "sha256:" + expected
if os.environ.get("VERIFY_PUBLIC") == "1":
    assert release["draft"] is False
    url = asset["browser_download_url"]
    assert url == "https://github.com/azx4121/facility-studio/releases/download/facs-v22-r3-macos-arm64-unvalidated/FACS-v22-r3-UNVALIDATED-COMPILE-ONLY-macOS-arm64.zip"
    subprocess.run(["curl", "--fail", "--location", "--retry", "3", "--retry-delay", "2", "--output", "public-redownload.zip", url], check=True)
    data = Path("public-redownload.zip").read_bytes()
    assert len(data) == 78519839 and hashlib.sha256(data).hexdigest() == expected
    print("PUBLIC_DOWNLOAD_VERIFIED", url, len(data), expected)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write("Verified unauthenticated public download of the complete ZIP.\n\n")
        summary.write(f"- URL: {url}\n- Size: {len(data)} bytes\n- SHA256: {expected}\n")
        summary.write("- This checks distribution integrity only, not native/GUI/engineering acceptance.\n")
else:
    assert release["draft"] is True
    print("DRAFT_SINGLE_ASSET_VERIFIED", asset["size"], expected)
