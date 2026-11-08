"""Independent portable tutorial checks. Select a source/platform by environment.

The tests import real product code, but use independent numerical oracles and
compare generated reports as software-regression evidence, not physics proof.
They never clear a module cache, force an author checkout, or open a browser.
"""

import hashlib
import json
import math
import os
import re
import sys
import subprocess
from functools import lru_cache
import zipfile
from html import unescape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(
    os.environ.get("FACILITY_SOURCE_TREE", Path(__file__).resolve().parents[1])
).resolve()
PLATFORM = os.environ.get("FACILITY_TEST_PLATFORM", "macos")
BASELINE_MANIFEST = json.loads(
    (
        Path(__file__).with_name("independent_tutorial_resources")
        / "v19-source-manifest.json"
    ).read_text()
)
BASELINE_FILES = {row["path"]: row for row in BASELINE_MANIFEST["files"]}
assert PLATFORM in ("macos", "windows")
sys.path.insert(0, str(ROOT / PLATFORM))
from facility_studio import ahu_engine, engine, reports, tutorial_help
from facility_studio.lighting_direct import calculate_direct
from facility_studio.photometry import load_photometry
from facility_studio.workspace_store import read_workspace

TUTORIAL = ROOT / "docs/tutorial"
REPORT_NAMES = (
    "01_Expected_Report.txt",
    "01_Expected_Report.en.txt",
    "02_Expected_AHU_Report.txt",
    "02_Expected_AHU_Report.en.txt",
)


def parse_data(page):
    m = re.search(
        r'<script\s+type="application/json"\s+id="tutorial-data">(.*?)</script>',
        page,
        re.DOTALL,
    )
    assert m, "tutorial-data missing"
    return json.loads(m[1])


def normalized(text):
    return ("\n".join(x.rstrip() for x in str(text).splitlines()) + "\n").encode(
        "utf-8"
    )


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.assets = []
        self.ids = set()

    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if key in a:
                self.links.append(a[key])
                if key == "src" or tag != "a":
                    self.assets.append(a[key])


def check_local_links(text, containing_file, root, extra_ids=()):
    parser = Assets()
    parser.feed(text)
    parser.ids.update(extra_ids)
    links = parser.links + re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text)
    for raw in links:
        part = urlsplit(unescape(raw))
        if part.scheme or part.netloc:
            continue
        if not part.path:
            # Markdown headings have renderer-dependent slugs; explicit chapter
            # fragments in HTML are verified separately below.
            continue
        target = (containing_file.parent / unquote(part.path)).resolve()
        assert target.is_relative_to(root), f"Link escapes source: {raw}"
        assert target.is_file(), f"Broken local link in {containing_file}: {raw}"


def test_actual_selected_source_is_imported():
    for module in (tutorial_help, engine, reports, ahu_engine):
        assert Path(module.__file__).resolve().is_relative_to(ROOT / PLATFORM)


def test_all_generated_reports_and_all_active_locations():
    first = engine.calculate(read_workspace(TUTORIAL / "01_Practice_AHU.json")["main"])
    second = ahu_engine.nm_calculate(
        read_workspace(TUTORIAL / "02_Practice_MAU_and_AHU.json")["ahus"][0]["inputs"]
    )
    archives = [
        ROOT / PLATFORM / "facility_studio/resources/beginner_tutorial.zip",
        TUTORIAL
        / (
            "Facility_Studio_Beginner_Tutorial_"
            + ("Windows" if PLATFORM == "windows" else "macOS")
            + ".zip"
        ),
    ]
    for lang, suffix in [("zh-Hant", ""), ("en", ".en")]:
        for stem, result, render in [
            ("01_Expected_Report", first, reports.report),
            ("02_Expected_AHU_Report", second, reports.nm_report),
        ]:
            name = stem + suffix + ".txt"
            actual = normalized(render(result, language=lang))
            assert (TUTORIAL / PLATFORM / name).read_bytes() == actual, (
                f"{PLATFORM}/{name} is stale"
            )
            if PLATFORM == "windows":
                assert (TUTORIAL / name).read_bytes() == actual, f"root/{name} is stale"
            for archive in archives:
                with zipfile.ZipFile(archive) as z:
                    assert z.read(name) == actual, f"{archive}/{name} is stale"
    # Preserve independently published baseline numeric values.
    assert first["qs"] == pytest.approx(7.869996, abs=1e-9)
    assert first["ql"] == pytest.approx(0.44, abs=1e-9)
    assert first["light"]["qty"] == 25
    assert first["supply_room_cmh"] == pytest.approx(2400.235496650782, abs=1e-8)
    assert first["water"]["CHW"]["lpm"] == pytest.approx(37.282459, abs=5e-7)


def test_active_archive_identity_content_local_assets_and_platform():
    suffix = "Windows" if PLATFORM == "windows" else "macOS"
    named = TUTORIAL / f"Facility_Studio_Beginner_Tutorial_{suffix}.zip"
    embedded = ROOT / PLATFORM / "facility_studio/resources/beginner_tutorial.zip"
    assert named.read_bytes() == embedded.read_bytes()
    source = parse_data((TUTORIAL / "START_HERE.html").read_text())
    with zipfile.ZipFile(named) as z:
        names = z.namelist()
        allowed = tutorial_help.TUTORIAL_FILES
        assert len(names) == len(set(names)) and set(names) == allowed
        assert all(
            not PurePosixPath(n).is_absolute()
            and ".." not in PurePosixPath(n).parts
            and "\\" not in n
            for n in names
        )
        page = parse_data(z.read("START_HERE.html").decode())
        assert source["content"] == page["content"]
        for lang in ("zh-Hant", "en"):
            assert suffix in page["labels"][lang]["offline"]
            parser = Assets()
            for row in page["content"][lang]:
                parser.ids.add(row["id"])
                parser.feed(row["html"])
            # Include static sidebar links/assets too.
            parser.feed(z.read("START_HERE.html").decode())
            for asset in parser.assets:
                part = urlsplit(unescape(asset))
                assert not part.scheme and not part.netloc, (
                    f"Network asset in offline bundle: {asset}"
                )
            for raw in parser.links:
                part = urlsplit(unescape(raw))
                if part.scheme or part.netloc:
                    assert part.scheme in ("https", "http") and part.netloc, (
                        f"Unsafe external link {raw}"
                    )
                    continue
                if not part.path:
                    if part.fragment:
                        assert part.fragment in parser.ids, raw
                else:
                    assert unquote(part.path) in names, f"Missing bundled asset {raw}"
        for name in names:
            if name == "START_HERE.html" or name in REPORT_NAMES:
                continue
            p = TUTORIAL / name
            if not p.exists() and name.startswith("LICENSE"):
                p = ROOT / name
            assert p.is_file(), f"Missing source asset {name}"
            assert z.read(name) == p.read_bytes(), f"Stale asset {name}"


def test_root_and_guide_links_resolve():
    paths = [
        ROOT / "README.md",
        ROOT / "README.en.md",
        ROOT / "docs/README.md",
        ROOT / "docs/README.en.md",
        TUTORIAL / "README.md",
        TUTORIAL / "START_HERE.html",
    ]
    paths.extend((ROOT / "docs/guides").glob("*.md"))
    for path in paths:
        if path.exists():
            check_local_links(path.read_text(), path, ROOT)
    for rows in parse_data((TUTORIAL / "START_HERE.html").read_text())[
        "content"
    ].values():
        for row in rows:
            check_local_links(
                row["html"], TUTORIAL / "START_HERE.html", ROOT, (r["id"] for r in rows)
            )
    assert "handoff/STATUS.json" not in (TUTORIAL / "README.md").read_text()


def test_direct_exercise_uses_existing_synthetic_file_and_independent_oracle():
    candidates = [n for n in tutorial_help.TUTORIAL_FILES if n.endswith(".ies")]
    assert len(candidates) == 1, "An offline synthetic IES source must be bundled"
    source = TUTORIAL / candidates[0]
    assert (
        source.read_bytes()
        == (
            ROOT / "docs/examples/direct-lighting/synthetic-constant-1000cd.ies"
        ).read_bytes()
    )
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == "f03fd81cd35c3dcb010b07237053a3863388e339260bc3ea83dcc8b9d65ba093"
    )
    photometry = load_photometry(source)
    # Fixed inputs and closed-form geometry are independent of tutorial oracle
    # JSON, tutorial generator, verifier and product output.
    scene = {
        "length_m": 2,
        "width_m": 2,
        "workplane_m": 0,
        "edge_m": 0,
        "nx": 2,
        "ny": 2,
        "maintenance": 1,
        "fixtures": [
            {
                "photometry": "SYN",
                "x_m": 1,
                "y_m": 1,
                "z_m": 2,
                "yaw_deg": 0,
                "multiplier": 1,
            }
        ],
    }
    expected = 1000 * 2 / math.pow(4 + 0.5, 1.5)
    assert expected == pytest.approx(209.51312035156963, rel=0, abs=1e-12)
    for maintenance in (1, 0.8):
        scene["maintenance"] = maintenance
        output = calculate_direct({"SYN": photometry}, scene)
        assert output["grid"]["x_m"] == [0.5, 1.5]
        assert output["grid"]["y_m"] == [0.5, 1.5]
        assert all(
            v == pytest.approx(expected * maintenance, abs=1e-10)
            for row in output["grid"]["lux"]
            for v in row
        )
        assert output["summary"]["uniformity_min_avg"] == 1
        assert output["reflected_lux"] is None and output["ugr"] is None
    scene["nx"] = scene["ny"] = 4
    scene["maintenance"] = 1
    refined = calculate_direct({"SYN": photometry}, scene)
    assert refined["summary"]["minimum_lux"] < refined["summary"]["maximum_lux"], (
        "Equal coarse samples are not a uniform continuous field"
    )


class ExerciseFields(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}
        self.active = None

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if "data-exercise" in attributes:
            key = attributes["data-exercise"]
            assert key not in self.fields, f"Duplicate exercise field {key}"
            self.fields[key] = ""
            self.active = (tag, key)

    def handle_data(self, text):
        if self.active:
            self.fields[self.active[1]] += text

    def handle_endtag(self, tag):
        if self.active and self.active[0] == tag:
            self.active = None


def test_every_published_exercise_field_matches_independent_geometry_and_oracle():
    pages = [(TUTORIAL / "START_HERE.html").read_text()]
    suffix = "Windows" if PLATFORM == "windows" else "macOS"
    for path in [
        TUTORIAL / f"Facility_Studio_Beginner_Tutorial_{suffix}.zip",
        ROOT / PLATFORM / "facility_studio/resources/beginner_tutorial.zip",
    ]:
        with zipfile.ZipFile(path) as z:
            pages.append(z.read("START_HERE.html").decode())
    for page in pages:
        for language in ("zh-Hant", "en"):
            chapter = next(
                r["html"]
                for r in parse_data(page)["content"][language]
                if r["id"] == "lighting"
            )
            fields = ExerciseFields()
            fields.feed(chapter)
            fields = fields.fields
            expected = {
                "length_m": 2,
                "width_m": 2,
                "workplane_m": 0,
                "edge_m": 0,
                "nx": 2,
                "ny": 2,
                "maintenance": 1,
            }
            assert set(fields) == set(expected) | {"schedule", "lux-m1", "lux-m08"}
            for key, value in expected.items():
                assert float(fields[key]) == value
            row = fields["schedule"].split(",")
            assert row[0] == "P1"
            assert [float(x) for x in row[1:]] == [1, 1, 2, 0, 1]
            # Independently derive from the actual published geometry, not
            # from product code or the product verifier's accepted strings.
            length, width = float(fields["length_m"]), float(fields["width_m"])
            sample_x, sample_y = length / 4, width / 4
            x, y, z, _yaw, scale = (float(x) for x in row[1:])
            height = z - float(fields["workplane_m"])
            expected_lux = (
                1000
                * height
                / ((sample_x - x) ** 2 + (sample_y - y) ** 2 + height**2) ** 1.5
                * scale
            )
            assert float(fields["lux-m1"]) == pytest.approx(
                expected_lux, rel=0, abs=0.5e-6
            )
            assert float(fields["lux-m08"]) == pytest.approx(
                expected_lux * 0.8, rel=0, abs=0.5e-6
            )


