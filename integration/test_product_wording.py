import copy
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'macos'))
from facility_studio.schema import default_project
from facility_studio.engine import calculate
from facility_studio.reports import report, nm_report
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.ahu_engine import nm_calculate
from facility_studio.simple_schema import defaults
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_reports import tool_report
from facility_studio.i18n import translate, canonical_choice

BANNED = re.compile(r'PsychroLib|python-hvac|CoolProp|\bfluids\b|\bPint\b|fusion|五庫|實際計算後端', re.I)


def test_product_report_keeps_models_private_and_does_not_mutate_input():
    p = default_project()
    before = copy.deepcopy(p)
    r = calculate(p)
    assert len(r['engineering_backends']) == 5
    assert not BANNED.search(str(report(r)))
    assert p == before
    assert not BANNED.search(str(nm_report(nm_calculate(dict(NM_DEFAULTS)))))


@pytest.mark.parametrize('tool', ['water','liquid','vacuum','duct','units','cleanroom','electrical'])
def test_user_tool_reports_use_engineering_terms(tool):
    d = defaults(tool)
    r = calculate_tool(tool, d)
    assert not BANNED.search(str(tool_report(r, d)))


@pytest.mark.parametrize('canonical', ['CoolProp 純水溫壓','幾何 ε-NTU（python-hvac）'])
def test_presented_choices_round_trip_to_existing_project_values(canonical):
    display = translate(canonical, 'zh-Hant')
    assert not BANNED.search(display)
    assert canonical_choice(display, [canonical, '沿用手動物性']) == canonical


def test_installer_public_name_and_operation_guide_are_product_only():
    readme = (ROOT/'integration/README_繁體中文.md').read_text()
    assert not BANNED.search(readme)
    build = (ROOT/'integration/build.py').read_text()
    assert 'NAME = "Facility Studio 5.7.1 測試版"' in build
    meta = (ROOT/'integration/windows_version.txt').read_text()
    assert 'FacilityStudioEngineeringFusion' not in meta
    assert '五庫' not in meta
    installer = (ROOT/'integration/windows_installer.py').read_text()
    welcome = next(line for line in installer.splitlines() if 'MUI_WELCOMEPAGE_TEXT' in line)
    assert not BANNED.search(welcome)
    assert '五套工程計算庫' not in welcome and 'Python' not in welcome


def test_exported_review_files_omit_dependency_metadata(tmp_path):
    from facility_studio.engineering_verification import compare_defaults, export_report
    data = compare_defaults()
    for extension in ('txt', 'html', 'json'):
        target = tmp_path / ('核對.' + extension)
        export_report(data, target)
        content = target.read_text()
        assert not BANNED.search(content)
        assert '套件版本' not in content


@pytest.mark.parametrize('platform', ['macos', 'windows'])
def test_bundled_tutorial_is_current_and_uses_product_wording(platform):
    import json
    import zipfile
    with zipfile.ZipFile(ROOT/platform/'facility_studio/resources/beginner_tutorial.zip') as archive:
        page = archive.read('START_HERE.html').decode('utf-8')
        data = json.loads(re.search(r'id="tutorial-data">(.*?)(</script>)', page, re.S)[1])
        assert '5.7.1' in data['labels']['zh-Hant']['offline']
        assert {'liquid', 'vacuum', 'cleanroom'} <= {c['id'] for c in data['content']['zh-Hant']}
        for name in archive.namelist():
            if name.endswith(('.html', '.txt')) and not name.upper().startswith('LICENSE'):
                assert not BANNED.search(archive.read(name).decode('utf-8'))


def test_native_menu_copy_uses_public_engineering_language():
    import ast
    tree = ast.parse((ROOT/'macos/facility_studio/sandbox_ui.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not BANNED.search(node.value)


@pytest.mark.parametrize('tool', ['liquid', 'vacuum'])
def test_new_tools_are_available_through_the_delivered_command_line(tool, monkeypatch, capsys):
    from facility_studio.cli import main
    monkeypatch.setattr(sys, 'argv', ['facility-studio', '--language', 'zh-Hant', '--tool', tool])
    assert main() == 0
    assert not BANNED.search(capsys.readouterr().out)
