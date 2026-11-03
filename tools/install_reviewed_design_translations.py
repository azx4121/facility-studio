"""Install explicitly reviewed local-model suggestions, never execute model text."""
from pathlib import Path
import ast
import json
import pprint
import re

root = Path(__file__).resolve().parents[1]
evidence = Path('/Users/chaoi/Facility-Studio-FEED-Evidence-20261103')
original = list(json.loads((evidence / 'missing-translations.json').read_text(encoding='utf-8')))
translations = {}
for index in range(0, len(original), 40):
    response = json.loads((evidence / f'qwen-translation-{index}.json').read_text(encoding='utf-8'))
    if response.get('done') is not True or response.get('model') != 'qwen3.8:27b':
        raise ValueError('Local-model response did not finish')
    content = response['message']['content'].lstrip()
    parsed, end = json.JSONDecoder().raw_decode(content)
    batch = original[index:index + 40]
    if not isinstance(parsed, list) or len(parsed) != len(batch):
        raise ValueError('Unexpected suggestion format or missing translations')
    for source, english in zip(batch, parsed):
        if not isinstance(english, str) or re.search(r'[\u3400-\u9fff]', english):
            raise ValueError('Invalid English suggestion')
        translations[source] = english

# Human-reviewed corrections: retain mass balance and the actual quantity being
# supplied. The model's extra </think> suffix is not source code or UI content.
translations['熱質平衡與公用需求'] = 'Heat and mass balance and utility requirements'
translations['kPa(abs)；化學液／混合液須提供，不能沿用純水值'] = 'kPa(abs); chemical liquids and mixtures require their own bubble-point pressure, not a pure-water value'
translations.update({
    '吸入口相對泵基準高度': 'Suction nozzle elevation relative to pump datum',
    'm；相對原廠 NPSH 基準面，高於為正；不同基準不可混用': 'm; relative to the manufacturer NPSH datum, positive above it; do not mix reference levels',
    '吸入口相對原廠 NPSH 基準面 ': 'Suction nozzle elevation relative to manufacturer NPSH datum ',
    '限大型液槽表面速度可忽略、等溫穩態滿管均質液體；吸入管採本頁內徑及流量。液位與吸入口高度均相對原廠 NPSH 基準面。吸入總壓損須另填，包含入口、管件、濾器及設備，不能直接套用排出路徑。全線局部高點、夾氣、瞬變、最小淹沒深度與泵全曲線須另核對。': 'Limited to a large vessel with negligible surface velocity and isothermal steady homogeneous full-pipe flow. Suction diameter and flow follow this page. Both liquid level and nozzle elevation reference the manufacturer NPSH datum. Enter total suction losses separately, including entry, fittings, filters and equipment; do not reuse discharge losses. Local high points, entrained gas, transients, minimum submergence and complete pump curves require separate checks.',
})
# Only strings actually present in product code are added; obsolete drafts are
# not part of the presentation catalog.
authored = set()
for path in (root / 'macos/facility_studio').glob('*.py'):
    if path.name == 'english_catalog.py':
        continue
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            authored.add(node.value)
translations = {k: v for k, v in translations.items() if k in authored}
for platform in ('macos', 'windows'):
    path = root / platform / 'facility_studio/english_catalog.py'
    with path.open('a', encoding='utf-8') as stream:
        stream.write('\n# Design document and suction UI; local suggestions independently reviewed.\nTEXT.update(' + pprint.pformat(translations, width=130, sort_dicts=True) + ')\n')
(evidence / 'reviewed-translations.json').write_text(json.dumps(translations, ensure_ascii=False, indent=2), encoding='utf-8')
print('Installed reviewed translations:', len(translations))
