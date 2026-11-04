"""Formal identities and retired publishers, not native package acceptance."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("platform", ["windows", "macos"])
def test_formal_product_version_ignores_historical_sandbox_flag(platform, monkeypatch):
    monkeypatch.setenv("FACILITY_STUDIO_SANDBOX", "1")
    version = load_file(ROOT / platform / "facility_studio/version.py", "formal_version_" + platform)
    assert version.VERSION == version.BUILD_VERSION == "5.7.3"
    assert version.REVISION == "release.1"
    assert version.REPORT_VERSION == "5.7.3 · " + ("Windows" if platform == "windows" else "macOS")


def test_native_bundle_and_windows_resources_share_formal_identity():
    build = (ROOT / "integration/build.py").read_text(encoding="utf-8")
    resource = (ROOT / "integration/windows_version.txt").read_text(encoding="utf-8")
    installer = (ROOT / "integration/windows_installer.py").read_text(encoding="utf-8")
    assert 'NAME = "Facility Studio 5.7.3"' in build
    assert '"--osx-bundle-identifier", "com.facilitystudio.release573"' in build
    assert 'CFBundleVersion="5.7.3.2"' in build
    assert 'platform.machine() != "arm64"' in build
    assert "README_English.md" in build and "User_Guide_English.md" in build
    assert "filevers=(5, 7, 3, 2), prodvers=(5, 7, 3, 2)" in resource
    assert "StringStruct('ProductVersion', '5.7.3')" in resource
    assert "StringStruct('OriginalFilename', 'Facility Studio 5.7.3.exe')" in resource
    assert 'VIProductVersion "5.7.3.2"' in installer
    assert '"ProductVersion" "5.7.3"' in installer
    assert "FacilityStudio573" in resource and "FacilityStudio573" in installer
    for text in (build, resource, installer):
        assert "preview573" not in text and "Preview573" not in text
        assert "5.7.3-preview.1" not in text and "5.7.3 測試版" not in text


@pytest.mark.parametrize("platform", ["windows", "macos"])
def test_product_data_override_does_not_mutate_os_environment(platform, tmp_path):
    support = load_file(ROOT / platform / "facility_studio/platform_support.py", "formal_support_" + platform)
    env = {"FACILITY_STUDIO_DATA": str(tmp_path / "product-data"), "LOCALAPPDATA": str(tmp_path / "os-data")}
    original = dict(env)
    assert support.app_data_root(platform="win32", environ=env) == tmp_path / "product-data"
    assert env == original
    assert support.app_data_root(platform="win32", environ={"LOCALAPPDATA": env["LOCALAPPDATA"]}) == tmp_path / "os-data/Facility_Studio_V5_5"
    source = (ROOT / platform / "facility_studio/sandbox_ui.py").read_text()
    assert 'os.environ.get("FACILITY_STUDIO_NATIVE_MENUS")' in source
    assert 'root.title("Facility Studio " + BUILD)' in source


def test_entry_uses_product_data_and_retires_obsolete_selftest():
    text = (ROOT / "integration/entry.py").read_text()
    assert 'Path.home() / "Facility Studio Data-5.7.3"' in text
    assert "FACILITY_STUDIO_DATA=str(data)" in text
    assert "LOCALAPPDATA=" not in text
    assert "FACILITY_STUDIO_NATIVE_MENUS=" in text
    assert "historical sandbox self-test is retired" in text
    assert "from facility_studio.sandbox_selftest import" not in text


@pytest.mark.parametrize("filename", ["windows-offline-release.yml", "macos-native-release.yml", "public-downloads-maintenance.yml"])
def test_legacy_workflow_has_no_automatic_trigger_or_release_step(filename):
    text = (ROOT / ".github/workflows" / filename).read_text()
    on = text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert on.strip() == "workflow_dispatch:"
    assert re.findall(r"^  ([a-z_-]+):", text, re.M) == ["workflow_dispatch", "contents", "retired"]
    assert "contents: read" in text and "exit 1" in text
    assert "No software was built, tested or published." in text
    for forbidden in ("uses:", "contents: write", "winrelease", "publish.py", "verify.py", "build_native_release.py", "FACILITY_GITHUB_TOKEN", "github.token", "New-NetFirewallRule", "Remove-NetFirewallRule", "gh release"):
        assert forbidden not in text


@pytest.mark.parametrize("publisher", ["windows/winrelease/publish.py", "macos/macos/publish_mac_release.py"])
def test_retired_publisher_refuses_on_main_without_network_or_asset_changes(publisher, tmp_path):
    marker = tmp_path / "old-asset.exe"
    marker.write_bytes(b"unchanged historical synthetic asset")
    code = '''import runpy, sys

def reject_network(event, args):
    if event.startswith("socket."):
        raise AssertionError("Retired publisher attempted network access")

sys.addaudithook(reject_network)
runpy.run_path(sys.argv[1], run_name="__main__")
'''
    process = subprocess.run([sys.executable, "-c", code, str(ROOT / publisher), "--assets", str(tmp_path)], env=dict(os.environ, GITHUB_REF="refs/heads/main", FACILITY_RELEASE_COMMIT="a" * 40), capture_output=True, text=True, timeout=20)
    assert process.returncode != 0
    assert "historical 5.6 publisher is retired" in process.stderr
    assert "Traceback" not in process.stderr
    assert marker.read_bytes() == b"unchanged historical synthetic asset"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["old-asset.exe"]


@pytest.mark.parametrize("filename", ["啟動_Facility_Studio_Windows.cmd", "打包離線EXE_Windows.cmd"])
def test_historical_cmd_is_inert_and_retains_crlf(filename):
    data = (ROOT / filename).read_bytes()
    assert b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
    text = data.decode("utf-8")
    assert "exit /b 1" in text
    for line in text.splitlines():
        assert line.startswith(("@echo off", "setlocal ", "chcp ", "title ", "echo ", "exit /b 1"))


@pytest.mark.parametrize("platform", ["windows", "macos"])
def test_real_entry_help_keeps_os_appdata_and_old_user_data(platform, tmp_path):
    old_data = tmp_path / 'os-appdata'
    old_data.mkdir()
    marker = old_data / 'existing-user-data.txt'
    marker.write_text('preserve')
    data = tmp_path / 'formal-data'
    code = '''import importlib.util,json,os,sys
spec=importlib.util.spec_from_file_location("formal_entry",sys.argv[1])
entry=importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)
sys.argv=[sys.argv[1],"--help"]
try:
    result=entry.main()
except SystemExit as exc:
    result=exc.code
print(json.dumps({"exit":result,"os_data":os.environ["LOCALAPPDATA"],"product_data":os.environ["FACILITY_STUDIO_DATA"],"native_menus":os.environ["FACILITY_STUDIO_NATIVE_MENUS"]}))
'''
    process = subprocess.run([sys.executable, '-c', code, str(ROOT/'integration/entry.py')],
        env=dict(os.environ, PYTHONPATH=str(ROOT/platform), LOCALAPPDATA=str(old_data),
                 FACILITY_STUDIO_FUSION_DATA=str(data), MPLCONFIGDIR=str(tmp_path/'mpl')),
        capture_output=True, encoding='utf-8', timeout=60)
    assert process.returncode == 0, process.stderr
    import json
    result = json.loads(process.stdout.splitlines()[-1])
    assert result == {'exit': 0, 'os_data': str(old_data), 'product_data': str(data), 'native_menus': '1'}
    assert marker.read_text() == 'preserve'
    assert sorted(p.name for p in old_data.iterdir()) == ['existing-user-data.txt']
    assert (data/'啟動與驗收記錄.log').is_file()
