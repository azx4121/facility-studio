"""Deletion scope, partial recovery, checksum and publisher safety checks."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.public_release_policy import parse_checksums, prepare_public_assets, public_checksums
from tools.update_public_downloads import GitHub, STAGED_SUMS, desired_body, digest, plan_release

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tools/public-downloads-20261008.json").read_text())


def fixture(index=0):
    spec = copy.deepcopy(MANIFEST["releases"][index])
    sums = (
        f"{spec['keep_asset']['digest'][7:]}  {spec['keep_asset']['name']}\n"
        f"{spec['remove_asset']['digest'][7:]}  {spec['remove_asset']['name']}\n"
    ).encode()
    checksum_asset = {"id": 999, "name": "SHA256SUMS.txt", "size": len(sums), "digest": digest(sums)}
    release = {
        "id": spec["release_id"], "tag_name": spec["tag"], "draft": False,
        "immutable": False, "body": spec["body_before"],
        "assets": [copy.deepcopy(spec["keep_asset"]), copy.deepcopy(spec["remove_asset"]), checksum_asset],
    }
    return spec, release, sums


class FakeGitHub(GitHub):
    def __init__(self, release):
        self.current = copy.deepcopy(release)
        self.calls = []
        self.bad_upload = False

    def request(self, route, data=None, method="GET", upload=False):
        self.calls.append((route, method))
        if upload:
            asset = {"id": 1000, "name": STAGED_SUMS, "size": len(data), "digest": digest(data)}
            if self.bad_upload:
                asset["digest"] = "sha256:" + "0" * 64
            self.current["assets"].append(asset)
            return asset
        if "/assets/" in route:
            asset_id = int(route.rsplit("/", 1)[1])
            asset = next(a for a in self.current["assets"] if a["id"] == asset_id)
            if method == "DELETE":
                self.current["assets"].remove(asset)
                return None
            asset.update(data)
            return asset
        if method == "PATCH":
            self.current.update(data)
        return copy.deepcopy(self.current)


class LeaseChecks(unittest.TestCase):
    def test_both_release_preflights(self):
        for index in range(2):
            spec, release, sums = fixture(index)
            plan = plan_release(release, spec, sums)
            self.assertEqual(set(parse_checksums(plan["public_checksums"])), {spec["keep_asset"]["name"]})

    def assert_rejected(self, mutate):
        spec, release, sums = fixture()
        mutate(spec, release)
        with self.assertRaises(ValueError):
            plan_release(release, spec, sums)

    def test_changed_keep_id(self):
        self.assert_rejected(lambda s, r: r["assets"][0].update(id=123))

    def test_changed_keep_hash(self):
        self.assert_rejected(lambda s, r: r["assets"][0].update(digest="sha256:" + "0" * 64))

    def test_changed_keep_size(self):
        self.assert_rejected(lambda s, r: r["assets"][0].update(size=1))

    def test_changed_zip_id(self):
        self.assert_rejected(lambda s, r: r["assets"][1].update(id=123))

    def test_changed_zip_hash(self):
        self.assert_rejected(lambda s, r: r["assets"][1].update(digest="sha256:" + "0" * 64))

    def test_changed_zip_size(self):
        self.assert_rejected(lambda s, r: r["assets"][1].update(size=1))

    def test_wrong_release_id(self):
        self.assert_rejected(lambda s, r: r.update(id=1))

    def test_wrong_tag(self):
        self.assert_rejected(lambda s, r: r.update(tag_name="another-release"))

    def test_outside_requested_scope(self):
        self.assert_rejected(lambda s, r: s.update(tag="v5.5.5-win.2"))

    def test_changed_body(self):
        self.assert_rejected(lambda s, r: r.update(body="Edited by the owner"))

    def test_draft_release(self):
        self.assert_rejected(lambda s, r: r.update(draft=True))

    def test_immutable_release(self):
        self.assert_rejected(lambda s, r: r.update(immutable=True))

    def test_missing_executable(self):
        self.assert_rejected(lambda s, r: r["assets"].pop(0))

    def test_duplicate_asset_name(self):
        self.assert_rejected(lambda s, r: r["assets"].append(copy.deepcopy(r["assets"][0])))

    def test_unexpected_asset(self):
        self.assert_rejected(lambda s, r: r["assets"].append({"name": "owner-added-notes.txt"}))

    def test_cannot_delete_executable(self):
        self.assert_rejected(lambda s, r: s["remove_asset"].update(name=s["keep_asset"]["name"]))

    def test_changed_downloaded_checksums(self):
        spec, release, sums = fixture()
        with self.assertRaises(ValueError):
            plan_release(release, spec, sums.replace(b"fcfa", b"0000"))

    def test_bad_staged_checksums(self):
        self.assert_rejected(lambda s, r: r["assets"].append({"name": STAGED_SUMS, "size": 1, "digest": "bad"}))

    def test_text_replacement_must_be_unique(self):
        spec, _, _ = fixture()
        spec["replacements"].append(["missing", "new"])
        with self.assertRaises(ValueError):
            desired_body(spec)


class ApplyChecks(unittest.TestCase):
    def test_only_requested_zip_and_old_sums_are_deleted(self):
        spec, release, sums = fixture()
        client = FakeGitHub(release)
        client.apply(plan_release(release, spec, sums))
        expected = {spec["keep_asset"]["name"], "SHA256SUMS.txt"}
        self.assertEqual({a["name"] for a in client.current["assets"]}, expected)
        self.assertIn(spec["keep_asset"], client.current["assets"])
        deleted = {int(route.rsplit("/", 1)[1]) for route, method in client.calls if method == "DELETE"}
        self.assertEqual(deleted, {999, spec["remove_asset"]["id"]})

    def test_failed_upload_retains_existing_assets(self):
        spec, release, sums = fixture()
        client = FakeGitHub(release)
        client.bad_upload = True
        with self.assertRaises(ValueError):
            client.apply(plan_release(release, spec, sums))
        self.assertFalse(any(method == "DELETE" for _, method in client.calls))
        for asset in release["assets"]:
            self.assertIn(asset, client.current["assets"])

    def test_successful_rerun_has_no_mutations(self):
        spec, release, sums = fixture()
        client = FakeGitHub(release)
        first_plan = plan_release(release, spec, sums)
        client.apply(first_plan)
        client.calls.clear()
        public = first_plan["public_checksums"].encode()
        client.apply(plan_release(client.current, spec, public))
        self.assertEqual(client.calls, [])

    def test_resume_after_old_sums_deleted(self):
        spec, release, sums = fixture()
        public = public_checksums(sums.decode(), [spec["keep_asset"]["name"]])
        release["assets"][-1] = {"id": 1000, "name": STAGED_SUMS, "size": len(public), "digest": digest(public)}
        client = FakeGitHub(release)
        client.apply(plan_release(release, spec, public))
        self.assertEqual({a["name"] for a in client.current["assets"]}, {spec["keep_asset"]["name"], "SHA256SUMS.txt"})

    def test_resume_after_zip_already_removed(self):
        spec, release, sums = fixture(1)
        release["assets"].pop(1)
        client = FakeGitHub(release)
        client.apply(plan_release(release, spec, sums))
        self.assertIn(spec["keep_asset"], client.current["assets"])
        self.assertEqual(client.current["body"], desired_body(spec))


class PublisherChecks(unittest.TestCase):
    def test_public_sums_exclude_zip_without_changing_internal_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            binary = b"native-tested-executable"
            archive = b"developer-archive"
            (path / "app.exe").write_bytes(binary)
            (path / "internal.zip").write_bytes(archive)
            sums = f"{digest(binary)[7:]}  app.exe\n{digest(archive)[7:]}  internal.zip\n"
            (path / "SHA256SUMS.txt").write_text(sums)
            prepared = prepare_public_assets(path, ["app.exe"])
            self.assertEqual(set(prepared), {"app.exe", "SHA256SUMS.txt"})
            self.assertEqual(prepared["app.exe"], binary)
            self.assertEqual(set(parse_checksums(prepared["SHA256SUMS.txt"].decode())), {"app.exe"})
            self.assertEqual((path / "SHA256SUMS.txt").read_text(), sums)
            self.assertEqual((path / "internal.zip").read_bytes(), archive)

    def test_modified_binary_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "app.dmg").write_bytes(b"modified")
            (path / "SHA256SUMS.txt").write_text(f"{digest(b'original')[7:]}  app.dmg\n")
            with self.assertRaises(ValueError):
                prepare_public_assets(path, ["app.dmg"])

    def test_duplicate_checksum_rejected(self):
        with self.assertRaises(ValueError):
            parse_checksums(("0" * 64 + "  app.exe\n") * 2)

    def test_invalid_checksum_rejected(self):
        with self.assertRaises(ValueError):
            parse_checksums("invalid  app.exe\n")

    def test_missing_public_checksum_rejected(self):
        with self.assertRaises(ValueError):
            public_checksums("0" * 64 + "  other.exe\n", ["app.exe"])

    def test_publishers_do_not_include_zip_assets(self):
        paths = ["windows/winrelease/publish.py", "macos/macos/publish_mac_release.py"]
        for index, path in enumerate(paths):
            spec = importlib.util.spec_from_file_location("publisher" + str(index), ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if index == 0:
                self.assertEqual(module.FILENAMES, ("Facility_Studio_V5_5_7_Windows_Offline.exe", "SHA256SUMS.txt"))
            else:
                source = (ROOT / path).read_text()
                self.assertNotIn("_OneClick.zip", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
