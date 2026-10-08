"""Retire exactly two owner-requested ZIPs; retain executable identities."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.public_release_policy import parse_checksums, public_checksums

REPOSITORY = "azx4121/facility-studio"
API = "https://api.github.com/repos/" + REPOSITORY
STAGED_SUMS = "SHA256SUMS.public.txt"
TARGETS = {"v5.5.6-win.3", "v5.5.6-mac.2"}
NOTE = (
    "\n\n2026-10-08：依維護者要求，移除本版完整 ZIP；請下載上方 EXE／DMG。"
    "原始碼、範本與驗證記錄留在倉庫。現有程式未重新建置或更換簽章。\n"
    "The complete ZIP is retired. Download the EXE/DMG; source, templates and "
    "verification remain in the repository. The retained binary is unchanged."
)


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def desired_body(spec):
    body = spec["body_before"]
    for old, new in spec["replacements"]:
        if body.count(old) != 1:
            raise ValueError("Release text replacement is not unique")
        body = body.replace(old, new)
    return body + NOTE


def check_asset(asset, expected):
    for key in ("id", "name", "size", "digest"):
        if asset.get(key) != expected.get(key):
            raise ValueError("Asset lease changed: " + expected["name"] + " / " + key)


def plan_release(release, spec, checksum_data):
    """Read-only preflight; allow interrupted, explicitly recognized states."""
    if spec["tag"] not in TARGETS:
        raise ValueError("Release is outside the requested scope")
    if release.get("id") != spec["release_id"] or release.get("tag_name") != spec["tag"]:
        raise ValueError("Release identity changed")
    if release.get("draft") or release.get("immutable"):
        raise ValueError("Release is draft or immutable")
    body = desired_body(spec)
    if release.get("body") not in (spec["body_before"], body):
        raise ValueError("Release body changed since inspection")
    assets = {item["name"]: item for item in release["assets"]}
    if len(assets) != len(release["assets"]):
        raise ValueError("Duplicate release asset names")
    keep, remove = spec["keep_asset"], spec["remove_asset"]
    if not remove["name"].endswith("_OneClick.zip"):
        raise ValueError("Only the requested complete ZIP may be deleted")
    allowed = {keep["name"], remove["name"], "SHA256SUMS.txt", STAGED_SUMS}
    if set(assets) - allowed:
        raise ValueError("Unexpected assets were added; inspect before proceeding")
    check_asset(assets.get(keep["name"], {}), keep)
    if remove["name"] in assets:
        check_asset(assets[remove["name"]], remove)
    sums = assets.get("SHA256SUMS.txt") or assets.get(STAGED_SUMS)
    if not sums or len(checksum_data) > 8192:
        raise ValueError("Missing or oversized checksums")
    if sums.get("digest") != digest(checksum_data) or sums.get("size") != len(checksum_data):
        raise ValueError("Downloaded checksums do not match GitHub metadata")
    entries = parse_checksums(checksum_data.decode("utf-8"))
    expected_entries = {keep["name"]: keep["digest"].removeprefix("sha256:")}
    original_entries = {
        **expected_entries,
        remove["name"]: remove["digest"].removeprefix("sha256:"),
    }
    if entries not in (expected_entries, original_entries):
        raise ValueError("Checksum entries changed")
    public = public_checksums(checksum_data.decode("utf-8"), [keep["name"]])
    staged = assets.get(STAGED_SUMS)
    if staged and (staged.get("size") != len(public) or staged.get("digest") != digest(public)):
        raise ValueError("Staged public checksums changed")
    return {
        "spec": spec,
        "release": release,
        "assets": assets,
        "checksum_before": checksum_data.decode("utf-8"),
        "public_checksums": public.decode("utf-8"),
        "body_after": body,
    }


class GitHub:
    def __init__(self, token):
        self.headers = {
            "User-Agent": "FacilityStudio-owner-requested-download-cleanup",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = "Bearer " + token

    def request(self, route, data=None, method="GET", upload=False):
        base = "https://uploads.github.com/repos/" + REPOSITORY if upload else API
        if not route.startswith("/releases"):
            raise ValueError("Only scoped release operations are permitted")
        headers = {**self.headers}
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif isinstance(data, bytes):
            headers["Content-Type"] = "application/octet-stream"
        request = urllib.request.Request(base + route, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        return json.loads(payload) if payload else None

    def release(self, spec):
        return self.request("/releases/" + str(spec["release_id"]))

    def checksums(self, release):
        asset = next((a for a in release["assets"] if a["name"] == "SHA256SUMS.txt"), None)
        asset = asset or next((a for a in release["assets"] if a["name"] == STAGED_SUMS), None)
        if not asset or asset.get("size", 8193) > 8192:
            raise ValueError("Missing or oversized checksum asset")
        url = asset["browser_download_url"]
        prefix = "https://github.com/" + REPOSITORY + "/releases/download/"
        if not url.startswith(prefix):
            raise ValueError("Unexpected public checksum download host")
        # Public download has no Authorization header to forward on redirects.
        separator = "&" if "?" in url else "?"
        url += separator + urllib.parse.urlencode({"asset_id": asset["id"]})
        request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read(8193)

    def delete_asset(self, asset):
        self.request("/releases/assets/" + str(asset["id"]), method="DELETE")

    def apply(self, plan):
        spec, assets = plan["spec"], plan["assets"]
        public = plan["public_checksums"].encode("utf-8")
        canonical = assets.get("SHA256SUMS.txt")
        staged = assets.get(STAGED_SUMS)
        if not canonical or canonical["digest"] != digest(public):
            if not staged:
                route = "/releases/" + str(spec["release_id"]) + "/assets?"
                route += urllib.parse.urlencode({"name": STAGED_SUMS})
                staged = self.request(route, data=public, method="POST", upload=True)
            if staged.get("digest") != digest(public) or staged.get("size") != len(public):
                raise ValueError("Uploaded checksum verification failed; old sums retained")
            if canonical:
                self.delete_asset(canonical)
            self.request(
                "/releases/assets/" + str(staged["id"]),
                {"name": "SHA256SUMS.txt"}, "PATCH",
            )
        elif staged:
            self.delete_asset(staged)
        removed = assets.get(spec["remove_asset"]["name"])
        if removed:
            self.delete_asset(removed)
        if plan["release"]["body"] != plan["body_after"]:
            self.request(
                "/releases/" + str(spec["release_id"]),
                {"body": plan["body_after"]}, "PATCH",
            )
        print("Public downloads simplified: " + spec["tag"], flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if args.apply and (
        os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_ACTIONS") != "true"
    ):
        raise RuntimeError("Mutations are restricted to this repository's main-branch Actions job")
    manifest = json.loads(Path(__file__).with_name("public-downloads-20261008.json").read_text())
    if manifest.get("repository") != REPOSITORY or manifest.get("schema") != 1:
        raise ValueError("Unexpected cleanup manifest")
    if {s["tag"] for s in manifest["releases"]} != TARGETS or len(manifest["releases"]) != 2:
        raise ValueError("Exactly the two requested releases are required")
    token = os.environ.get("FACILITY_GITHUB_TOKEN", "")
    if args.apply and not token:
        raise RuntimeError("An authorized release-maintenance token is required")
    client = GitHub(token)
    plans = []
    for spec in manifest["releases"]:
        release = client.release(spec)
        plans.append(plan_release(release, spec, client.checksums(release)))
    report = {"schema": 1, "applied": False, "before": plans, "after": []}
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.apply:
        print("Read-only preflight passed for both requested releases")
        return
    # Every release is preflighted before the first mutation.
    for plan in plans:
        fresh = client.release(plan["spec"])
        fresh_plan = plan_release(fresh, plan["spec"], client.checksums(fresh))
        client.apply(fresh_plan)
        final = client.release(plan["spec"])
        final_plan = plan_release(final, plan["spec"], client.checksums(final))
        expected_names = {plan["spec"]["keep_asset"]["name"], "SHA256SUMS.txt"}
        if set(final_plan["assets"]) != expected_names or final["body"] != plan["body_after"]:
            raise ValueError("Release post-mutation verification failed")
        if final_plan["checksum_before"] != plan["public_checksums"]:
            raise ValueError("Published checksum content differs")
        report["after"].append(final)
        args.evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["applied"] = True
    args.evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Verified: original EXE/DMG identities retained; only requested ZIPs removed")


if __name__ == "__main__":
    main()