@lru_cache(maxsize=None)
def indexed_modes(root):
    """Read a dedicated source checkout's authoritative index, not NTFS flags.

    CI reconstructs this index from the preserved source manifest and explicit
    overlays. Caller still verifies frozen hashes, plus the index blob below.
    Missing/unmerged entries fail closed; no guessed filename permissions.
    """
    top = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--show-toplevel"], text=True).strip()
    assert Path(top).resolve() == root.resolve(), "Source tree needs its own provenance index"
    rows = subprocess.check_output(["git", "-C", str(root), "ls-files", "--stage", "-z"])
    entries = {}
    for row in rows.split(b"\0"):
        if not row:
            continue
        metadata, name = row.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        assert stage == "0", "Unmerged source provenance index"
        entries[name.decode("utf-8")] = mode, oid
    return entries


def indexed_source_mode(root, relative, body):
    entries = indexed_modes(root)
    assert relative in entries, f"Missing indexed mode provenance: {relative}"
    mode, oid = entries[relative]
    assert mode in ("100644", "100755"), f"Unsupported indexed file mode: {relative}"
    assert len(oid) in (40, 64), "Unsupported Git object format"
    payload = b"blob " + str(len(body)).encode("ascii") + b"\0" + body
    actual = hashlib.new("sha1" if len(oid) == 40 else "sha256", payload).hexdigest()
    assert actual == oid, f"Indexed mode is not bound to current file bytes: {relative}"
    return mode


def source_mode(path, relative, body):
    if os.name == "nt":
        return indexed_source_mode(ROOT, relative, body)
    return "100755" if path.stat().st_mode & 0o111 else "100644"


