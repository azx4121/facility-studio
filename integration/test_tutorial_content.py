"""Offline guide contract for the current candidate, without needing a browser."""
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = ROOT / 'docs/tutorial'
REQUIRED = ['start', 'interface', 'first-case', 'inputs', 'results', 'export']


def data(text):
    match = re.search(r'<script type="application/json" id="tutorial-data">(.*?)</script>', text, re.S)
    assert match, 'Missing offline tutorial data'
    return json.loads(match[1])


def constants(platform):
    tree = ast.parse((ROOT / platform / 'facility_studio/tutorial_help.py').read_text(encoding='utf-8'))
    return {item.targets[0].id: ast.literal_eval(item.value) for item in tree.body
            if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id in {'TUTORIAL_FILES', 'SECTIONS'}}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])


def test_same_bilingual_chapters_and_six_required_steps():
    guide = data((TUTORIAL / 'START_HERE.html').read_text(encoding='utf-8'))
    ids = [row['id'] for row in guide['content']['zh-Hant']]
    assert ids == [row['id'] for row in guide['content']['en']]
    assert ids[:6] == REQUIRED
    assert len(set(ids)) == len(ids)
    for platform in ('windows', 'macos'):
        assert set(ids) == constants(platform)['SECTIONS']
    readme = (TUTORIAL / 'README.md').read_text(encoding='utf-8')
    assert '[本候選版驗收狀態](../../handoff/STATUS.json)' not in readme
    assert '731e416，不是本候選版驗收' in readme
    assert 'historical delivery status for 731e416' in readme
    for lang in ('zh-Hant', 'en'):
        assert guide['labels'][lang]['n'] == 6
        assert 'preview.1' in guide['labels'][lang]['offline']
        chapters = {row['id']: row['html'] for row in guide['content'][lang]}
        assert '01_Practice_AHU.json' in chapters['first-case']
        assert 'https://' not in chapters['first-case'], 'First practice must work offline'
        assert '<img' not in chapters['interface'] + chapters['air'], 'Do not present obsolete UI images as current'
        candidate_doc = 'https://github.com/azx4121/facility-studio/blob/2d42afdeb4c09d4edc64f02e55376e239ce0fe4d/docs/2026-11-03-direct-lighting.md'
        assert candidate_doc in chapters['lighting'], 'Candidate document must use a verified commit, not main'
        assert '/blob/main/docs/2026-11-03-' not in chapters['lighting']
        assert 'Facility_Studio_Beginner_Tutorial.zip' not in chapters['first-case']
        for key in ('lighting', 'air', 'capacity'):
            assert '<ol>' in chapters[key], 'New tools need actual ordered workflows'


@pytest.mark.parametrize('platform,suffix', [('windows', 'Windows'), ('macos', 'macOS')])
def test_current_bundle_contains_reviewed_content_and_local_links(platform, suffix):
    source = data((TUTORIAL / 'START_HERE.html').read_text(encoding='utf-8'))
    resource = ROOT / platform / 'facility_studio/resources/beginner_tutorial.zip'
    assert resource.read_bytes() == (TUTORIAL / f'Facility_Studio_Beginner_Tutorial_{suffix}.zip').read_bytes()
    expected = constants(platform)['TUTORIAL_FILES']
    with zipfile.ZipFile(resource) as archive:
        assert set(archive.namelist()) == expected
        assert len(archive.namelist()) == len(expected)
        shipped = data(archive.read('START_HERE.html').decode('utf-8'))
        assert source['content'] == shipped['content'], 'Bundle must not ship older chapters'
        for lang in ('zh-Hant', 'en'):
            assert '5.7.3' in shipped['labels'][lang]['offline']
            assert suffix in shipped['labels'][lang]['offline']
            parser = Links()
            for row in shipped['content'][lang]:
                parser.ids.add(row['id'])
                parser.feed(row['html'])
            for link in parser.links:
                if link.startswith('#'):
                    assert link[1:] in parser.ids
                elif not link.startswith(('https://', 'http://')):
                    assert link in expected, f'Missing local tutorial target: {link}'
        for name in ('READ_ME_FIRST.txt', '01_Practice_AHU.json', '02_Practice_MAU_and_AHU.json'):
            assert archive.read(name) == (TUTORIAL / name).read_bytes()


