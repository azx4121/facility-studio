"""Fail closed on missing, duplicate, skipped or incomplete startup evidence."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

PREFIX = 'test_native_untouched_launch_contains_outer_visible_frame_and_client'
EXPECTED = {f'{PREFIX}[{launch}-{entry}-{language}]'
            for launch in range(4) for entry in ('simple', 'workbench')
            for language in ('zh-Hant', 'en')}


def verify(path):
    cases = list(ET.parse(path).getroot().iter('testcase'))
    assert len(cases) == 16 and {c.get('name') for c in cases} == EXPECTED
    for case in cases:
        assert not any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))
        props = case.findall('./properties/property[@name="startup_readout"]')
        assert len(props) == 1
        data = json.loads(props[0].get('value'))
        assert data['native_menu'] is True and data['first_map']
        work = data['work_area']
        assert len(work) == 4 and work[0] < work[2] and work[1] < work[3]
        assert set(data['settled']) == {'outer', 'visible', 'client'}
        for rect in data['settled'].values():
            assert len(rect) == 4
            assert work[0] <= rect[0] < rect[2] <= work[2]
            assert work[1] <= rect[1] < rect[3] <= work[3]
        assert case.get('name').endswith(f'-{data["entry"]}-{data["language"]}]')
    return {'startup_cases': 16, 'zero_skips': True, 'native_menu': True, 'passed': True}


if __name__ == '__main__':
    print(json.dumps(verify(Path(sys.argv[1]))))