def test_indexed_mode_requires_matching_blob_and_explicit_mode(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    path = tmp_path / "launcher.command"
    path.write_bytes(b"#!/bin/sh\nexit 0\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "launcher.command"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "update-index", "--chmod=+x", "launcher.command"], check=True)
    assert indexed_source_mode(tmp_path, "launcher.command", path.read_bytes()) == "100755"
    with pytest.raises(AssertionError, match="not bound"):
        indexed_source_mode(tmp_path, "launcher.command", path.read_bytes() + b"# changed\n")
    with pytest.raises(AssertionError, match="Missing indexed"):
        indexed_source_mode(tmp_path, "missing.command", b"")
    subprocess.run(["git", "-C", str(tmp_path), "update-index", "--chmod=-x", "launcher.command"], check=True)
    indexed_modes.cache_clear()
    # Same extension, different authoritative mode: never infer executable.
    assert indexed_source_mode(tmp_path, "launcher.command", path.read_bytes()) == "100644"


def assert_original_bytes(relative):
    row = BASELINE_FILES[relative]
    path = ROOT / relative
    assert path.is_file(), f"Original path missing: {relative}"
    body = path.read_bytes()
    assert (
        len(body) == row["bytes"] and hashlib.sha256(body).hexdigest() == row["sha256"]
    ), f"Original bytes changed: {relative}"
    mode = source_mode(path, relative, body)
    assert mode == row["mode"], f"Original mode changed: {relative}"


# Historical v21 Tk transitions remain exact and unchanged. Additional v22
# endpoints are pinned separately below. None are exclusions, and the frozen
# v19 manifest remains unchanged.
REVIEWED_V21_TK_REPAIRS = {
    "macos/facility_studio/acceptance_contract.py": {
        "v19": {
            "sha256": "f557a6514515e0d148dc157bd6f25e734a2492c37905c69a44c6510fc6764f0d",
            "bytes": 16520,
            "mode": "100644",
        },
        "v21": {
            "sha256": "e945e038f567dfd17f19b953ae7c60a19424663fdbce592eaa2a80dabebbb638",
            "bytes": 16520,
            "mode": "100644",
        },
    },
    "macos/facility_studio/fusion_acceptance.py": {
        "v19": {
            "sha256": "f53d7a0d90ea63453e62f64ddc0336b75186ec5d208b848b43fdcd51136a61d1",
            "bytes": 9262,
            "mode": "100644",
        },
        "v21": {
            "sha256": "9fb419c2f9d394a231b3237dc8198e7f8a3918034dde5245f7346ada002c5033",
            "bytes": 12692,
            "mode": "100644",
        },
    },
    "windows/facility_studio/acceptance_contract.py": {
        "v19": {
            "sha256": "f557a6514515e0d148dc157bd6f25e734a2492c37905c69a44c6510fc6764f0d",
            "bytes": 16520,
            "mode": "100644",
        },
        "v21": {
            "sha256": "e945e038f567dfd17f19b953ae7c60a19424663fdbce592eaa2a80dabebbb638",
            "bytes": 16520,
            "mode": "100644",
        },
    },
    "windows/facility_studio/fusion_acceptance.py": {
        "v19": {
            "sha256": "f53d7a0d90ea63453e62f64ddc0336b75186ec5d208b848b43fdcd51136a61d1",
            "bytes": 9262,
            "mode": "100644",
        },
        "v21": {
            "sha256": "9fb419c2f9d394a231b3237dc8198e7f8a3918034dde5245f7346ada002c5033",
            "bytes": 12692,
            "mode": "100644",
        },
    },
}


# Explicit reviewed v22 endpoints. The four historically excepted tutorial
# helper/archive paths are now pinned too. No current-file-derived approvals.
REVIEWED_V22_PRODUCT_TRANSITIONS = {'macos/facility_studio/audit_acceptance.py': {'reason': 'Reviewed existing acceptance '
                                                         'producer/test load-only contract.',
                                               'v19': {'bytes': 41596,
                                                       'mode': '100644',
                                                       'sha256': 'ae430e5cbcbc18fb411c7dd0252ade1b67741718371f59a4a6543cde24ac8074'},
                                               'v21': {'bytes': 41596,
                                                       'mode': '100644',
                                                       'sha256': 'ae430e5cbcbc18fb411c7dd0252ade1b67741718371f59a4a6543cde24ac8074'},
                                               'v22': {'bytes': 42236,
                                                       'mode': '100644',
                                                       'sha256': '1cb446c35ad860538dd4fce3c1e441bc3a9b9c45ca144ae559597d47b0d57079'}},
 'macos/facility_studio/cli.py': {'reason': 'Reviewed load-only electrical safety gate runtime; no '
                                            'automatic sizing authority.',
                                  'v19': {'bytes': 8222,
                                          'mode': '100644',
                                          'sha256': 'a56a4ddf2f7ba3569888863e3cd731918a527b7ed4c1f5a7f60ff3d2673d8cf9'},
                                  'v21': {'bytes': 8222,
                                          'mode': '100644',
                                          'sha256': 'a56a4ddf2f7ba3569888863e3cd731918a527b7ed4c1f5a7f60ff3d2673d8cf9'},
                                  'v22': {'bytes': 8317,
                                          'mode': '100644',
                                          'sha256': 'ba6f8b842b3dd564bd471ef94ccbc1476a6d89dad8e1f33bf3d8a9ed490da96c'}},
 'macos/facility_studio/desktop.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                'runtime; no automatic sizing authority.',
                                      'v19': {'bytes': 56787,
                                              'mode': '100644',
                                              'sha256': 'c587a18970fec4c123c56b098695e53a7aba727a4c9223698bdaafb88bf8b43f'},
                                      'v21': {'bytes': 56787,
                                              'mode': '100644',
                                              'sha256': 'c587a18970fec4c123c56b098695e53a7aba727a4c9223698bdaafb88bf8b43f'},
                                      'v22': {'bytes': 56862,
                                              'mode': '100644',
                                              'sha256': '4a3779a0a9adb176da2530dca87074f55ff894c2a9a1a54b116a746e0683a26a'}},
 'macos/facility_studio/display_helpers.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                        'runtime; no automatic sizing authority.',
                                              'v19': {'bytes': 10215,
                                                      'mode': '100644',
                                                      'sha256': '7aeb3068c36ab07a98dda0cc7119ef1dbc3438dc06c323c1915a5507a160ad65'},
                                              'v21': {'bytes': 10215,
                                                      'mode': '100644',
                                                      'sha256': '7aeb3068c36ab07a98dda0cc7119ef1dbc3438dc06c323c1915a5507a160ad65'},
                                              'v22': {'bytes': 9968,
                                                      'mode': '100644',
                                                      'sha256': '4c305c5c36f7547c87074779d14629678e2b0beaf763f5ef43afaf00276cccc5'}},
 'macos/facility_studio/electrical_disclosures.py': {'reason': 'Reviewed load-only electrical '
                                                               'safety gate runtime; no automatic '
                                                               'sizing authority.',
                                                     'v19': {'bytes': 2522,
                                                             'mode': '100644',
                                                             'sha256': '801ac3c452d201e0a482efb9182c1e4da073b43d4b51127720cc7fc23b610a51'},
                                                     'v21': {'bytes': 2522,
                                                             'mode': '100644',
                                                             'sha256': '801ac3c452d201e0a482efb9182c1e4da073b43d4b51127720cc7fc23b610a51'},
                                                     'v22': {'bytes': 11347,
                                                             'mode': '100644',
                                                             'sha256': '70f1c915fa35d9efdd515ea43efd1f8e94b26fdb7095672a1255e8681e294da0'}},
 'macos/facility_studio/english_catalog.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                        'runtime; no automatic sizing authority.',
                                              'v19': {'bytes': 440401,
                                                      'mode': '100644',
                                                      'sha256': '88ec9ae2bd81eb2b102d06a5b104a74f7d751da9c654856d69c255e9b4a1ceb0'},
                                              'v21': {'bytes': 440401,
                                                      'mode': '100644',
                                                      'sha256': '88ec9ae2bd81eb2b102d06a5b104a74f7d751da9c654856d69c255e9b4a1ceb0'},
                                              'v22': {'bytes': 447988,
                                                      'mode': '100644',
                                                      'sha256': '4f27d571a6a3aba004761ca341f12eec13249e7960d557442e7d36fda2c507f0'}},
 'macos/facility_studio/equipment_analysis.py': {'reason': 'Reviewed load-only electrical safety '
                                                           'gate runtime; no automatic sizing '
                                                           'authority.',
                                                 'v19': {'bytes': 30966,
                                                         'mode': '100644',
                                                         'sha256': 'd66775801f23fcdea3e38a5808d0d178f327eae0e880e1162ec01370d2bcde63'},
                                                 'v21': {'bytes': 30966,
                                                         'mode': '100644',
                                                         'sha256': 'd66775801f23fcdea3e38a5808d0d178f327eae0e880e1162ec01370d2bcde63'},
                                                 'v22': {'bytes': 30597,
                                                         'mode': '100644',
                                                         'sha256': '2a7f47a510175c2bb093e05ba2e44f54c696496c87b63ff70eddf10a509a9ccc'}},
 'macos/facility_studio/equipment_io.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                     'runtime; no automatic sizing authority.',
                                           'v19': {'bytes': 22079,
                                                   'mode': '100644',
                                                   'sha256': '5e061df5287bfdecbc4f259647eb17061e008a0340b5d0d6ad47244b3f69ae72'},
                                           'v21': {'bytes': 22079,
                                                   'mode': '100644',
                                                   'sha256': '5e061df5287bfdecbc4f259647eb17061e008a0340b5d0d6ad47244b3f69ae72'},
                                           'v22': {'bytes': 22154,
                                                   'mode': '100644',
                                                   'sha256': '1a09634087be9126939381c36e4a0fe8eea6980e5f057215f38e59e05f75fee9'}},
 'macos/facility_studio/html_report.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                    'runtime; no automatic sizing authority.',
                                          'v19': {'bytes': 11535,
                                                  'mode': '100644',
                                                  'sha256': 'bdc139348330d58d9549bde8b4887f39ea62ccc40cb8db09c50b891b6a5608e0'},
                                          'v21': {'bytes': 11535,
                                                  'mode': '100644',
                                                  'sha256': 'bdc139348330d58d9549bde8b4887f39ea62ccc40cb8db09c50b891b6a5608e0'},
                                          'v22': {'bytes': 11718,
                                                  'mode': '100644',
                                                  'sha256': 'f46815be71dead6d63099811a993c5bae4bc7b599556e29b2df13fbdffa794c4'}},
 'macos/facility_studio/inactive_acceptance.py': {'reason': 'Reviewed existing acceptance '
                                                            'producer/test load-only contract.',
                                                  'v19': {'bytes': 15596,
                                                          'mode': '100644',
                                                          'sha256': '429ba6eebe2fa78a3534845776ac9e26d8a17432cc65730a182c83b42eb80c68'},
                                                  'v21': {'bytes': 15596,
                                                          'mode': '100644',
                                                          'sha256': '429ba6eebe2fa78a3534845776ac9e26d8a17432cc65730a182c83b42eb80c68'},
                                                  'v22': {'bytes': 15730,
                                                          'mode': '100644',
                                                          'sha256': '98d4f99441dd9310704addd22de29dbb01e1c0d1ebbeecda83ee17fa835877ed'}},
 'macos/facility_studio/main_view.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                  'runtime; no automatic sizing authority.',
                                        'v19': {'bytes': 48074,
                                                'mode': '100644',
                                                'sha256': '46df4a073a73b95192af11173bc9a7202dfaf5c07a8fd59e3b194c6770590ad1'},
                                        'v21': {'bytes': 48074,
                                                'mode': '100644',
                                                'sha256': '46df4a073a73b95192af11173bc9a7202dfaf5c07a8fd59e3b194c6770590ad1'},
                                        'v22': {'bytes': 47991,
                                                'mode': '100644',
                                                'sha256': '6cf637419158293020b7be96b0a53027a6c0d5b3335b7b4347795835083518f4'}},
 'macos/facility_studio/quality.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                'runtime; no automatic sizing authority.',
                                      'v19': {'bytes': 23060,
                                              'mode': '100644',
                                              'sha256': 'cd757f38ca0a5b19c0e3e731cfc9dfe643a60b2a9a725a8511ee24700033433b'},
                                      'v21': {'bytes': 23060,
                                              'mode': '100644',
                                              'sha256': 'cd757f38ca0a5b19c0e3e731cfc9dfe643a60b2a9a725a8511ee24700033433b'},
                                      'v22': {'bytes': 23122,
                                              'mode': '100644',
                                              'sha256': '7664f0960014daf531e3374c7244683d6e6fd9dd8f8c1a2d25f3650b2577724f'}},
 'macos/facility_studio/quick_tools.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                    'runtime; no automatic sizing authority.',
                                          'v19': {'bytes': 13482,
                                                  'mode': '100644',
                                                  'sha256': '28d1738746d48bd8570e21eb2838b9b0ca57d8b1224d22d911fe74e68b005b0e'},
                                          'v21': {'bytes': 13482,
                                                  'mode': '100644',
                                                  'sha256': '28d1738746d48bd8570e21eb2838b9b0ca57d8b1224d22d911fe74e68b005b0e'},
                                          'v22': {'bytes': 13490,
                                                  'mode': '100644',
                                                  'sha256': 'ae127c8e39a3bb823ebcc34979026cca430c10616e0680f4a7209e9fa0719d16'}},
 'macos/facility_studio/reports.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                'runtime; no automatic sizing authority.',
                                      'v19': {'bytes': 56419,
                                              'mode': '100644',
                                              'sha256': '57c26b21b13a2b35606326fa05942d367c8aca871143f1e0bf4de3f54dbf894a'},
                                      'v21': {'bytes': 56419,
                                              'mode': '100644',
                                              'sha256': '57c26b21b13a2b35606326fa05942d367c8aca871143f1e0bf4de3f54dbf894a'},
                                      'v22': {'bytes': 55450,
                                              'mode': '100644',
                                              'sha256': 'bd223edea7f62686e33ee804b1fbe72fc54009936cefb62566b0f9cd732c6453'}},
 'macos/facility_studio/resources/Equipment_Template.xlsx': {'reason': 'Reviewed current '
                                                                       'tutorial/resource '
                                                                       'instructions and generated '
                                                                       'archive.',
                                                             'v19': {'bytes': 131243,
                                                                     'mode': '100644',
                                                                     'sha256': '9d629e2f18248f9050e31a231b9184991884b3e992dda5835298f4dd2449df28'},
                                                             'v21': {'bytes': 131243,
                                                                     'mode': '100644',
                                                                     'sha256': '9d629e2f18248f9050e31a231b9184991884b3e992dda5835298f4dd2449df28'},
                                                             'v22': {'bytes': 131291,
                                                                     'mode': '100644',
                                                                     'sha256': 'd2ef56ec750077a7fb2525418daa656ca2e7c1cef298bb4caf4f745efc010035'}},
 'macos/facility_studio/resources/beginner_tutorial.zip': {'reason': 'Reviewed current '
                                                                     'tutorial/resource '
                                                                     'instructions and generated '
                                                                     'archive.',
                                                           'v19': {'bytes': 90104,
                                                                   'mode': '100644',
                                                                   'sha256': '44ed93cebab1204bedf04d953b81a72e9ea0f709d1968635293f331d6253bbf1'},
                                                           'v21': {'bytes': 98469,
                                                                   'mode': '100644',
                                                                   'sha256': 'b3c8b1118e8fbf48496e8b72052624dba24893c989cdd41bb16b36531121fab9'},
                                                           'v22': {'bytes': 101164,
                                                                   'mode': '100644',
                                                                   'sha256': 'b54bec5df20744901de8a1d8cd187e1dfed2007e6d64aac7cb1f9ccdf3f3e42c'}},
 'macos/facility_studio/simple_engines.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                       'runtime; no automatic sizing authority.',
                                             'v19': {'bytes': 48755,
                                                     'mode': '100644',
                                                     'sha256': 'fcd91aec093de2051895be789b2f96d54fa7057e5d4fd5009a136cc87d883d35'},
                                             'v21': {'bytes': 48755,
                                                     'mode': '100644',
                                                     'sha256': 'fcd91aec093de2051895be789b2f96d54fa7057e5d4fd5009a136cc87d883d35'},
                                             'v22': {'bytes': 48984,
                                                     'mode': '100644',
                                                     'sha256': 'd85e7821ef75a4c545cc567228e4a99971fafe8c984e9fb3d48ee527eb966ea0'}},
 'macos/facility_studio/simple_reports.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                       'runtime; no automatic sizing authority.',
                                             'v19': {'bytes': 27987,
                                                     'mode': '100644',
                                                     'sha256': 'a932c5efa69f2c2dd8410222222720124078f8be3ce163097768662ff60ba6db'},
                                             'v21': {'bytes': 27987,
                                                     'mode': '100644',
                                                     'sha256': 'a932c5efa69f2c2dd8410222222720124078f8be3ce163097768662ff60ba6db'},
                                             'v22': {'bytes': 25463,
                                                     'mode': '100644',
                                                     'sha256': '87da65138f43cd4ccaa0b67ade463454e3c78d141ecbad882bfcd016654a9a2d'}},
 'macos/facility_studio/simple_schema.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                      'runtime; no automatic sizing authority.',
                                            'v19': {'bytes': 29977,
                                                    'mode': '100644',
                                                    'sha256': '4764f3f35871dc896eef23caf5ba8d604d1ae6c1e82dda72264436e7300d8906'},
                                            'v21': {'bytes': 29977,
                                                    'mode': '100644',
                                                    'sha256': '4764f3f35871dc896eef23caf5ba8d604d1ae6c1e82dda72264436e7300d8906'},
                                            'v22': {'bytes': 30127,
                                                    'mode': '100644',
                                                    'sha256': '2fd447d58cb53ce2acdd658be444cb382006a66f4f82c421384844af20deb6da'}},
 'macos/facility_studio/template_language.py': {'reason': 'Reviewed load-only electrical safety '
                                                          'gate runtime; no automatic sizing '
                                                          'authority.',
                                                'v19': {'bytes': 2550,
                                                        'mode': '100644',
                                                        'sha256': 'f7177bad498059d1fef7bf5cc9038d0b117e595bd730e19fb6e1a74980efd6e5'},
                                                'v21': {'bytes': 2550,
                                                        'mode': '100644',
                                                        'sha256': 'f7177bad498059d1fef7bf5cc9038d0b117e595bd730e19fb6e1a74980efd6e5'},
                                                'v22': {'bytes': 3382,
                                                        'mode': '100644',
                                                        'sha256': '69c64da70c1086731e5a587ea77e804ab8497ccd921edd015c4895752548e3fe'}},
 'macos/facility_studio/tools_view.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                   'runtime; no automatic sizing authority.',
                                         'v19': {'bytes': 33383,
                                                 'mode': '100644',
                                                 'sha256': '9100a33d1a78f74a45d0ef931f1b2e4d6024b17f6b7d049cf2319c76070eb3fd'},
                                         'v21': {'bytes': 33383,
                                                 'mode': '100644',
                                                 'sha256': '9100a33d1a78f74a45d0ef931f1b2e4d6024b17f6b7d049cf2319c76070eb3fd'},
                                         'v22': {'bytes': 34637,
                                                 'mode': '100644',
                                                 'sha256': '6bfe1acc7ddab1321447a5ae97744d16a79b91fc4c06f87ac3b6fd2372ab7610'}},
 'macos/facility_studio/tutorial_help.py': {'reason': 'Historical v19-to-v21 tutorial helper, '
                                                      'previously excepted; unchanged in v22 and '
                                                      'now pinned.',
                                            'v19': {'bytes': 3033,
                                                    'mode': '100644',
                                                    'sha256': '4d235b82247e0e4610433d62b686415a6c8b556e4bcd9047d0ad4cd0556b7478'},
                                            'v21': {'bytes': 5526,
                                                    'mode': '100644',
                                                    'sha256': '90d8e34eac952c0106e80e73ad4ce42ebad5357c30ad8cb168188ed02d7f387e'},
                                            'v22': {'bytes': 5526,
                                                    'mode': '100644',
                                                    'sha256': '90d8e34eac952c0106e80e73ad4ce42ebad5357c30ad8cb168188ed02d7f387e'}},
 'macos/facility_studio/utils.py': {'reason': 'Reviewed load-only electrical safety gate runtime; '
                                              'no automatic sizing authority.',
                                    'v19': {'bytes': 34192,
                                            'mode': '100644',
                                            'sha256': '8ecee6b63599c0130c35544d60aed4e689e7b503659d6bdca1929e357bbfcb91'},
                                    'v21': {'bytes': 34192,
                                            'mode': '100644',
                                            'sha256': '8ecee6b63599c0130c35544d60aed4e689e7b503659d6bdca1929e357bbfcb91'},
                                    'v22': {'bytes': 34500,
                                            'mode': '100644',
                                            'sha256': 'd62fad05ee68cac844ba43275872fdb485af87269565840b80b1787d553bf981'}},
 'macos/facility_studio/workflow_acceptance.py': {'reason': 'Reviewed existing acceptance '
                                                            'producer/test load-only contract.',
                                                  'v19': {'bytes': 13181,
                                                          'mode': '100644',
                                                          'sha256': '9ba601a9f0a45214cf97a009e4c58c2f92d847e30261f6397da3cd722d7af428'},
                                                  'v21': {'bytes': 13181,
                                                          'mode': '100644',
                                                          'sha256': '9ba601a9f0a45214cf97a009e4c58c2f92d847e30261f6397da3cd722d7af428'},
                                                  'v22': {'bytes': 13359,
                                                          'mode': '100644',
                                                          'sha256': '50bdabc77ecd256e60a6e6cdea660b7283a430c35910ab667d2ac7b32bad2f16'}},
 'macos/tests/electrical_units.py': {'reason': 'Reviewed existing acceptance producer/test '
                                               'load-only contract.',
                                     'v19': {'bytes': 15947,
                                             'mode': '100644',
                                             'sha256': '73d016fb987082eeb65989a033063f7987d25c15bfce450bd0536846abac484b'},
                                     'v21': {'bytes': 15947,
                                             'mode': '100644',
                                             'sha256': '73d016fb987082eeb65989a033063f7987d25c15bfce450bd0536846abac484b'},
                                     'v22': {'bytes': 16030,
                                             'mode': '100644',
                                             'sha256': '3a10aae5bf830cecfcabfce616dff8974b65b46187398f0e41d85b9475cfbdca'}},
 'macos/tests/feed_stress/stress_f.py': {'reason': 'Reviewed existing acceptance producer/test '
                                                   'load-only contract.',
                                         'v19': {'bytes': 6735,
                                                 'mode': '100644',
                                                 'sha256': 'e52e0d8eb6f31495769732c816ba3f88949ae53fd30e2752ac2a6ae40c687f0d'},
                                         'v21': {'bytes': 6735,
                                                 'mode': '100644',
                                                 'sha256': 'e52e0d8eb6f31495769732c816ba3f88949ae53fd30e2752ac2a6ae40c687f0d'},
                                         'v22': {'bytes': 6653,
                                                 'mode': '100644',
                                                 'sha256': 'a447db091b29f050f4a4401f5c6e5fc1021953427778f5183c4b1f4fcb502587'}},
 'macos/tests/independent.py': {'reason': 'Reviewed existing acceptance producer/test load-only '
                                          'contract.',
                                'v19': {'bytes': 8309,
                                        'mode': '100644',
                                        'sha256': 'bd76feaa7818fee65881b2ffd1287102c14e6339df0599af7f95fd8f3cd2d9bc'},
                                'v21': {'bytes': 8309,
                                        'mode': '100644',
                                        'sha256': 'bd76feaa7818fee65881b2ffd1287102c14e6339df0599af7f95fd8f3cd2d9bc'},
                                'v22': {'bytes': 6067,
                                        'mode': '100644',
                                        'sha256': '2cd7e322f59c8463590d442a0ea75aeea70755db15f9342ab11a07f0db2cfd72'}},
 'macos/tests/regression.py': {'reason': 'Reviewed existing acceptance producer/test load-only '
                                         'contract.',
                               'v19': {'bytes': 1751,
                                       'mode': '100644',
                                       'sha256': '525bed8dce04e90de2dfdc3a74ffb834562120447c9608c82308301aa1ab6850'},
                               'v21': {'bytes': 1751,
                                       'mode': '100644',
                                       'sha256': '525bed8dce04e90de2dfdc3a74ffb834562120447c9608c82308301aa1ab6850'},
                               'v22': {'bytes': 1751,
                                       'mode': '100644',
                                       'sha256': '8fca70172fb8d7af96ecabc87acfcff5fc40f0a65fbce7b267406ccab689b8f5'}},
 'macos/tests/simple_features.py': {'reason': 'Reviewed existing acceptance producer/test '
                                              'load-only contract.',
                                    'v19': {'bytes': 14522,
                                            'mode': '100644',
                                            'sha256': 'c74fc79cb3d5fe085eb841925f70e84bea5325c7a0bae7548227ed6e15b30556'},
                                    'v21': {'bytes': 14522,
                                            'mode': '100644',
                                            'sha256': 'c74fc79cb3d5fe085eb841925f70e84bea5325c7a0bae7548227ed6e15b30556'},
                                    'v22': {'bytes': 14213,
                                            'mode': '100644',
                                            'sha256': '7330f5aaf39ed7c860e47d65d56f67dd2cd6874bc39d791d870d1122f6d165bb'}},
 'macos/tests/simple_gui.py': {'reason': 'Reviewed existing acceptance producer/test load-only '
                                         'contract.',
                               'v19': {'bytes': 10858,
                                       'mode': '100644',
                                       'sha256': 'd23fc39643f10215223fc714fd1cf76c7bd8ef2dc68790246993d49310656db3'},
                               'v21': {'bytes': 10858,
                                       'mode': '100644',
                                       'sha256': 'd23fc39643f10215223fc714fd1cf76c7bd8ef2dc68790246993d49310656db3'},
                               'v22': {'bytes': 11058,
                                       'mode': '100644',
                                       'sha256': '82e68bebb4ae02029c8dd0451ffa3b27bbe97e5f25cad5405ab84e726f9c409f'}},
 'macos/tests/v554_features.py': {'reason': 'Reviewed existing acceptance producer/test load-only '
                                            'contract.',
                                  'v19': {'bytes': 22155,
                                          'mode': '100644',
                                          'sha256': 'c6896e008988a1b5bab5ca4bdb77e82eeab589012c678247cee89cea7704d8c5'},
                                  'v21': {'bytes': 22155,
                                          'mode': '100644',
                                          'sha256': 'c6896e008988a1b5bab5ca4bdb77e82eeab589012c678247cee89cea7704d8c5'},
                                  'v22': {'bytes': 21987,
                                          'mode': '100644',
                                          'sha256': 'ea0cff5aff0b4a72f0c2ca489448d8eb08d2a6e0badfcce9421a8fd5beecf1c7'}},
 'windows/facility_studio/audit_acceptance.py': {'reason': 'Reviewed existing acceptance '
                                                           'producer/test load-only contract.',
                                                 'v19': {'bytes': 41596,
                                                         'mode': '100644',
                                                         'sha256': 'ae430e5cbcbc18fb411c7dd0252ade1b67741718371f59a4a6543cde24ac8074'},
                                                 'v21': {'bytes': 41596,
                                                         'mode': '100644',
                                                         'sha256': 'ae430e5cbcbc18fb411c7dd0252ade1b67741718371f59a4a6543cde24ac8074'},
                                                 'v22': {'bytes': 42236,
                                                         'mode': '100644',
                                                         'sha256': '1cb446c35ad860538dd4fce3c1e441bc3a9b9c45ca144ae559597d47b0d57079'}},
 'windows/facility_studio/cli.py': {'reason': 'Reviewed load-only electrical safety gate runtime; '
                                              'no automatic sizing authority.',
                                    'v19': {'bytes': 8222,
                                            'mode': '100644',
                                            'sha256': 'a56a4ddf2f7ba3569888863e3cd731918a527b7ed4c1f5a7f60ff3d2673d8cf9'},
                                    'v21': {'bytes': 8222,
                                            'mode': '100644',
                                            'sha256': 'a56a4ddf2f7ba3569888863e3cd731918a527b7ed4c1f5a7f60ff3d2673d8cf9'},
                                    'v22': {'bytes': 8317,
                                            'mode': '100644',
                                            'sha256': 'ba6f8b842b3dd564bd471ef94ccbc1476a6d89dad8e1f33bf3d8a9ed490da96c'}},
 'windows/facility_studio/desktop.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                  'runtime; no automatic sizing authority.',
                                        'v19': {'bytes': 56787,
                                                'mode': '100644',
                                                'sha256': 'c587a18970fec4c123c56b098695e53a7aba727a4c9223698bdaafb88bf8b43f'},
                                        'v21': {'bytes': 56787,
                                                'mode': '100644',
                                                'sha256': 'c587a18970fec4c123c56b098695e53a7aba727a4c9223698bdaafb88bf8b43f'},
                                        'v22': {'bytes': 56862,
                                                'mode': '100644',
                                                'sha256': '4a3779a0a9adb176da2530dca87074f55ff894c2a9a1a54b116a746e0683a26a'}},
 'windows/facility_studio/display_helpers.py': {'reason': 'Reviewed load-only electrical safety '
                                                          'gate runtime; no automatic sizing '
                                                          'authority.',
                                                'v19': {'bytes': 10215,
                                                        'mode': '100644',
                                                        'sha256': '7aeb3068c36ab07a98dda0cc7119ef1dbc3438dc06c323c1915a5507a160ad65'},
                                                'v21': {'bytes': 10215,
                                                        'mode': '100644',
                                                        'sha256': '7aeb3068c36ab07a98dda0cc7119ef1dbc3438dc06c323c1915a5507a160ad65'},
                                                'v22': {'bytes': 9968,
                                                        'mode': '100644',
                                                        'sha256': '4c305c5c36f7547c87074779d14629678e2b0beaf763f5ef43afaf00276cccc5'}},
 'windows/facility_studio/electrical_disclosures.py': {'reason': 'Reviewed load-only electrical '
                                                                 'safety gate runtime; no '
                                                                 'automatic sizing authority.',
                                                       'v19': {'bytes': 2522,
                                                               'mode': '100644',
                                                               'sha256': '801ac3c452d201e0a482efb9182c1e4da073b43d4b51127720cc7fc23b610a51'},
                                                       'v21': {'bytes': 2522,
                                                               'mode': '100644',
                                                               'sha256': '801ac3c452d201e0a482efb9182c1e4da073b43d4b51127720cc7fc23b610a51'},
                                                       'v22': {'bytes': 11347,
                                                               'mode': '100644',
                                                               'sha256': '70f1c915fa35d9efdd515ea43efd1f8e94b26fdb7095672a1255e8681e294da0'}},
 'windows/facility_studio/english_catalog.py': {'reason': 'Reviewed load-only electrical safety '
                                                          'gate runtime; no automatic sizing '
                                                          'authority.',
                                                'v19': {'bytes': 440401,
                                                        'mode': '100644',
                                                        'sha256': '88ec9ae2bd81eb2b102d06a5b104a74f7d751da9c654856d69c255e9b4a1ceb0'},
                                                'v21': {'bytes': 440401,
                                                        'mode': '100644',
                                                        'sha256': '88ec9ae2bd81eb2b102d06a5b104a74f7d751da9c654856d69c255e9b4a1ceb0'},
                                                'v22': {'bytes': 447988,
                                                        'mode': '100644',
                                                        'sha256': '4f27d571a6a3aba004761ca341f12eec13249e7960d557442e7d36fda2c507f0'}},
 'windows/facility_studio/equipment_analysis.py': {'reason': 'Reviewed load-only electrical safety '
                                                             'gate runtime; no automatic sizing '
                                                             'authority.',
                                                   'v19': {'bytes': 30966,
                                                           'mode': '100644',
                                                           'sha256': 'd66775801f23fcdea3e38a5808d0d178f327eae0e880e1162ec01370d2bcde63'},
                                                   'v21': {'bytes': 30966,
                                                           'mode': '100644',
                                                           'sha256': 'd66775801f23fcdea3e38a5808d0d178f327eae0e880e1162ec01370d2bcde63'},
                                                   'v22': {'bytes': 30597,
                                                           'mode': '100644',
                                                           'sha256': '2a7f47a510175c2bb093e05ba2e44f54c696496c87b63ff70eddf10a509a9ccc'}},
 'windows/facility_studio/equipment_io.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                       'runtime; no automatic sizing authority.',
                                             'v19': {'bytes': 22079,
                                                     'mode': '100644',
                                                     'sha256': '5e061df5287bfdecbc4f259647eb17061e008a0340b5d0d6ad47244b3f69ae72'},
                                             'v21': {'bytes': 22079,
                                                     'mode': '100644',
                                                     'sha256': '5e061df5287bfdecbc4f259647eb17061e008a0340b5d0d6ad47244b3f69ae72'},
                                             'v22': {'bytes': 22154,
                                                     'mode': '100644',
                                                     'sha256': '1a09634087be9126939381c36e4a0fe8eea6980e5f057215f38e59e05f75fee9'}},
 'windows/facility_studio/html_report.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                      'runtime; no automatic sizing authority.',
                                            'v19': {'bytes': 11535,
                                                    'mode': '100644',
                                                    'sha256': 'bdc139348330d58d9549bde8b4887f39ea62ccc40cb8db09c50b891b6a5608e0'},
                                            'v21': {'bytes': 11535,
                                                    'mode': '100644',
                                                    'sha256': 'bdc139348330d58d9549bde8b4887f39ea62ccc40cb8db09c50b891b6a5608e0'},
                                            'v22': {'bytes': 11718,
                                                    'mode': '100644',
                                                    'sha256': 'f46815be71dead6d63099811a993c5bae4bc7b599556e29b2df13fbdffa794c4'}},
 'windows/facility_studio/inactive_acceptance.py': {'reason': 'Reviewed existing acceptance '
                                                              'producer/test load-only contract.',
                                                    'v19': {'bytes': 15596,
                                                            'mode': '100644',
                                                            'sha256': '429ba6eebe2fa78a3534845776ac9e26d8a17432cc65730a182c83b42eb80c68'},
                                                    'v21': {'bytes': 15596,
                                                            'mode': '100644',
                                                            'sha256': '429ba6eebe2fa78a3534845776ac9e26d8a17432cc65730a182c83b42eb80c68'},
                                                    'v22': {'bytes': 15730,
                                                            'mode': '100644',
                                                            'sha256': '98d4f99441dd9310704addd22de29dbb01e1c0d1ebbeecda83ee17fa835877ed'}},
 'windows/facility_studio/main_view.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                    'runtime; no automatic sizing authority.',
                                          'v19': {'bytes': 48074,
                                                  'mode': '100644',
                                                  'sha256': '46df4a073a73b95192af11173bc9a7202dfaf5c07a8fd59e3b194c6770590ad1'},
                                          'v21': {'bytes': 48074,
                                                  'mode': '100644',
                                                  'sha256': '46df4a073a73b95192af11173bc9a7202dfaf5c07a8fd59e3b194c6770590ad1'},
                                          'v22': {'bytes': 47991,
                                                  'mode': '100644',
                                                  'sha256': '6cf637419158293020b7be96b0a53027a6c0d5b3335b7b4347795835083518f4'}},
 'windows/facility_studio/quality.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                  'runtime; no automatic sizing authority.',
                                        'v19': {'bytes': 23060,
                                                'mode': '100644',
                                                'sha256': 'cd757f38ca0a5b19c0e3e731cfc9dfe643a60b2a9a725a8511ee24700033433b'},
                                        'v21': {'bytes': 23060,
                                                'mode': '100644',
                                                'sha256': 'cd757f38ca0a5b19c0e3e731cfc9dfe643a60b2a9a725a8511ee24700033433b'},
                                        'v22': {'bytes': 23122,
                                                'mode': '100644',
                                                'sha256': '7664f0960014daf531e3374c7244683d6e6fd9dd8f8c1a2d25f3650b2577724f'}},
 'windows/facility_studio/quick_tools.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                      'runtime; no automatic sizing authority.',
                                            'v19': {'bytes': 13482,
                                                    'mode': '100644',
                                                    'sha256': '28d1738746d48bd8570e21eb2838b9b0ca57d8b1224d22d911fe74e68b005b0e'},
                                            'v21': {'bytes': 13482,
                                                    'mode': '100644',
                                                    'sha256': '28d1738746d48bd8570e21eb2838b9b0ca57d8b1224d22d911fe74e68b005b0e'},
                                            'v22': {'bytes': 13490,
                                                    'mode': '100644',
                                                    'sha256': 'ae127c8e39a3bb823ebcc34979026cca430c10616e0680f4a7209e9fa0719d16'}},
 'windows/facility_studio/reports.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                  'runtime; no automatic sizing authority.',
                                        'v19': {'bytes': 56419,
                                                'mode': '100644',
                                                'sha256': '57c26b21b13a2b35606326fa05942d367c8aca871143f1e0bf4de3f54dbf894a'},
                                        'v21': {'bytes': 56419,
                                                'mode': '100644',
                                                'sha256': '57c26b21b13a2b35606326fa05942d367c8aca871143f1e0bf4de3f54dbf894a'},
                                        'v22': {'bytes': 55450,
                                                'mode': '100644',
                                                'sha256': 'bd223edea7f62686e33ee804b1fbe72fc54009936cefb62566b0f9cd732c6453'}},
 'windows/facility_studio/resources/Equipment_Template.xlsx': {'reason': 'Reviewed current '
                                                                         'tutorial/resource '
                                                                         'instructions and '
                                                                         'generated archive.',
                                                               'v19': {'bytes': 131243,
                                                                       'mode': '100644',
                                                                       'sha256': '9d629e2f18248f9050e31a231b9184991884b3e992dda5835298f4dd2449df28'},
                                                               'v21': {'bytes': 131243,
                                                                       'mode': '100644',
                                                                       'sha256': '9d629e2f18248f9050e31a231b9184991884b3e992dda5835298f4dd2449df28'},
                                                               'v22': {'bytes': 131291,
                                                                       'mode': '100644',
                                                                       'sha256': 'd2ef56ec750077a7fb2525418daa656ca2e7c1cef298bb4caf4f745efc010035'}},
 'windows/facility_studio/resources/beginner_tutorial.zip': {'reason': 'Reviewed current '
                                                                       'tutorial/resource '
                                                                       'instructions and generated '
                                                                       'archive.',
                                                             'v19': {'bytes': 90109,
                                                                     'mode': '100644',
                                                                     'sha256': 'd9028e716b682dc91621a58b1ddb72ccf3db2a0aece9cbe4dfa9997240c9e7b3'},
                                                             'v21': {'bytes': 98475,
                                                                     'mode': '100644',
                                                                     'sha256': '3173d272541e8befc49a9118eeef1d28a854719df1b085dd14bbf99c3620e3b3'},
                                                             'v22': {'bytes': 101170,
                                                                     'mode': '100644',
                                                                     'sha256': 'ad0dd20e792baaefd976c968335fd1990f1c6b6dd722e96576f125271d346171'}},
 'windows/facility_studio/simple_engines.py': {'reason': 'Reviewed load-only electrical safety '
                                                         'gate runtime; no automatic sizing '
                                                         'authority.',
                                               'v19': {'bytes': 48755,
                                                       'mode': '100644',
                                                       'sha256': 'fcd91aec093de2051895be789b2f96d54fa7057e5d4fd5009a136cc87d883d35'},
                                               'v21': {'bytes': 48755,
                                                       'mode': '100644',
                                                       'sha256': 'fcd91aec093de2051895be789b2f96d54fa7057e5d4fd5009a136cc87d883d35'},
                                               'v22': {'bytes': 48984,
                                                       'mode': '100644',
                                                       'sha256': 'd85e7821ef75a4c545cc567228e4a99971fafe8c984e9fb3d48ee527eb966ea0'}},
 'windows/facility_studio/simple_reports.py': {'reason': 'Reviewed load-only electrical safety '
                                                         'gate runtime; no automatic sizing '
                                                         'authority.',
                                               'v19': {'bytes': 27987,
                                                       'mode': '100644',
                                                       'sha256': 'a932c5efa69f2c2dd8410222222720124078f8be3ce163097768662ff60ba6db'},
                                               'v21': {'bytes': 27987,
                                                       'mode': '100644',
                                                       'sha256': 'a932c5efa69f2c2dd8410222222720124078f8be3ce163097768662ff60ba6db'},
                                               'v22': {'bytes': 25463,
                                                       'mode': '100644',
                                                       'sha256': '87da65138f43cd4ccaa0b67ade463454e3c78d141ecbad882bfcd016654a9a2d'}},
 'windows/facility_studio/simple_schema.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                        'runtime; no automatic sizing authority.',
                                              'v19': {'bytes': 29977,
                                                      'mode': '100644',
                                                      'sha256': '4764f3f35871dc896eef23caf5ba8d604d1ae6c1e82dda72264436e7300d8906'},
                                              'v21': {'bytes': 29977,
                                                      'mode': '100644',
                                                      'sha256': '4764f3f35871dc896eef23caf5ba8d604d1ae6c1e82dda72264436e7300d8906'},
                                              'v22': {'bytes': 30127,
                                                      'mode': '100644',
                                                      'sha256': '2fd447d58cb53ce2acdd658be444cb382006a66f4f82c421384844af20deb6da'}},
 'windows/facility_studio/template_language.py': {'reason': 'Reviewed load-only electrical safety '
                                                            'gate runtime; no automatic sizing '
                                                            'authority.',
                                                  'v19': {'bytes': 2550,
                                                          'mode': '100644',
                                                          'sha256': 'f7177bad498059d1fef7bf5cc9038d0b117e595bd730e19fb6e1a74980efd6e5'},
                                                  'v21': {'bytes': 2550,
                                                          'mode': '100644',
                                                          'sha256': 'f7177bad498059d1fef7bf5cc9038d0b117e595bd730e19fb6e1a74980efd6e5'},
                                                  'v22': {'bytes': 3382,
                                                          'mode': '100644',
                                                          'sha256': '69c64da70c1086731e5a587ea77e804ab8497ccd921edd015c4895752548e3fe'}},
 'windows/facility_studio/tools_view.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                     'runtime; no automatic sizing authority.',
                                           'v19': {'bytes': 33383,
                                                   'mode': '100644',
                                                   'sha256': '9100a33d1a78f74a45d0ef931f1b2e4d6024b17f6b7d049cf2319c76070eb3fd'},
                                           'v21': {'bytes': 33383,
                                                   'mode': '100644',
                                                   'sha256': '9100a33d1a78f74a45d0ef931f1b2e4d6024b17f6b7d049cf2319c76070eb3fd'},
                                           'v22': {'bytes': 34637,
                                                   'mode': '100644',
                                                   'sha256': '6bfe1acc7ddab1321447a5ae97744d16a79b91fc4c06f87ac3b6fd2372ab7610'}},
 'windows/facility_studio/tutorial_help.py': {'reason': 'Historical v19-to-v21 tutorial helper, '
                                                        'previously excepted; unchanged in v22 and '
                                                        'now pinned.',
                                              'v19': {'bytes': 3033,
                                                      'mode': '100644',
                                                      'sha256': '4d235b82247e0e4610433d62b686415a6c8b556e4bcd9047d0ad4cd0556b7478'},
                                              'v21': {'bytes': 5526,
                                                      'mode': '100644',
                                                      'sha256': '90d8e34eac952c0106e80e73ad4ce42ebad5357c30ad8cb168188ed02d7f387e'},
                                              'v22': {'bytes': 5526,
                                                      'mode': '100644',
                                                      'sha256': '90d8e34eac952c0106e80e73ad4ce42ebad5357c30ad8cb168188ed02d7f387e'}},
 'windows/facility_studio/utils.py': {'reason': 'Reviewed load-only electrical safety gate '
                                                'runtime; no automatic sizing authority.',
                                      'v19': {'bytes': 34192,
                                              'mode': '100644',
                                              'sha256': '8ecee6b63599c0130c35544d60aed4e689e7b503659d6bdca1929e357bbfcb91'},
                                      'v21': {'bytes': 34192,
                                              'mode': '100644',
                                              'sha256': '8ecee6b63599c0130c35544d60aed4e689e7b503659d6bdca1929e357bbfcb91'},
                                      'v22': {'bytes': 34500,
                                              'mode': '100644',
                                              'sha256': 'd62fad05ee68cac844ba43275872fdb485af87269565840b80b1787d553bf981'}},
 'windows/facility_studio/workflow_acceptance.py': {'reason': 'Reviewed existing acceptance '
                                                              'producer/test load-only contract.',
                                                    'v19': {'bytes': 13181,
                                                            'mode': '100644',
                                                            'sha256': '9ba601a9f0a45214cf97a009e4c58c2f92d847e30261f6397da3cd722d7af428'},
                                                    'v21': {'bytes': 13181,
                                                            'mode': '100644',
                                                            'sha256': '9ba601a9f0a45214cf97a009e4c58c2f92d847e30261f6397da3cd722d7af428'},
                                                    'v22': {'bytes': 13359,
                                                            'mode': '100644',
                                                            'sha256': '50bdabc77ecd256e60a6e6cdea660b7283a430c35910ab667d2ac7b32bad2f16'}},
 'windows/installer/payload/facility_studio/resources/Equipment_Template.xlsx': {'reason': 'Reviewed '
                                                                                           'current '
                                                                                           'tutorial/resource '
                                                                                           'instructions '
                                                                                           'and '
                                                                                           'generated '
                                                                                           'archive.',
                                                                                 'v19': {'bytes': 72948,
                                                                                         'mode': '100644',
                                                                                         'sha256': '25160dc5f699ac73851bc4137309f6426b11c75c5b7c6b2927da750fab96d2ed'},
                                                                                 'v21': {'bytes': 72948,
                                                                                         'mode': '100644',
                                                                                         'sha256': '25160dc5f699ac73851bc4137309f6426b11c75c5b7c6b2927da750fab96d2ed'},
                                                                                 'v22': {'bytes': 72895,
                                                                                         'mode': '100644',
                                                                                         'sha256': 'e04fe6eeaaac7d6df001697ba97dbc597c93648eef7ac7d15cd780065cb9924a'}},
 'windows/tests/electrical_units.py': {'reason': 'Reviewed existing acceptance producer/test '
                                                 'load-only contract.',
                                       'v19': {'bytes': 15947,
                                               'mode': '100644',
                                               'sha256': '73d016fb987082eeb65989a033063f7987d25c15bfce450bd0536846abac484b'},
                                       'v21': {'bytes': 15947,
                                               'mode': '100644',
                                               'sha256': '73d016fb987082eeb65989a033063f7987d25c15bfce450bd0536846abac484b'},
                                       'v22': {'bytes': 16030,
                                               'mode': '100644',
                                               'sha256': '3a10aae5bf830cecfcabfce616dff8974b65b46187398f0e41d85b9475cfbdca'}},
 'windows/tests/feed_stress/stress_f.py': {'reason': 'Reviewed existing acceptance producer/test '
                                                     'load-only contract.',
                                           'v19': {'bytes': 6735,
                                                   'mode': '100644',
                                                   'sha256': 'e52e0d8eb6f31495769732c816ba3f88949ae53fd30e2752ac2a6ae40c687f0d'},
                                           'v21': {'bytes': 6735,
                                                   'mode': '100644',
                                                   'sha256': 'e52e0d8eb6f31495769732c816ba3f88949ae53fd30e2752ac2a6ae40c687f0d'},
                                           'v22': {'bytes': 6653,
                                                   'mode': '100644',
                                                   'sha256': 'a447db091b29f050f4a4401f5c6e5fc1021953427778f5183c4b1f4fcb502587'}},
 'windows/tests/independent.py': {'reason': 'Reviewed existing acceptance producer/test load-only '
                                            'contract.',
                                  'v19': {'bytes': 8309,
                                          'mode': '100644',
                                          'sha256': 'bd76feaa7818fee65881b2ffd1287102c14e6339df0599af7f95fd8f3cd2d9bc'},
                                  'v21': {'bytes': 8309,
                                          'mode': '100644',
                                          'sha256': 'bd76feaa7818fee65881b2ffd1287102c14e6339df0599af7f95fd8f3cd2d9bc'},
                                  'v22': {'bytes': 6067,
                                          'mode': '100644',
                                          'sha256': '2cd7e322f59c8463590d442a0ea75aeea70755db15f9342ab11a07f0db2cfd72'}},
 'windows/tests/regression.py': {'reason': 'Reviewed existing acceptance producer/test load-only '
                                           'contract.',
                                 'v19': {'bytes': 1751,
                                         'mode': '100644',
                                         'sha256': '525bed8dce04e90de2dfdc3a74ffb834562120447c9608c82308301aa1ab6850'},
                                 'v21': {'bytes': 1751,
                                         'mode': '100644',
                                         'sha256': '525bed8dce04e90de2dfdc3a74ffb834562120447c9608c82308301aa1ab6850'},
                                 'v22': {'bytes': 1751,
                                         'mode': '100644',
                                         'sha256': '8fca70172fb8d7af96ecabc87acfcff5fc40f0a65fbce7b267406ccab689b8f5'}},
 'windows/tests/simple_features.py': {'reason': 'Reviewed existing acceptance producer/test '
                                                'load-only contract.',
                                      'v19': {'bytes': 14522,
                                              'mode': '100644',
                                              'sha256': 'c74fc79cb3d5fe085eb841925f70e84bea5325c7a0bae7548227ed6e15b30556'},
                                      'v21': {'bytes': 14522,
                                              'mode': '100644',
                                              'sha256': 'c74fc79cb3d5fe085eb841925f70e84bea5325c7a0bae7548227ed6e15b30556'},
                                      'v22': {'bytes': 14213,
                                              'mode': '100644',
                                              'sha256': '7330f5aaf39ed7c860e47d65d56f67dd2cd6874bc39d791d870d1122f6d165bb'}},
 'windows/tests/simple_gui.py': {'reason': 'Reviewed existing acceptance producer/test load-only '
                                           'contract.',
                                 'v19': {'bytes': 10858,
                                         'mode': '100644',
                                         'sha256': 'd23fc39643f10215223fc714fd1cf76c7bd8ef2dc68790246993d49310656db3'},
                                 'v21': {'bytes': 10858,
                                         'mode': '100644',
                                         'sha256': 'd23fc39643f10215223fc714fd1cf76c7bd8ef2dc68790246993d49310656db3'},
                                 'v22': {'bytes': 11058,
                                         'mode': '100644',
                                         'sha256': '82e68bebb4ae02029c8dd0451ffa3b27bbe97e5f25cad5405ab84e726f9c409f'}},
 'windows/tests/v554_features.py': {'reason': 'Reviewed existing acceptance producer/test '
                                              'load-only contract.',
                                    'v19': {'bytes': 22155,
                                            'mode': '100644',
                                            'sha256': 'c6896e008988a1b5bab5ca4bdb77e82eeab589012c678247cee89cea7704d8c5'},
                                    'v21': {'bytes': 22155,
                                            'mode': '100644',
                                            'sha256': 'c6896e008988a1b5bab5ca4bdb77e82eeab589012c678247cee89cea7704d8c5'},
                                    'v22': {'bytes': 21987,
                                            'mode': '100644',
                                            'sha256': 'ea0cff5aff0b4a72f0c2ca489448d8eb08d2a6e0badfcce9421a8fd5beecf1c7'}}}

