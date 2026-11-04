"""Reject altered embedded resources and false provenance in a real CArchive."""
import hashlib
import json
from pathlib import Path

import pytest
from PyInstaller.archive.writers import CArchiveWriter

from integration.windows_onefile import validate_archive


def make_archive(tmp_path, *, corrupt_resource=False, corrupt_commit=False, missing_license=False):
    root = tmp_path / 'source'
    root.mkdir()
    content = {
        'integration/README_繁體中文.md': '操作說明 Ω',
        'integration/README_English.md': 'User guide',
        'LICENSE': 'main license',
        'LICENSE_LEGACY_MIT': 'legacy terms',
        'THIRD_PARTY_NOTICES.md': 'third-party terms',
        'macos/macos/PsychroLib-LICENSE.txt': 'PsychroLib terms',
    }
    for name, text in content.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    resource = b'synthetic resource content'
    expected = dict(provenance_schema=1, commit='a' * 40, version='5.7.3',
                    source_platform='windows', build_channel='stable', source_clean=True,
                    build_inputs_sha256={'integration/build.py': 'b' * 64},
                    product_source_sha256={'facility_studio/resources/測試.bin': hashlib.sha256(resource).hexdigest()})
    embedded = dict(expected, packaging='windows-onefile')
    if corrupt_commit:
        embedded['commit'] = 'c' * 40
    notice = '\n'.join(text for name, text in content.items() if not name.startswith('integration/'))
    files = {'Build_Manifest.json': json.dumps(embedded).encode(),
             '第三方授權.txt': b'incomplete license' if missing_license else notice.encode(),
             'python3.dll': b'synthetic DLL',
             'facility_studio/resources/測試.bin': b'altered' if corrupt_resource else resource,
             '操作說明_繁體中文.md': content['integration/README_繁體中文.md'].encode(),
             'User_Guide_English.md': content['integration/README_English.md'].encode()}
    entries = []
    for i, (name, data) in enumerate(files.items()):
        path = tmp_path / ('entry-' + str(i))
        path.write_bytes(data)
        entries.append((name, str(path), True, 'x'))
    archive = tmp_path / 'synthetic.exe'
    CArchiveWriter(str(archive), entries, 'python312.dll')
    return archive, root, expected


def test_real_archive_preserves_resources_notices_and_exact_source_identity(tmp_path):
    archive, root, expected = make_archive(tmp_path)
    report = validate_archive(archive, root, expected)
    assert report['passed'] and report['embedded_notices'] and report['embedded_python3_dll']
    assert len(report['verified_resource_sha256']) == 3


@pytest.mark.parametrize('tamper', ['corrupt_resource', 'corrupt_commit', 'missing_license'])
def test_tampered_archive_is_rejected(tmp_path, tamper):
    archive, root, expected = make_archive(tmp_path, **{tamper: True})
    with pytest.raises(RuntimeError):
        validate_archive(archive, root, expected)
