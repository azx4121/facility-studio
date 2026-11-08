#!/usr/bin/env python3
"""Validate current public documentation without network access or third-party packages.

Historical pages are checked when linked to, but not rewritten or promoted to
current evidence. This is a documentation check, not application acceptance.
"""
from pathlib import Path
import hashlib
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')


def markdown_ids(text):
    ids = set(re.findall(r'<a\s+[^>]*id=["\']([^"\']+)', text))
    counts = {}
    in_code = False
    for line in text.splitlines():
        if line.startswith('```'):
            in_code = not in_code
        if in_code or not re.match(r'^#{1,6}\s', line):
            continue
        title = re.sub(r'^#{1,6}\s+|\s+#+$', '', line).lower()
        title = re.sub(r'!?\[([^\]]+)\]\([^)]+\)', r'\1', title)
        title = re.sub(r'<[^>]+>', '', title)
        slug = ''.join(c for c in title if c in '-_ ' or c.isalnum() or unicodedata.category(c).startswith('M'))
        slug = slug.replace(' ', '-')
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        ids.add(slug + (f'-{number}' if number else ''))
    return ids


def check():
    docs = sorted(set([ROOT/'README.md', ROOT/'README.en.md', ROOT/'CONTRIBUTING.md',
        ROOT/'docs/development.md', ROOT/'docs/images/README.md', ROOT/'docs/tutorial/README.md',
        ROOT/'docs/releases/v5.7.3.md', *ROOT.glob('docs/guides/*.md'),
        *ROOT.glob('docs/README*.md'), *ROOT.glob('docs/faq*.md'), *ROOT.glob('docs/signing*.md'),
        *ROOT.glob('docs/getting-started*.md'), *ROOT.glob('docs/visual-tour*.md'),
        *ROOT.glob('docs/verification/*.md')]))
    errors = []
    checked = 0
    for source in docs:
        text = source.read_text(encoding='utf-8')
        explicit = re.findall(r'<a\s+[^>]*id=["\']([^"\']+)', text)
        if len(explicit) != len(set(explicit)):
            errors.append(f'{source.relative_to(ROOT)}: duplicate explicit anchors')
        for raw in LINK.findall(text):
            url = urlsplit(raw)
            if url.scheme or url.netloc:
                continue
            target = (source.parent / unquote(url.path)).resolve() if url.path else source
            checked += 1
            if not target.is_relative_to(ROOT):
                errors.append(f'{source.relative_to(ROOT)}: path escapes repository: {raw}')
            elif not target.exists():
                errors.append(f'{source.relative_to(ROOT)}: missing target: {raw}')
            elif url.fragment and target.suffix.lower() == '.md':
                if unquote(url.fragment) not in markdown_ids(target.read_text(encoding='utf-8')):
                    errors.append(f'{source.relative_to(ROOT)}: missing anchor: {raw}')
    diagrams = list((ROOT/'docs/images/diagrams').glob('*.svg'))
    if len(diagrams) != 6:
        errors.append('Expected three bilingual diagrams (six SVG files)')
    for path in diagrams:
        try:
            tree = ET.fromstring(path.read_text(encoding='utf-8'))
            tags = {el.tag.rsplit('}', 1)[-1] for el in tree.iter()}
            if not {'title', 'desc'} <= tags or tree.get('role') != 'img':
                errors.append(f'{path.name}: missing accessible image description')
            if {'script', 'foreignObject', 'image'} & tags:
                errors.append(f'{path.name}: scripts, embedded images or foreign objects are not permitted')
            provenance = (ROOT/'docs/images/README.md').read_text(encoding='utf-8')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if f'[{path.name}](diagrams/{path.name}) | `{digest}`' not in provenance:
                errors.append(f'{path.name}: SHA256 does not match the provenance page')
            strings = ''.join(tree.itertext())
            disclaimer = '非軟體截圖或驗收證明' if '.zh.' in path.name else 'not a UI screenshot or acceptance evidence'
            if disclaimer not in strings:
                errors.append(f'{path.name}: missing illustration disclaimer')
            for el in tree.iter():
                for key, value in el.attrib.items():
                    if key.lower().startswith('on') or (key.endswith('href') and not value.startswith('#')):
                        errors.append(f'{path.name}: unsafe/external attribute {key}')
        except ET.ParseError as exc:
            errors.append(f'{path.name}: invalid XML: {exc}')
    screenshots = [ROOT/'docs/images'/name for name in (
        'facs-5.7.3-v22-macos-arm64-electrical-zh-Hant.jpg',
        'facs-5.7.3-v22-macos-arm64-workbench-zh-Hant.jpg',
        'facs-5.7.3-v22-macos-arm64-vacuum-en.jpg',
    )]
    provenance = (ROOT/'docs/images/README.md').read_text(encoding='utf-8')
    for path in screenshots:
        if not path.is_file():
            errors.append(f'{path.name}: missing original candidate screenshot')
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if f']({path.name}) | {len(data)} | `{digest}`' not in provenance:
            errors.append(f'{path.name}: bytes/SHA256 do not match the provenance page')
        if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
            errors.append(f'{path.name}: invalid JPEG signature')
    for error in errors:
        print('FAIL:', error)
    print(f'{len(docs)} current Markdown documents; {checked} local links; {len(diagrams)} SVG diagrams; {len(screenshots)} candidate screenshots; {len(errors)} errors.')
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(check())