REVIEWED_V22_DOCUMENT_INDEX_TRANSITIONS = {'docs/images/README.md': {'reason': 'Current image-index disclaimer only; actual historical '
                                     'images, reports and evidence remain immutable.',
                           'v19': {'bytes': 9146,
                                   'mode': '100644',
                                   'sha256': 'ef507026fb1f3ad29a89f63fc7a8e9229e447bf759af37c76e02302e6b99d6e6'},
                           'v21': {'bytes': 9146,
                                   'mode': '100644',
                                   'sha256': 'ef507026fb1f3ad29a89f63fc7a8e9229e447bf759af37c76e02302e6b99d6e6'},
                           'v22': {'bytes': 9629,
                                   'mode': '100644',
                                   'sha256': '356cbd4451afc4a2053ff840add1f91cddc2555357e107f85dae4e204dc930bf'}}}


# Explicit reviewed successors for the Windows portable release. Original v19/v22
# identities remain frozen; no other product byte or path is exempted.
REVIEWED_WINDOWS_PORTABLE_R1 = {'windows/facility_studio/english_catalog.py': {'reason': 'Windows-only exact application-owned worksheet '
                                                          'title catalog translation to Instructions; '
                                                          'exporter and all electrical restrictions '
                                                          'unchanged.',
                                                'v22': {'bytes': 447988,
                                                        'mode': '100644',
                                                        'sha256': '4f27d571a6a3aba004761ca341f12eec13249e7960d557442e7d36fda2c507f0'},
                                                'windows_portable_r1': {'bytes': 448014,
                                                                        'mode': '100644',
                                                                        'sha256': 'c9b1d7a222e3e867afe19f55b8933f37e1a44b1e1faec495d3aaf7f795fa7ec5'}},
 'windows/facility_studio/feed_review_preview.py': {'reason': 'Windows-only fresh dialog work-area sizing; '
                                                              'settings footer reservation. No engineering '
                                                              'calculation changes.',
                                                    'v22': {'bytes': 17488,
                                                            'mode': '100644',
                                                            'sha256': '29762b1396ec27ff31c184e4a5dc7bb980b65f1c8cdd698de78bc72c40557172'},
                                                    'windows_portable_r1': {'bytes': 17658,
                                                                            'mode': '100644',
                                                                            'sha256': '55755cddc6c5068f2ea1e6df378aacf180e6bf13b81bd7d80a8026eca36f3386'}},
 'windows/facility_studio/fusion_settings.py': {'reason': 'Windows-only fresh dialog work-area sizing; '
                                                          'settings footer reservation. No engineering '
                                                          'calculation changes.',
                                                'v22': {'bytes': 9234,
                                                        'mode': '100644',
                                                        'sha256': 'c95f24261600e7886a5c047dfb3fae5686de409fce15f838901f627cf2539d45'},
                                                'windows_portable_r1': {'bytes': 9602,
                                                                        'mode': '100644',
                                                                        'sha256': 'a175bcc15ac656b7417bf2a80421f7340866092e6a076df4652ff980f0b5469d'}},
 'windows/facility_studio/window_geometry.py': {'reason': 'Windows-only first-map placement including '
                                                          'OS-derived upcoming native menu frame; no later '
                                                          'repositioning, calculation or macOS changes.',
                                                'v22': {'bytes': 4686,
                                                        'mode': '100644',
                                                        'sha256': 'd670cd4ed349b417233985d945914c0202db29568c6cadc99218eaf8c0ba8c73'},
                                                'windows_portable_r1': {'bytes': 10322,
                                                                        'mode': '100644',
                                                                        'sha256': 'dba6710d8b14e0bc3135b59626c0577b164f697602b286e21d75d1d8786a55a5'}},
 'windows/facility_studio/simple_desktop.py': {'reason': 'Windows-only native menu installation before first '
                                                         'layout/map; no calculation or macOS changes.',
                                               'v22': {'bytes': 59334,
                                                       'mode': '100644',
                                                       'sha256': '5b7a50c30afca9a5b33ebd47da345b6ca0f4c54c3dc4b4a3a8d75b511acacdcc'},
                                               'windows_portable_r1': {'bytes': 59481,
                                                                       'mode': '100644',
                                                                       'sha256': 'ae3febe265b42d72d37e40897ecf418f4de49458334b90b411b413a532e63a75'}},
 'windows/facility_studio/desktop.py': {'reason': 'Windows-only authored menu localization and bounded '
                                                  'bilingual selector fit; original engineering enums, '
                                                  'equations, startup ordering and macOS unchanged.',
                                        'v22': {'bytes': 56862,
                                                'mode': '100644',
                                                'sha256': '4a3779a0a9adb176da2530dca87074f55ff894c2a9a1a54b116a746e0683a26a'},
                                        'windows_portable_r1': {'bytes': 57135,
                                                                'mode': '100644',
                                                                'sha256': 'b81a43b35a56acb6ac4c0afd3831a86b0e71f589f6b563057a3e2b9056033f5f'}},
 'windows/facility_studio/sandbox_ui.py': {'reason': 'Windows-only authored menu localization and bounded '
                                                     'bilingual selector fit; original engineering enums, '
                                                     'equations, startup ordering and macOS unchanged.',
                                           'v22': {'bytes': 5581,
                                                   'mode': '100644',
                                                   'sha256': 'c49f3fe2239dae431bff94837cf2a1afb335206f347becd18b5a9237e327e072'},
                                           'windows_portable_r1': {'bytes': 7077,
                                                                   'mode': '100644',
                                                                   'sha256': '57d264bd3b8118e9dca3ee7213399f7633bf581f451a1b48bee329cca566368f'}}}