def test_new_tool_limits_and_saving_are_explicit_in_both_languages():
    guide = data((TUTORIAL / 'START_HERE.html').read_text(encoding='utf-8'))
    required = {
        'zh-Hant': {
            'air': ['所在地大氣壓', '快照', '重新開啟', '比容', '濕球', '焓', '端點'],
            'lighting': ['ID,x,y,z,yaw,scale', '不含反射', 'UGR', 'DIALux', '重新載入', '取代下方配置', '對話框', '0.32 kW'],
            'capacity': ['176 kW', '180 kW', '94／4 kW', '初篩', 'N−1', '不會保存容量計畫', '重新擷取', '待資料／待覆核'],
            'export': ['複製成功', '匯出成功', '黃色', '紅色'],
        },
        'en': {
            'air': ['snapshot', 'reopen', 'specific-volume', 'wet bulb', 'enthalpy', 'endpoints'],
            'lighting': ['ID,x,y,z,yaw,scale', 'excluding reflections', 'UGR', 'DIALux', 'cannot reopen', 'save dialog', '0.32 kW'],
            'capacity': ['176 kW', '180 kW', '94/4 kW', 'N−1', 'does not save this capacity plan', 'Recapture', 'data/review required'],
            'export': ['Copy successful', 'Export successful', 'Red', 'amber'],
        },
    }
    for lang, sections in required.items():
        chapters = {row['id']: row['html'] for row in guide['content'][lang]}
        for key, terms in sections.items():
            for term in terms:
                assert term in chapters[key], (lang, key, term)


def test_named_chinese_controls_exist_in_current_candidate():
    files = ['simple_desktop.py', 'simple_schema.py', 'lighting_layout_ui.py',
             'desktop.py', 'capacity_planning_ui.py']
    controls = ['放大空氣線圖', '配置／直接照度', '容量／擴建規劃', '所在地大氣壓',
                '產生可編輯配置', '從需求彙整擷取', '將兩頁選取列記為方案', '另存計畫']
    page = (TUTORIAL / 'START_HERE.html').read_text(encoding='utf-8')
    for platform in ('windows', 'macos'):
        source = '\n'.join((ROOT / platform / 'facility_studio' / name).read_text(encoding='utf-8') for name in files)
        for control in controls:
            assert control in source and control in page


def test_design_refresher_uses_named_bullets_and_preserves_chapter_order(tmp_path):
    for folder in ('tools', 'docs/tutorial', 'integration'):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'tools/add_design_tutorial.py', tmp_path / 'tools/add_design_tutorial.py')
    shutil.copyfile(ROOT / 'integration/README_繁體中文.md', tmp_path / 'integration/README_繁體中文.md')
    original = (TUTORIAL / 'START_HERE.html').read_text(encoding='utf-8')
    target = tmp_path / 'docs/tutorial/START_HERE.html'
    target.write_text(original, encoding='utf-8')
    subprocess.run([sys.executable, str(tmp_path / 'tools/add_design_tutorial.py')], check=True)
    updated = data(target.read_text(encoding='utf-8'))
    assert updated == data(original), 'Rebuilding design chapters must not replace them with earlier unrelated bullets'
    subprocess.run([sys.executable, str(tmp_path / 'tools/add_design_tutorial.py')], check=True)
    assert data(target.read_text(encoding='utf-8')) == updated


def test_tutorial_javascript_navigation_when_node_available():
    """Test event logic, not layout; keep browser/native acceptance separate."""
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node unavailable for the DOM-event contract')
    result = subprocess.run([node, str(ROOT / 'tools/verify_tutorial_navigation.cjs')],
                            check=True, capture_output=True, text=True)
    evidence = json.loads(result.stdout)
    assert evidence['passed'] and evidence['checks'] >= 30
