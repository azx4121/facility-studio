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


def test_exported_review_files_omit_dependency_metadata(tmp_path):
    from facility_studio.engineering_verification import compare_defaults, export_report
    data = compare_defaults()
    for extension in ('txt', 'html', 'json'):
        target = tmp_path / ('核對.' + extension)
        export_report(data, target)
        content = target.read_text()
        assert not BANNED.search(content)
        assert '套件版本' not in content
