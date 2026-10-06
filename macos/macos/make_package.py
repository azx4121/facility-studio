"""Create and byte-verify a ZIP that retains macOS app permissions and symlinks."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def zip_tree(source, destination, root_name):
    source = Path(source)
    with zipfile.ZipFile(
        destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
    ) as archive:
        for path in sorted(source.rglob("*")):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            name = root_name + "/" + path.relative_to(source).as_posix()
            if path.is_symlink():
                item = zipfile.ZipInfo(name)
                item.create_system = 3
                item.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(item, os.readlink(path).encode("utf-8"))
            elif path.is_dir():
                item = zipfile.ZipInfo(name + "/")
                item.create_system = 3
                item.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x10
                archive.writestr(item, b"")
            elif path.is_file():
                archive.write(path, name)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")


def extract_unix_zip(path, destination):
    destination = Path(destination).resolve()
    pending = []
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            target = destination / item.filename
            if not target.resolve().is_relative_to(destination):
                raise ValueError("ZIP path escapes destination")
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode):
                pending.append((target, archive.read(item).decode("utf-8")))
            elif item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
                target.chmod(stat.S_IMODE(mode) or 0o644)
    for target, value in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(value)
    for target, _ in pending:
        if not target.exists() or not target.resolve().is_relative_to(destination):
            raise ValueError("Broken or external ZIP symlink")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build, output = args.build.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="facility_mac_delivery_") as directory:
        directory = Path(directory)
        stage = directory / "stage"
        stage.mkdir()
        shutil.copytree(
            build / "Facility Studio.app", stage / "Facility Studio.app", symlinks=True
        )
        shutil.copy2(ROOT / "README_macOS.txt", stage / "README_macOS.txt")
        shutil.copy2(
            ROOT / "facility_studio/resources/Equipment_Template.xlsx",
            stage / "Facility_Studio_V5_5_4_Equipment_Template.xlsx",
        )
        for name in ("Install_on_Mac.command", "Verify_on_Mac.command"):
            target = stage / name
            shutil.copy2(ROOT / "macos" / name, target)
            target.chmod(0o755)
            subprocess.run(["bash", "-n", str(target)], check=True)
        for name in (
            "Mac_Release_Verification.json",
            "Independent_Bundle_Checks.json",
            "Mac_Bundle_Manifest.json",
        ):
            shutil.copy2(build / name, stage / name)
        source_zip = output / "Facility_Studio_V5_5_4_macOS_Source.zip"
        zip_tree(ROOT, source_zip, "Facility_Studio_V5_5_4_macOS_Source")
        shutil.copy2(source_zip, stage / "Source_and_Verification.zip")
        bundle = output / "Facility_Studio_V5_5_4_macOS_OneClick.zip"
        zip_tree(stage, bundle, "Facility_Studio_V5_5_4_macOS")

        # Verify the delivered bytes after real extraction, including native
        # load paths and every sealed byte. No target executable is run on Linux.
        extracted = directory / "extracted"
        extracted.mkdir()
        extract_unix_zip(bundle, extracted)
        contents = extracted / "Facility_Studio_V5_5_4_macOS"
        report = output / "Mac_Delivery_Integrity.json"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "macos/verify_bundle.py"),
                str(contents / "Facility Studio.app"),
                "--report",
                str(report),
            ],
            check=True,
        )
        for name in ("Install_on_Mac.command", "Verify_on_Mac.command"):
            assert (contents / name).stat().st_mode & 0o111
        assert (
            contents / "Facility_Studio_V5_5_4_Equipment_Template.xlsx"
        ).read_bytes() == (
            ROOT / "facility_studio/resources/Equipment_Template.xlsx"
        ).read_bytes()

        extracted_source = directory / "source"
        extracted_source.mkdir()
        extract_unix_zip(contents / "Source_and_Verification.zip", extracted_source)
        source = extracted_source / "Facility_Studio_V5_5_4_macOS_Source"
        for tool in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):
            subprocess.run(
                [
                    sys.executable,
                    str(source / "Facility_Studio_V5_5.py"),
                    "--tool",
                    tool,
                    "--report",
                    str(directory / f"{tool}.txt"),
                ],
                check=True,
            )
        subprocess.run(
            [
                sys.executable,
                str(source / "Facility_Studio_V5_5.py"),
                "--project",
                str(source / "Default_Project.json"),
                "--report",
                str(directory / "full.txt"),
            ],
            check=True,
        )
        template = directory / "匯出 範本.xlsx"
        subprocess.run(
            [
                sys.executable,
                str(source / "Facility_Studio_V5_5.py"),
                "--export-equipment-template",
                str(template),
            ],
            check=True,
        )
        assert (
            template.read_bytes()
            == (
                contents / "Facility_Studio_V5_5_4_Equipment_Template.xlsx"
            ).read_bytes()
        )
        empty_result = subprocess.run(
            [
                sys.executable,
                str(source / "Facility_Studio_V5_5.py"),
                "--equipment",
                str(template),
                "--report",
                str(directory / "equipment.txt"),
            ],
            capture_output=True,
            text=True,
        )
        assert (
            empty_result.returncode == 2
        ), "Disabled-only template must not produce fake totals"
        # Populate actual active equipment through the shipped schema, rather
        # than relying on a disabled example or an XLSX formula cache.
        sys.path.insert(0, str(source))
        from facility_studio.equipment_schema import SCHEMAS, SYSTEMS, example

        for system in SYSTEMS:
            csv_path = directory / f"實際設備 {system}.csv"
            schema = SCHEMAS[system]
            row = example(system)
            row["enabled"] = 1
            with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([column["label"] for column in schema])
                writer.writerow([row[column["key"]] for column in schema])
            subprocess.run(
                [
                    sys.executable,
                    str(source / "Facility_Studio_V5_5.py"),
                    "--equipment",
                    str(csv_path),
                    "--equipment-system",
                    system,
                    "--report",
                    str(directory / f"equipment_{system}.txt"),
                ],
                check=True,
            )
        checked_source_files = 0
        for path in (
            contents / "Facility Studio.app/Contents/Resources/app/facility_studio"
        ).rglob("*"):
            if path.is_file():
                relative = path.relative_to(
                    contents / "Facility Studio.app/Contents/Resources/app"
                )
                assert path.read_bytes() == (source / relative).read_bytes()
                checked_source_files += 1
        final = json.loads(report.read_text(encoding="utf-8"))
        final.update(
            {
                "zip_crc_checked": True,
                "unix_symlinks_recreated_and_verified": True,
                "delivered_app_matches_source_files": checked_source_files,
                "extracted_source_cli_tools_executed": 7,
                "extracted_source_full_report_executed": True,
                "extracted_source_excel_export_import_executed": True,
                "disabled_template_expected_rejection_checked": True,
                "extracted_source_active_equipment_systems_executed": 7,
                "native_app_executed": False,
                "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                "bundle_size_bytes": bundle.stat().st_size,
            }
        )
        report.write_text(
            json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        shutil.copy2(ROOT / "README_macOS.txt", output / "README_macOS.txt")
        shutil.copy2(
            build / "Mac_Release_Verification.json",
            output / "Mac_Release_Verification.json",
        )
    print(
        f"Delivered and extracted {bundle.name}: {bundle.stat().st_size:,} bytes; 7 source tools, full report, template and native bundle byte checks passed."
    )


if __name__ == "__main__":
    main()
