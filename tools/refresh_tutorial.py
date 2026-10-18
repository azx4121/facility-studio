"""Refresh one platform's tutorial without rewriting other releases."""
import argparse
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "macos"), default="windows")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / args.platform))
    from facility_studio import version
    from facility_studio.engine import calculate
    from facility_studio.ahu_engine import nm_calculate
    from facility_studio.reports import report, nm_report
    from facility_studio.tutorial_help import TUTORIAL_FILES

    tutorial = ROOT / "docs/tutorial"
    references = tutorial / args.platform
    references.mkdir(exist_ok=True)
    first = json.loads((tutorial / "01_Practice_AHU.json").read_text(encoding="utf-8"))
    second = json.loads((tutorial / "02_Practice_MAU_and_AHU.json").read_text(encoding="utf-8"))
    primary, ahu = calculate(first["main"]), nm_calculate(second["ahus"][0]["inputs"])
    overrides = {}
    for language, suffix in (("zh-Hant", ""), ("en", ".en")):
        for name, text in (("01_Expected_Report", report(primary, language=language)),
                           ("02_Expected_AHU_Report", nm_report(ahu, language=language))):
            filename = name + suffix + ".txt"
            body = ("\n".join(line.rstrip() for line in str(text).splitlines()) + "\n").encode("utf-8")
            (references / filename).write_bytes(body)
            overrides[filename] = body

    # Keep all reviewed HTML chapters and practice inputs unchanged. Only this
    # platform's bundled heading and reference-report bytes are replaced.
    page = (tutorial / "START_HERE.html").read_text(encoding="utf-8")
    pattern = r'(<script type="application/json" id="tutorial-data">)(.*?)(</script>)'
    match = re.search(pattern, page, re.S)
    if match is None:
        raise ValueError("Tutorial data block missing")
    data = json.loads(match[2])
    label = getattr(version, "REPORT_VERSION", version.VERSION + " · " + args.platform)
    for language in ("zh-Hant", "en"):
        data["labels"][language]["offline"] = ("離線版｜V" if language == "zh-Hant" else "Offline | V") + label
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    overrides["START_HERE.html"] = (page[:match.start(2)] + encoded + page[match.end(2):]).encode("utf-8")
    suffix = "Windows" if args.platform == "windows" else "macOS"
    archive_path = tutorial / ("Facility_Studio_Beginner_Tutorial_" + suffix + ".zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted(TUTORIAL_FILES):
            path = tutorial / filename
            if not path.exists() and filename.startswith("LICENSE"):
                path = ROOT / filename
            info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, overrides.get(filename, path.read_bytes()))
    (ROOT / args.platform / "facility_studio/resources/beginner_tutorial.zip").write_bytes(archive_path.read_bytes())
    print("Refreshed", args.platform, "reference reports and bundled tutorial:", label)


if __name__ == "__main__":
    main()