def assert_reviewed_product_bytes(relative):
    portable = REVIEWED_WINDOWS_PORTABLE_R1.get(relative)
    if portable is not None:
        original = BASELINE_FILES[relative]
        prior = REVIEWED_V22_PRODUCT_TRANSITIONS.get(relative)
        if prior is not None:
            assert {key: original[key] for key in ("sha256", "bytes", "mode")} == prior["v19"], (
                "Reviewed immutable v19 predecessor changed: " + relative)
            assert prior["v22"] == portable["v22"], "Reviewed immutable v22 predecessor changed: " + relative
        else:
            assert {key: original[key] for key in ("sha256", "bytes", "mode")} == portable["v22"], (
                "Reviewed immutable predecessor changed: " + relative)
        expected = portable["windows_portable_r1"]
        path = ROOT / relative
        assert path.is_file(), "Reviewed portable repair path missing: " + relative
        body = path.read_bytes()
        assert len(body) == expected["bytes"] and hashlib.sha256(body).hexdigest() == expected["sha256"], (
            "Reviewed Windows portable repair bytes changed: " + relative)
        assert source_mode(path, relative, body) == expected["mode"], "Reviewed portable mode changed: " + relative
        return
    transition = REVIEWED_V22_PRODUCT_TRANSITIONS.get(relative)
    if transition is None:
        transition = REVIEWED_V22_DOCUMENT_INDEX_TRANSITIONS.get(relative)
    endpoint = "v22"
    if transition is None:
        transition = REVIEWED_V21_TK_REPAIRS.get(relative)
        endpoint = "v21"
    if transition is None:
        assert_original_bytes(relative)
        return
    original = BASELINE_FILES[relative]
    assert {key: original[key] for key in ("sha256", "bytes", "mode")} == transition[
        "v19"
    ], f"Reviewed v19 predecessor changed: {relative}"
    expected = transition[endpoint]
    path = ROOT / relative
    assert path.is_file(), f"Reviewed repair path missing: {relative}"
    body = path.read_bytes()
    assert (
        len(body) == expected["bytes"]
        and hashlib.sha256(body).hexdigest() == expected["sha256"]
    ), f"Reviewed {endpoint} repair bytes changed: {relative}"
    mode = source_mode(path, relative, body)
    assert mode == expected["mode"], f"Reviewed repair mode changed: {relative}"


