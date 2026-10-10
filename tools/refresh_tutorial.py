"""Regenerate current tutorial reports and bundles without replacing practice data."""

import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "windows"))
from facility_studio import i18n
from facility_studio.engine import calculate
from facility_studio.ahu_engine import nm_calculate
from facility_studio.reports import report, nm_report
from facility_studio.tutorial_help import TUTORIAL_FILES
from facility_studio.version import VERSION


def main():
    tutorial = ROOT / "docs/tutorial"
    workspace = json.loads((tutorial / "01_Practice_AHU.json").read_text(encoding="utf-8"))
    second = json.loads((tutorial / "02_Practice_MAU_and_AHU.json").read_text(encoding="utf-8"))
    primary = calculate(workspace["main"])
    ahu = nm_calculate(second["ahus"][0]["inputs"])
    for language, suffix in (("zh-Hant", ""), ("en", ".en")):
        i18n.set_language(language, persist=False)
        for name, text in (("01_Expected_Report", report(primary)), ("02_Expected_AHU_Report", nm_report(ahu))):
            clean = "\n".join(line.rstrip() for line in str(text).splitlines()) + "\n"
            (tutorial / (name + suffix + ".txt")).write_text(clean, encoding="utf-8")
    expected_path = tutorial / "expected-results.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected["app_version"] = VERSION
    expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Preserve the reviewed layout and all existing chapters. Append the short
    # interaction notes, making reruns idempotent with a versioned note marker.
    page_path = tutorial / "START_HERE.html"
    page = page_path.read_text(encoding="utf-8")
    pattern = r'(<script type="application/json" id="tutorial-data">)(.*?)(</script>)'
    match = re.search(pattern, page, re.S)
    if match is None:
        raise ValueError("Tutorial data block missing")
    data = json.loads(match[2])
    notes = {
        "zh-Hant": {
            "electrical": "完整工作台：一般／馬達負載含明列 HP 時才採最大馬達加成，0 未知採總電流 125%；連續負載固定採總電流 125%，停用最大馬達草稿不影響結果。降載依環溫與同管下拉區間；簡易工具採實填環溫／載流線數。",
            "ahu": "停用欄位只保留草稿，不影響計算或報告。非電熱段不使用電熱效率；熱回收未上線不列採用熱水條件；非水洗設備不列水洗泵與補水。名目電力只計選用電熱、蒸汽和 EC 額定，循環泵與附屬設備另核。主案一段模式只用夏季；冬季逐段控制請在單機內設定。",
            "utilities": "閉式水路不把樓高加進循環泵差壓，系統靜壓另核；風管不用水側靜揚程。切換模式保留原草稿，採用值與原因會在畫面／報告說明。",
        },
        "en": {
            "electrical": "Workbench: general/motor loads with listed HP use the largest-motor allowance; 0 means unknown and uses 125% of total current. Continuous loads always use 125%, excluding inactive largest-motor drafts. Derating uses ambient/conductor dropdown ranges; independent tools use entered ambient/count values.",
            "ahu": "Inactive fields retain drafts but do not affect calculations or reports. Non-electric stages ignore electric efficiency. Offline heat recovery omits adopted water conditions; non-wash equipment omits wash-pump and wash-makeup sizing. Rated power sums selected direct heaters, steam generators and EC fans; pumps/auxiliaries require separate confirmation. Main C1 mode applies to summer only; use seasonal AHU controls for winter stages.",
            "utilities": "Closed circulation excludes building height from pump differential pressure; check system static pressure separately. Ducts exclude water-side static lift. Mode changes preserve drafts while the adopted value and reason are shown on screen/in reports.",
        },
    }
    for language, sections in data["content"].items():
        for section in sections:
            if section["id"] in notes[language]:
                marker = '<p data-v557-note="true">'
                section["html"] = re.sub(r'<p data-v557-note="true">.*?</p>', "", section["html"], flags=re.S)
                section["html"] += marker + notes[language][section["id"]] + "</p>\n"
        label = data["labels"][language]
        label["offline"] = ("離線版｜V" if language == "zh-Hant" else "Offline | V") + VERSION + " | Windows / macOS"
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = page[:match.start(2)] + encoded + page[match.end(2):]
    page_path.write_text(page, encoding="utf-8")
    readme = tutorial / "READ_ME_FIRST.txt"
    readme.write_text(re.sub(r"V5\.5\.\d+", "V" + VERSION, readme.read_text(encoding="utf-8")), encoding="utf-8")

    archive_path = tutorial / "Facility_Studio_Beginner_Tutorial.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted(TUTORIAL_FILES):
            path = tutorial / filename
            if not path.exists() and filename.startswith("LICENSE"):
                path = ROOT / filename
            archive.writestr(filename, path.read_bytes())
    content = archive_path.read_bytes()
    for package in ("windows", "macos", "windows/installer/payload"):
        path = ROOT / package / "facility_studio/resources/beginner_tutorial.zip"
        path.write_bytes(content)

    payload_root = ROOT / "windows/installer/payload"
    manifest = {
        path.relative_to(payload_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(payload_root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    (ROOT / "windows/installer/payload_sha256.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Refreshed bilingual reports, offline tutorial and source-payload manifest for V" + VERSION)


if __name__ == "__main__":
    main()
