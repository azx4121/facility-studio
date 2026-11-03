"""Add reviewed design-document and suction instructions to the offline guide."""
from pathlib import Path
import html
import json
import re

root = Path(__file__).resolve().parents[1]
path = root / "docs/tutorial/START_HERE.html"
page = path.read_text(encoding="utf-8")
match = re.search(r'(<script type="application/json" id="tutorial-data">)(.*?)(</script>)', page, re.S)
data = json.loads(match[2])
lines = (root / "integration/README_繁體中文.md").read_text(encoding="utf-8").splitlines()
paragraphs = []
for prefix in ('- 主畫面「設計依據與交付審查」', '- 「液體／純水管路」頁可勾選「加做泵浦吸入校核」'):
    matches = [line[2:] for line in lines if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError("Expected one tutorial source paragraph: " + prefix)
    paragraphs.append(matches[0])
entries = [
    ("design_review", "設計依據與交付審查", "Design basis and document review",
     "Create a separate project, enter the design basis and list each standard as Name｜Edition｜Clause｜Scope｜Source. Attach documents and record independent human review. Changed inputs or evidence invalidate prior reviews. Export saves a corresponding immutable revision. Attach an updated report whenever its original calculation changes. Move the entire project folder, including evidence. Document readiness is not certification; reviewer identities are manually recorded, not authenticated."),
    ("pump_suction", "液體泵浦吸入校核", "Pump suction check",
     "Enable the suction check on the liquid page. Enter vessel-surface absolute pressure, minimum level relative to pump datum and complete suction losses. The suction pipe uses the displayed diameter and flow; discharge losses are not reused. Mixtures need a sourced bubble-point pressure. Compare NPSHa with the actual manufacturer NPSHr plus a sourced project margin. Missing inputs or flashing do not pass. Changed conditions invalidate losses and curve references. Scope excludes transients, entrained gas and minimum submergence."),
]
for language in ("zh-Hant", "en"):
    for i, (key, title_zh, title_en, english) in enumerate(entries):
        title = title_zh if language == "zh-Hant" else title_en
        body = paragraphs[i] if language == "zh-Hant" else english
        row = dict(id=key, title=title, html="<h2>" + html.escape(title) + "</h2><p>" + html.escape(body) + "</p>")
        existing = next((item for item in data["content"][language] if item["id"] == key), None)
        if existing is not None:
            existing.update(row)
        else:
            data["content"][language].append(row)
encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
path.write_text(page[:match.start(2)] + encoded + page[match.end(2):], encoding="utf-8")