def test_frozen_baseline_manifest_has_exact_sealed_identity():
    payload = "".join(
        f"{BASELINE_FILES[k]['sha256']}  {k}\n" for k in sorted(BASELINE_FILES)
    ).encode()
    assert len(BASELINE_FILES) == 1346
    assert (
        hashlib.sha256(payload).hexdigest()
        == "9ce92d4e4ea83383cffd173e74dcc6454efabd1f3c51db441c5f44c862d722b5"
    )


def assert_exact_product_path_inventory(platform):
    old = {name for name in BASELINE_FILES if name.startswith(platform + "/")}
    new = {
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / platform).rglob("*")
        if p.is_file()
    }
    assert new == old, f"Unexpected product path additions/removals: {new ^ old}"


def test_all_product_files_match_exact_reviewed_successors():
    assert not (set(REVIEWED_V21_TK_REPAIRS) & set(REVIEWED_V22_PRODUCT_TRANSITIONS))
    assert set(REVIEWED_V22_PRODUCT_TRANSITIONS) <= set(BASELINE_FILES)
    assert set(REVIEWED_WINDOWS_PORTABLE_R1) <= set(BASELINE_FILES)
    assert not (set(REVIEWED_WINDOWS_PORTABLE_R1) & set(REVIEWED_V21_TK_REPAIRS))
    assert set(REVIEWED_WINDOWS_PORTABLE_R1) & set(REVIEWED_V22_PRODUCT_TRANSITIONS) == {
        "windows/facility_studio/english_catalog.py", "windows/facility_studio/desktop.py"}
    for platform in ("macos", "windows"):
        old = {name for name in BASELINE_FILES if name.startswith(platform + "/")}
        for relative in old:
            assert_reviewed_product_bytes(relative)
        assert_exact_product_path_inventory(platform)


