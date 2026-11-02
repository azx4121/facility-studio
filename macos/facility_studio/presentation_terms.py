"""Product wording only; calculation enums and private audit records stay stable."""
import re

TERMS = {
    'PsychroLib': ('濕空氣計算模型', 'psychrometric model'),
    'python-hvac': ('盤管熱質平衡模型', 'coil heat and mass model'),
    'CoolProp': ('熱物性模型', 'thermophysical model'),
    'fluids': ('流體壓損模型', 'fluid pressure-loss model'),
    'Pint': ('工程單位換算', 'engineering unit conversion'),
}


def user_text(text, english=False):
    if not english:
        text = text.replace('CoolProp 純水溫壓', '純水溫壓物性')
        text = text.replace('幾何 ε-NTU（python-hvac）', '幾何盤管性能計算')
    text = text.replace('工程模型設定｜五庫核心融合', '進階工程設定')
    text = text.replace('工程模型設定｜五庫融合', '進階工程設定')
    text = text.replace('Facility Studio 五庫融合測試版', 'Facility Studio 測試版')
    text = text.replace('五庫融合', '工程計算').replace('五庫核心融合', '工程計算')
    text = re.sub(r'\b[Ff]usion(?:[. -]\d+)?\b', '測試版' if not english else 'test edition', text)
    for name, words in TERMS.items():
        text = re.sub(re.escape(name) + r'(?:\s+\d+\.\d+(?:\.\d+)*)?', words[1 if english else 0], text, flags=re.I)
    return text
