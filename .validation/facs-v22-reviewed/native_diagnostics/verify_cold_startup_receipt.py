"""Fail closed on incomplete cold real-entry native Windows startup receipts."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

PREFIX = 'test_cold_real_entry_contains_untouched_native_window'
EXPECTED = {f'{PREFIX}[{launch}-{mode}-{language}]': (mode, language)
            for launch in range(4) for mode in ('simple', 'workbench')
            for language in ('zh-Hant', 'en')}
SOURCES = ('integration/entry.py', 'windows/facility_studio/cli.py',
           'windows/facility_studio/window_geometry.py',
           'windows/facility_studio/simple_desktop.py', 'windows/facility_studio/desktop.py')
VIEWS = ('facility_studio.simple_desktop', 'facility_studio.desktop')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def rectangle(value):
    require(isinstance(value, list) and len(value) == 4
            and all(type(n) is int for n in value)
            and value[0] < value[2] and value[1] < value[3], 'Invalid native rectangle')
    return value


def verify(path, source):
    raw = Path(path).read_bytes()
    require(b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw, 'Unsafe JUnit document')
    doc = ET.fromstring(raw)
    suites = list(doc.iter('testsuite'))
    cases = list(doc.iter('testcase'))
    require(len(suites) == 1 and len(cases) == 16
            and {c.get('name') for c in cases} == set(EXPECTED), 'Incomplete or duplicate cold cases')
    suite = suites[0]
    require(suite.get('tests') == '16' and all(suite.get(k) == '0'
            for k in ('failures', 'errors', 'skipped')), 'JUnit aggregate failure/count mismatch')
    expected_hashes = {name: hashlib.sha256((Path(source) / name).read_bytes()).hexdigest()
                       for name in SOURCES}
    for case in cases:
        require(case.get('classname', '').endswith('test_windows_cold_startup'), 'Wrong cold test module')
        require(not any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped')),
                'Cold startup failed or skipped')
        props = case.findall('./properties/property[@name="cold_startup_readout"]')
        require(len(props) == 1, 'Missing or duplicate cold startup readout')
        data = json.loads(props[0].get('value'), object_pairs_hook=unique_pairs)
        mode, language = EXPECTED[case.get('name')]
        require(data.get('mode') == mode and data.get('language') == language, 'Wrong launch identity')
        require(data.get('passed') is True and data.get('stable') is True
                and type(data.get('entry_exit')) is int and data['entry_exit'] == 0
                and data.get('errors') == [] and data.get('probe_moves_or_resizes_window') is False,
                'Cold entry did not pass without intervention')
        require(data.get('views_imported_when_tk_created') == {name: False for name in VIEWS}
                and all(value is False for value in data['views_imported_when_tk_created'].values()),
                'View imported before Tk creation')
        hashes = data.get('source_sha256')
        require(isinstance(hashes, dict), 'Missing source hashes')
        normalized = {name.replace('\\', '/'): value for name, value in hashes.items()}
        require(len(normalized) == len(hashes) and normalized == expected_hashes, 'Wrong source bytes')
        events = data.get('events')
        require(isinstance(events, list) and events and all(isinstance(e, dict) and 'error' not in e
                and isinstance(e.get('native'), dict)
                for e in events), 'Missing or failed native observations')
        require(any(e.get('event') == 'first_map' and isinstance(e.get('native'), dict) for e in events)
                and all(any(e.get('event') == event and e.get('function') == '_place_initial_windows_window'
                            for e in events) for event in ('call', 'return')), 'Missing cold Map or placement trace')
        require(all(type(e.get('elapsed')) in (int, float) and math.isfinite(e['elapsed'])
                    and e['elapsed'] >= 0 for e in events), 'Invalid observation time')
        require(all(a['elapsed'] <= b['elapsed'] for a, b in zip(events, events[1:])), 'Reordered observations')
        settled = data.get('settled')
        require(isinstance(settled, dict) and type(settled.get('hwnd')) is int and settled['hwnd'] > 0
                and type(settled.get('menu')) is int and settled['menu'] > 0
                and type(settled.get('dwm_hresult')) is int and settled['dwm_hresult'] == 0
                and settled.get('state') == 'normal', 'No settled native menu/window')
        samples = [e for e in events if e.get('event') == 'settled_sample'][-6:]
        require(len(samples) == 6 and all(e.get('native') == settled for e in samples)
                and samples[-1]['elapsed'] - samples[0]['elapsed'] >= 0.5,
                'Six stable samples spanning half a second required')
        work = rectangle(settled.get('work'))
        for name in ('outer', 'visible', 'client'):
            rect = rectangle(settled.get(name))
            require(work[0] <= rect[0] < rect[2] <= work[2]
                    and work[1] <= rect[1] < rect[3] <= work[3], 'Clipped settled ' + name)
        require(data.get('containment') == {name: True for name in ('outer', 'visible', 'client')}
                and all(v is True for v in data['containment'].values()), 'Incomplete containment claims')
    return dict(cold_startup_cases=16, zero_skips=True, real_entry=True, source_hashes_verified=True, passed=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.receipt, args.source)))