@pytest.mark.parametrize("relative", sorted(set(REVIEWED_V21_TK_REPAIRS) | set(REVIEWED_V22_PRODUCT_TRANSITIONS) | set(REVIEWED_V22_DOCUMENT_INDEX_TRANSITIONS) | set(REVIEWED_WINDOWS_PORTABLE_R1)))
def test_each_reviewed_endpoint_rejects_one_wrong_byte(tmp_path, monkeypatch, relative):
    assert_reviewed_product_bytes(relative)
    body = (ROOT / relative).read_bytes()
    assert body
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(bytes([body[0] ^ 1]) + body[1:])
    path.chmod((ROOT / relative).stat().st_mode & 0o777)
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="Reviewed .* repair bytes changed"):
        assert_reviewed_product_bytes(relative)


def test_unrelated_product_byte_remains_immutable(tmp_path, monkeypatch):
    relative = "macos/facility_studio/version.py"
    assert relative not in REVIEWED_V21_TK_REPAIRS
    assert relative not in REVIEWED_V22_PRODUCT_TRANSITIONS
    assert_reviewed_product_bytes(relative)
    body = (ROOT / relative).read_bytes()
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(bytes([body[0] ^ 1]) + body[1:])
    path.chmod((ROOT / relative).stat().st_mode & 0o777)
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="Original bytes changed"):
        assert_reviewed_product_bytes(relative)


def test_product_path_inventory_rejects_unexpected_addition(tmp_path, monkeypatch):
    # Recreate only names for this path-inventory control, never approve bytes.
    platform = "macos"
    for relative in BASELINE_FILES:
        if relative.startswith(platform + "/"):
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"")
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    assert_exact_product_path_inventory(platform)
    (tmp_path / platform / "UNREVIEWED_PRODUCT_FILE.py").write_bytes(b"sentinel")
    with pytest.raises(AssertionError, match="Unexpected product path additions/removals"):
        assert_exact_product_path_inventory(platform)


def test_historical_evidence_and_legacy_assets_preserved():
    explicit = [
        "docs/tutorial/Facility_Studio_Beginner_Tutorial.zip",
        "docs/tutorial/verification-windows.json",
        "docs/tutorial/verification-macos.json",
        "docs/tutorial/native-delivery-verification.json",
        "docs/tutorial/workbench-map.svg",
        "docs/tutorial/workbench-map.en.svg",
    ]
    paths = explicit + [
        p
        for p in BASELINE_FILES
        if p.startswith(("docs/verification/", "docs/images/", "docs/evidence/"))
    ]
    assert set(REVIEWED_V22_DOCUMENT_INDEX_TRANSITIONS) == {"docs/images/README.md"}
    for relative in paths:
        if relative == "docs/images/README.md":
            assert_reviewed_product_bytes(relative)
        else:
            assert_original_bytes(relative)


