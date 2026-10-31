"""Deliver the validated 5.5.4 files and verify execution from the actual ZIP."""

from pathlib import Path
import base64
import datetime as dt
import hashlib
import html
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

from nsis_integrity import expected_members, verify_setup

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "deliverables_v554"
SETUP = "Facility_Studio_V5_5_4_Setup.exe"
SOURCE = "Facility_Studio_V5_5_4_Source_and_Verification.zip"
BUNDLE = "Facility_Studio_V5_5_4_OneClick.zip"
TEMPLATE = "Facility_Studio_V5_5_4_Equipment_Template.xlsx"


def read(name):
    return json.loads((ROOT / "evidence" / name).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verification():
    specs = [
        ("52組工程情境與報告反算", "Numeric_Checks.json", 1247),
        ("20組既有數值條件", "V55_Feature_Checks.json", 93),
        ("主案／空調箱資料一致性", "V552_Core_Checks.json", 305),
        ("完整工作台視窗", "GUI_V55_Checks.json", 42),
        ("既有修正回歸", "V551_Fix_Checks.json", 31),
        ("完整工作台互鎖與來源", "V552_Interaction_Checks.json", 44),
        ("安裝內容完整性", "Packaging_Checks.json", 15),
        ("NSIS CRC／完整解壓／損壞檔攔截", "Installer_Integrity_Checks.json", 21),
        ("42組簡易工具公式及報告反算", "Simple_Numeric_Checks.json", 375),
        ("簡易工具視窗回歸", "Simple_GUI_Checks.json", 58),
        ("49組新增匯入／報告／線圖情境", "V554_New_Feature_Checks.json", 646),
        ("小數點／照明／線圖／匯入互動", "V554_GUI_Checks.json", 69),
        ("Excel各系統實際改值與公式重算", "Template_Checks.json", 7),
    ]
    suites = []
    for label, filename, expected in specs:
        raw = read(filename)
        records = raw["checks"] if isinstance(raw, dict) else raw
        assert len(records) == expected and all(c["passed"] for c in records), filename
        suites.append(
            dict(name=label, checks=len(records), passed=len(records), file=filename)
        )
    assert read("V554_New_Feature_Checks.json")["scenario_count"] == 49
    assert len(read("GUI_Suite_Execution.json")["suites"]) == 6
    assert all(
        record["passed"] for record in read("GUI_Suite_Execution.json")["suites"]
    )
    manifest = json.loads((ROOT / "installer/payload_sha256.json").read_text())
    integrity = verify_setup(ROOT / SETUP, expected_members(ROOT / "installer"))
    result = dict(
        version="5.5.4",
        assembled_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        python=platform.python_version(),
        test_platform=platform.system(),
        gui="Actual Tk/Xvfb; all desktop suites executed against this release",
        suites=suites,
        total_checks=sum(s["checks"] for s in suites),
        new_scenarios=49,
        new_interaction_checks=69,
        engineering_scenarios=52,
        additional_numeric_conditions=20,
        simple_tool_scenarios=42,
        equipment_systems=["電力", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV"],
        template_sheets=8,
        template_formula_recalculations=7,
        template_native_excel_execution_tested=False,
        application_modules=len(list((ROOT / "facility_studio").glob("*.py"))),
        payload_files=len(manifest),
        installer_integrity=integrity,
        installer="Windows NSIS online installer; builds application on user's Windows",
        windows_installation_tested=False,
        windows_application_exe_prebuilt=False,
        windows_keyboard_hardware_tested=False,
        engineering_design_certified=False,
        python_bootstrap_release="3.13.15 x64; fixed official SHA256 plus publisher signature",
        public_template_sha256=digest(
            ROOT / "facility_studio/resources/Equipment_Template.xlsx"
        ),
    )
    (ROOT / "evidence/Release_Verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def write_document(data):
    rows = "".join(
        f"<tr><td>{html.escape(s['name'])}</td><td>{s['checks']:,}</td><td>通過</td></tr>"
        for s in data["suites"]
    )
    gallery = ""
    for filename, label in [
        ("V554_Air_Live.png", "空氣狀態：直接看到目前點位，随數值更新"),
        ("V554_Lighting_Volume.png", "照明：體積與淨高分開標示，主要結果保持可見"),
        ("V554_Units_Difference.png", "溫度差：以冰水12→7°C說明，不加溫度偏移量"),
        ("V554_Units_Valve.png", "Kv／Cv：明列閥門通流係數定義"),
        ("V554_Equipment_Import.png", "七系統設備需求：分組、条件與尺寸候選"),
        ("V554_Equipment_Compact.png", "小視窗：清單、明細與匯出按鈕保持可操作"),
    ]:
        image = base64.b64encode((ROOT / "evidence" / filename).read_bytes()).decode(
            "ascii"
        )
        gallery += f"<figure><figcaption>{label}</figcaption><img alt='{label}' src='data:image/png;base64,{image}'></figure>"
    document = f"""<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>廠務工具V5.5.4｜更新、使用與驗證</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#eef3f7;color:#142c43;font:16px/1.7 'Microsoft JhengHei','Noto Sans CJK TC',sans-serif}}main{{max-width:1080px;margin:24px auto;background:white;padding:32px;border-radius:12px}}h1{{margin:0;font-size:30px}}h2{{font-size:21px;margin-top:28px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #dbe4eb;vertical-align:top}}th{{background:#edf5f7}}.notice{{background:#fff6e5;padding:16px;border-left:4px solid #bc7b19}}img{{max-width:100%;border:1px solid #dbe4eb}}figure{{margin:20px 0}}figcaption{{font-weight:bold}}code{{word-break:break-word}}@media(max-width:700px){{main{{padding:18px;margin:0}}}}@media print{{figure{{break-inside:avoid}}}}</style><main>
<h1>廠務工具 V5.5.4</h1><p>通用版 · FY圖示 · 四項簡易工具與完整工程工作台</p>
<p>本版處理數字鍵盤輸入、單位說明與照明體積欄位，加入即時空氣線圖及七系統設備表匯入。既有分段空調箱與完整工程工作台保留。</p>
<table><tr><th>項目</th><th>新版行為</th></tr>
<tr><td>數字鍵盤</td><td>小數點／地區小數分隔鍵統一輸入ASCII「.」；支援取代選取文字，不影響普通Delete。套用於主要與子視窗的輸入欄。</td></tr>
<tr><td>溫度差</td><td>更名為「溫度差（升溫／降溫）」。5°C差＝5K＝9°F差；若換算某個溫度，選「溫度」。</td></tr>
<tr><td>Kv／Cv</td><td>更名為「閥門流量係數（Kv／Cv）」，說明水流量／壓差定義與型錄用途；Kv≈0.865Cv(US)。</td></tr>
<tr><td>空氣狀態</td><td>即時畫出目前乾球／含濕比點位、RH曲線、焓與壓力。改值先清除舊點位，驗證通過後重畫。</td></tr>
<tr><td>照明</td><td>體積格明列m³，淨高格明列m；90m³÷3m＝照明面積30m²。切換m²／坪／長寬／體積保持面積。</td></tr>
<tr><td>設備表</td><td>Excel一檔七系統，CSV一檔一系統；按供應群組分開彙總，另列全開與同時需求。</td></tr></table>
<h2>一鍵安裝</h2><ol><li>解壓縮<code>{BUNDLE}</code>。</li><li>雙擊<code>{SETUP}</code>，首次保持連網。</li><li>等候建立應用EXE與桌面FY圖示捷徑，再開「Facility Studio V5.5」，確認顯示5.5.4。</li></ol>
<div class="notice">目標Windows 10/11 Intel/AMD x64。這是線上安裝器，會下載官方Python及套件並在本機建立應用EXE。已編譯Windows PE安裝器、核對CRC、完整解壓及{data['installer_integrity']['embedded_files']}個內含檔案。本次實際測試環境為Linux／Tk；Windows實機安裝與實體數字鍵盤尚未完成驗收。安裝器未具商業程式碼簽章。</div>
<h2>設備範本怎麼填</h2><ol><li>開啟懶人包內的<code>{TEMPLATE}</code>；也可在軟體右上「設備表匯入」→「1 匯出Excel範本」。</li><li>保留工作表名稱及第5列欄名，在黃色欄填實際設備數據。要納入的列把啟用設1；範例啟用0。</li><li>功率、流量與插座數填每台數據，設備台數另填。各系統可用相同設備編號對應，同一系統內不可重複。</li><li>按「2 匯入設備表」，上表看需求與尺寸候選，點選一列看條件、公式與设备明細。匯出TXT／JSON保留全部資料。</li></ol>
<p>選填參數空白會帶入預設並列出採用值；必填空白、無限數、重複編號與錯誤單位會指出系統／列號／欄位。輸入欄公式需貼上值；灰色公式欄不作為工程計算依據。預留100列，更多設備請在下方欄位提示之前插入列，最多每系統10,000筆。</p>
<table><tr><th>系統</th><th>彙總及定寸方式</th><th>重要條件</th></tr>
<tr><td>電力</td><td>各盤／相數／電壓分組，列kW、P/Q/S、電流、NFB與線徑候選、單台支路與插座數。</td><td>插座不再乘功率；不同供電不直接合併電流。支路按額定；進線不低於已納入最大單台支路需求。進線壓降採設計電流與阻抗上界。</td></tr>
<tr><td>PCW</td><td>水量×台數×同時率，各列ΔT分別計熱量再加總，列主管流量及參考管徑。</td><td>清水ρ=1000、cp=4.1868；未核泵揚程及換熱器。</td></tr>
<tr><td>CDA／N2</td><td>標準流量統一至25°C／101.325kPa(abs)，再換管內實際量定寸。</td><td>採已填最低絕壓、最高温度、最低流速上限；不同壓力級次仍須核減壓及供應架構。</td></tr>
<tr><td>EXHAUST</td><td>GEX／SEX／AEX／VEX／HEX分開，列方管與圓管。</td><td>設備端靜壓只列最大已知要求；未知保留空白，不相加為風機總ESP。</td></tr>
<tr><td>DI</td><td>製程同時水量＋全部額外持續循環量，列最小實際內徑。</td><td>持續循環量不乘同時率；水質與實供材質另核。</td></tr>
<tr><td>PV</td><td>標準／實際量、絕壓換算、管徑初估、製程端有效抽速。</td><td>Torr(abs)／kPa(abs)／mbar(abs)，限1~760Torr；未核導通、洩漏、放氣及泵曲線。</td></tr></table>
<p>同時使用率是瞬間需求估算係數，不能當成每小時運轉比例。安全排氣、吹掃及常時需求須另核。正式盤體尺寸、短路遮斷、相別分配、接地、完整管網與原廠選型仍需要現場／原廠資料。</p>
<h2>本版實際執行的驗證</h2><table><tr><th>測試組</th><th>檢查數</th><th>結果</th></tr>{rows}</table>
<p>合計{data['total_checks']:,}項檢查記錄。新增49組情境涵蓋多電壓、多PF、低同時率、馬達與連續負載、不同水量單位／溫差、氣體標準基準／ALPM、三種PV壓力單位、排氣分類、未知靜壓、DI循環量、真實XLSX／CSV讀入及圖上點位反算。</p>
<p>69項新介面檢查實際操作Tk鍵盤事件、選取文字取代、單位說明、體積連動、線圖即時更新、錯誤清除、背景匯入、重試、供電分組篩選、匯出與小視窗。另重跑既有完整工作台與簡易工具回歸。</p>
<p>Excel各工作表經實際改值及公式重算、掃描錯誤並渲染檢查；尚未於Microsoft Excel實機操作。測試通過不等同正式工程設計核准。</p>
<h2>實際介面</h2>{gallery}
<h2>原始碼與安裝完整性</h2><p>原始碼包含{data['application_modules']}個應用模組、工程表、圖示、Excel／CSV範本、測試與案例結果。安裝內容{data['payload_files']}檔逐一核對SHA-256。入口仍為<code>Facility_Studio_V5_5.py</code>；<code>--full</code>開完整工作台。</p>
<p>安裝時會在您的Windows實際執行主案、電力快算、範本匯出、七系統設備分析與GUI啟動檢查，通過才建立桌面捷徑。原始碼內<code>installer/START.cmd</code>也可重建Windows應用EXE。</p>
<p>公式依據與操作細節見README.txt。<a href="https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-8">NIST溫度與溫差</a> · <a href="https://www.spiraxsarco.com/learn-about-steam/control-hardware-electric-pneumatic-actuation/control-valve-sizing-for-water-systems">Spirax Sarco閥門係數</a> · <a href="https://www.python.org/downloads/release/python-31315/">官方Python與SHA-256</a> · <a href="https://pyinstaller.org/en/stable/usage.html">PyInstaller</a></p></main></html>"""
    document = (
        document.replace("随", "隨")
        .replace("条件", "條件")
        .replace("设备", "設備")
        .replace("温度", "溫度")
    )
    (ROOT / "Changes_and_Verification.html").write_text(document, encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    data = verification()
    write_document(data)
    for name in (SETUP, "Changes_and_Verification.html", "README.txt"):
        shutil.copy2(ROOT / name, OUT / name)
    shutil.copy2(
        ROOT / "facility_studio/resources/Equipment_Template.xlsx", OUT / TEMPLATE
    )
    shutil.copy2(
        ROOT / "evidence/Release_Verification.json", OUT / "Release_Verification.json"
    )
    verify_setup(OUT / SETUP, expected_members(ROOT / "installer"))
    source_files = [
        p
        for p in sorted(ROOT.rglob("*"))
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix != ".pyc"
        and not any(part.startswith(".") for part in p.relative_to(ROOT).parts)
        and ".openai-download-" not in p.name
        and p.name != "builder_runtime_path.txt"
        and not (p.suffix == ".exe" and p.name != SETUP)
    ]
    with zipfile.ZipFile(
        OUT / SOURCE, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in source_files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with tempfile.TemporaryDirectory(prefix="facility554_delivery_check_") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(OUT / SOURCE) as archive:
            assert archive.testzip() is None
            archive.extractall(target)
        subprocess.run(
            [
                sys.executable,
                "Facility_Studio_V5_5.py",
                "--project",
                "Default_Project.json",
                "--report",
                "full_check.txt",
                "--result",
                "full_check.json",
            ],
            cwd=target,
            check=True,
        )
        assert json.loads((target / "full_check.json").read_text(encoding="utf-8"))[
            "hash"
        ]
        for tool in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):
            subprocess.run(
                [
                    sys.executable,
                    "Facility_Studio_V5_5.py",
                    "--tool",
                    tool,
                    "--report",
                    tool + ".txt",
                    "--result",
                    tool + ".json",
                ],
                cwd=target,
                check=True,
            )
            assert (
                json.loads((target / (tool + ".json")).read_text(encoding="utf-8"))[
                    "tool"
                ]
                == tool
            )
        subprocess.run(
            [sys.executable, "tests/v554_features.py"], cwd=target, check=True
        )
        subprocess.run(
            [sys.executable, "tests/packaging_checks.py"], cwd=target, check=True
        )
        subprocess.run(
            [sys.executable, "tests/installer_integrity_checks.py"],
            cwd=target,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "Facility_Studio_V5_5.py",
                "--export-equipment-template",
                "exported.xlsx",
            ],
            cwd=target,
            check=True,
        )
        assert digest(target / "exported.xlsx") == data["public_template_sha256"]
    with zipfile.ZipFile(
        OUT / BUNDLE, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in (SETUP, "README.txt", "Changes_and_Verification.html"):
            archive.write(ROOT / name, name)
        archive.write(OUT / TEMPLATE, TEMPLATE)
        archive.write(OUT / SOURCE, SOURCE)
        archive.write(OUT / "Release_Verification.json", "Release_Verification.json")
    with zipfile.ZipFile(OUT / BUNDLE) as archive:
        assert archive.testzip() is None
        assert archive.read(SETUP) == (ROOT / SETUP).read_bytes()
        assert (
            archive.read(TEMPLATE)
            == (ROOT / "facility_studio/resources/Equipment_Template.xlsx").read_bytes()
        )
        verify_setup(archive.read(SETUP), expected_members(ROOT / "installer"))
    delivery = dict(
        version="5.5.4",
        source_zip_crc=True,
        source_zip_actual_execution=True,
        oneclick_zip_crc=True,
        embedded_setup_complete_verified=True,
        embedded_files=data["installer_integrity"]["embedded_files"],
        template_export_matches=True,
        windows_installation_tested=False,
        source_sha256=digest(OUT / SOURCE),
        oneclick_sha256=digest(OUT / BUNDLE),
    )
    (OUT / "Delivery_Integrity.json").write_text(
        json.dumps(delivery, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    files = sorted(
        p for p in OUT.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt"
    )
    (OUT / "SHA256SUMS.txt").write_text(
        "\n".join(digest(p) + "  " + p.name for p in files) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            dict(
                version="5.5.4",
                delivered_archive_execution="PASS",
                checks=data["total_checks"],
                source_files=len(source_files),
                artifacts=[dict(name=p.name, bytes=p.stat().st_size) for p in files],
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