@pytest.mark.parametrize(
    "bad_member",
    [
        "../escape.txt",
        "/tmp/escape.txt",
        "folder/../../escape.txt",
        "bad\\escape.txt",
        "START_HERE.html",
    ],
)
def test_tutorial_extractor_rejects_malicious_and_duplicate_members(
    tmp_path, monkeypatch, bad_member
):
    """Mock only resource location. Real extraction code is executed."""
    fake_package = tmp_path / "package"
    (fake_package / "resources").mkdir(parents=True)
    archive = fake_package / "resources/beginner_tutorial.zip"
    with (
        zipfile.ZipFile(
            ROOT / PLATFORM / "facility_studio/resources/beginner_tutorial.zip"
        ) as original,
        zipfile.ZipFile(archive, "w") as mutant,
    ):
        for entry in original.infolist():
            mutant.writestr(entry, original.read(entry))
        mutant.writestr(bad_member, "malicious sentinel")
    monkeypatch.setattr(
        tutorial_help, "__file__", str(fake_package / "tutorial_help.py")
    )
    destination = tmp_path / "dest"
    with pytest.raises(ValueError, match="unexpected|duplicate|unsafe|member|files"):
        tutorial_help.prepare_tutorial(destination)
    assert not (tmp_path / "escape.txt").exists()
    assert not list(destination.rglob("START_HERE.html")), (
        "Must reject before partial extraction"
    )


def test_changed_bundle_uses_new_cache_even_at_same_product_version(tmp_path):
    """Create a real v19 cache and invoke current extraction, without a browser."""
    from facility_studio.version import VERSION

    old_zip = (
        Path(__file__).with_name("independent_tutorial_resources")
        / f"v19-beginner-tutorial-{PLATFORM}.zip"
    )
    body = old_zip.read_bytes()
    original = BASELINE_FILES[
        f"{PLATFORM}/facility_studio/resources/beginner_tutorial.zip"
    ]
    assert hashlib.sha256(body).hexdigest() == original["sha256"]
    destination = tmp_path / "Tutorial"
    old_folder = destination / (
        "V" + VERSION.replace(".", "_") + "_" + hashlib.sha256(body).hexdigest()[:16]
    )
    old_folder.mkdir(parents=True)
    with zipfile.ZipFile(old_zip) as z:
        for entry in z.infolist():
            assert PurePosixPath(entry.filename).name == entry.filename
            (old_folder / entry.filename).write_bytes(z.read(entry))
    practice = old_folder / "01_Practice_AHU.json"
    practice.write_text('{"user": "keep my old practice"}')
    old_html = (old_folder / "START_HERE.html").read_bytes()
    old_report = (old_folder / "01_Expected_Report.txt").read_bytes()
    new_folder = tutorial_help.prepare_tutorial(destination)
    assert new_folder != old_folder
    assert new_folder.name.startswith("V" + VERSION.replace(".", "_") + "_")
    assert (new_folder / "START_HERE.html").read_bytes() != old_html
    assert (new_folder / "01_Expected_Report.txt").read_bytes() != old_report
    assert practice.read_text() == '{"user": "keep my old practice"}'
    assert (old_folder / "START_HERE.html").read_bytes() == old_html
    with zipfile.ZipFile(
        ROOT / PLATFORM / "facility_studio/resources/beginner_tutorial.zip"
    ) as z:
        for name in z.namelist():
            assert (new_folder / name).read_bytes() == z.read(name)


@pytest.mark.parametrize(
    "name",
    [
        "START_HERE.html",
        "01_Expected_Report.txt",
        "synthetic-constant-1000cd.ies",
        "2026-11-07-lighting-input-basis.md",
    ],
)
def test_changed_or_missing_cached_readonly_asset_is_not_silently_used(tmp_path, name):
    folder = tutorial_help.prepare_tutorial(tmp_path)
    target = folder / name
    expected = target.read_bytes()
    original_edit = b"INDEPENDENT_AUDIT_USER_ANNOTATED_ASSET"
    target.write_bytes(original_edit)
    try:
        returned = tutorial_help.prepare_tutorial(tmp_path)
    except ValueError:
        # Rejection is permitted: preserve possible user annotations.
        assert target.read_bytes() == original_edit
    else:
        assert returned == folder
        assert target.read_bytes() == expected, (
            "Existing tampered read-only asset was silently retained"
        )
        assert any(
            p.is_file() and p != target and p.read_bytes() == original_edit
            for p in tmp_path.rglob("*")
        ), "Restoration discarded user annotations without retaining old bytes"
    target.unlink()
    returned = tutorial_help.prepare_tutorial(tmp_path)
    assert returned == folder and target.read_bytes() == expected


@pytest.mark.parametrize(
    "name", ["01_Practice_AHU.json", "02_Practice_MAU_and_AHU.json"]
)
def test_existing_user_practice_is_preserved_in_current_cache(tmp_path, name):
    folder = tutorial_help.prepare_tutorial(tmp_path)
    target = folder / name
    target.write_text('{"modified": "user practice"}')
    assert tutorial_help.prepare_tutorial(tmp_path) == folder
    assert target.read_text() == '{"modified": "user practice"}'


@pytest.mark.parametrize("kind", ["symlink", "directory"])
def test_unsafe_cached_target_rejected_without_touching_other_data(tmp_path, kind):
    folder = tutorial_help.prepare_tutorial(tmp_path / "cache")
    target = folder / "START_HERE.html"
    target.unlink()
    victim = tmp_path / "user-data.txt"
    victim.write_bytes(b"preserve unrelated user data")
    if kind == "symlink":
        target.symlink_to(victim)
    else:
        target.mkdir()
    with pytest.raises((ValueError, OSError)):
        tutorial_help.prepare_tutorial(tmp_path / "cache")
    assert victim.read_bytes() == b"preserve unrelated user data"
    assert target.is_symlink() if kind == "symlink" else target.is_dir()


def test_failed_practice_read_does_not_create_empty_user_project(tmp_path, monkeypatch):
    original = zipfile.ZipFile.read

    def failing_read(archive, member, *args, **kwargs):
        name = member.filename if isinstance(member, zipfile.ZipInfo) else member
        if name == "01_Practice_AHU.json":
            raise OSError("independent injected read failure")
        return original(archive, member, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", failing_read)
    with pytest.raises(OSError, match="independent injected read failure"):
        tutorial_help.prepare_tutorial(tmp_path)
    assert not list(tmp_path.rglob("01_Practice_AHU.json")), (
        "Read failure left a partial/empty user practice file"
    )


def test_content_hash_cache_folder_symlink_is_not_followed(tmp_path):
    from facility_studio.version import VERSION

    body = (
        ROOT / PLATFORM / "facility_studio/resources/beginner_tutorial.zip"
    ).read_bytes()
    destination = tmp_path / "cache"
    destination.mkdir()
    folder = destination / (
        "V" + VERSION.replace(".", "_") + "_" + hashlib.sha256(body).hexdigest()[:16]
    )
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    folder.symlink_to(unrelated, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        tutorial_help.prepare_tutorial(destination)
    assert folder.is_symlink()
    assert not list(unrelated.iterdir()), (
        "Generated cache-folder symlink redirected extraction"
    )


def test_extracted_bytes_match_hashed_snapshot_if_resource_changes(
    tmp_path, monkeypatch
):
    import io

    original_content = (
        ROOT / PLATFORM / "facility_studio/resources/beginner_tutorial.zip"
    ).read_bytes()
    replacement = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(original_content)) as old,
        zipfile.ZipFile(replacement, "w") as new,
    ):
        for entry in old.infolist():
            body = old.read(entry)
            if entry.filename == "READ_ME_FIRST.txt":
                body = b"INDEPENDENT RESOURCE CHANGED AFTER SNAPSHOT\n"
            new.writestr(entry, body)
    package = tmp_path / "package"
    (package / "resources").mkdir(parents=True)
    resource = package / "resources/beginner_tutorial.zip"
    resource.write_bytes(original_content)
    monkeypatch.setattr(tutorial_help, "__file__", str(package / "tutorial_help.py"))
    original_read = Path.read_bytes
    swapped = []

    def read_then_swap(path):
        body = original_read(path)
        if path == resource and not swapped:
            swapped.append(True)
            resource.write_bytes(replacement.getvalue())
        return body

    monkeypatch.setattr(Path, "read_bytes", read_then_swap)
    folder = tutorial_help.prepare_tutorial(tmp_path / "cache")
    assert swapped
    assert folder.name.endswith(hashlib.sha256(original_content).hexdigest()[:16])
    with zipfile.ZipFile(io.BytesIO(original_content)) as archive:
        for name in archive.namelist():
            assert (folder / name).read_bytes() == archive.read(name), (
                f"Extracted different bytes under original hash: {name}"
            )


@pytest.mark.parametrize("name", ["START_HERE.html", "01_Practice_AHU.json"])
def test_caught_partial_write_failure_cleans_only_new_file(tmp_path, monkeypatch, name):
    """Injected caught OSError, not a power-loss/process-kill simulation."""
    original_open = Path.open
    failures = []

    class FailingWriter:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def write(self, body):
            self.handle.write(body[:17])
            self.handle.flush()
            failures.append(True)
            raise OSError("independent injected partial write")

    def maybe_failing_open(path, mode="r", *args, **kwargs):
        handle = original_open(path, mode, *args, **kwargs)
        if mode == "xb" and path.name == name:
            return FailingWriter(handle)
        return handle

    monkeypatch.setattr(Path, "open", maybe_failing_open)
    with pytest.raises(OSError, match="independent injected partial write"):
        tutorial_help.prepare_tutorial(tmp_path)
    assert failures
    assert not list(tmp_path.rglob(name)), (
        "Caught write failure left a partial newly-created file"
    )
    monkeypatch.setattr(Path, "open", original_open)
    folder = tutorial_help.prepare_tutorial(tmp_path)
    with zipfile.ZipFile(
        ROOT / PLATFORM / "facility_studio/resources/beginner_tutorial.zip"
    ) as z:
        assert (folder / name).read_bytes() == z.read(name)


@pytest.mark.parametrize("language", ["zh-Hant", "en"])
def test_rejected_cache_error_preserves_exact_path_in_each_language(
    tmp_path, monkeypatch, language
):
    """Real cache rejection; only browser/messagebox presentation is mocked."""
    from unittest.mock import Mock

    from facility_studio import i18n, localized_tk

    monkeypatch.setattr(
        tutorial_help, "app_data", lambda: tmp_path / "水量與熱量" / "fluids"
    )
    monkeypatch.setattr(tutorial_help.webbrowser, "open", Mock())
    monkeypatch.setattr(localized_tk.messagebox, "showerror", Mock())
    folder = tutorial_help.prepare_tutorial()
    target = folder / "START_HERE.html"
    target.write_bytes(b"user annotation preserved")
    assert tutorial_help.open_tutorial() is None
    tutorial_help.webbrowser.open.assert_not_called()
    localized_tk.messagebox.showerror.assert_called_once()
    raw_message = localized_tk.messagebox.showerror.call_args.args[1]
    assert str(target) in i18n.translate(raw_message, language), (
        "Error translation changed the actionable recovery path"
    )
    assert target.read_bytes() == b"user annotation preserved"
