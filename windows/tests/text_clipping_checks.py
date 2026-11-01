"""Text must not be cut off: sidebar, author credit, labels, buttons, KPI cards, chart captions.

Real Tk widgets are laid out at the smallest window sizes in both languages and every visible
text widget is measured against the space it was given:
- a label or button without wrapping must be at least as wide as its text;
- a wrapping label must be at least as wide as its longest word (CJK wraps per character) and as
  tall as its wrapped text needs;
- the sidebar items, tutorial button and author credit must lie fully inside the sidebar;
- the psychrometric chart's legend and its A / B captions must stay inside the canvas and apart.
Read-only combo boxes (selected text wider than the field) are not covered here.
Needs a display. It proves the laid-out sizes, not how Windows renders the fonts.
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from tkinter import font as tkfont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_settings = tempfile.mkdtemp(prefix="facility_clipping_")
os.environ["LOCALAPPDATA"] = _settings
os.environ["FACILITY_STUDIO_PREFERENCES"] = str(Path(_settings) / "preferences.json")

from facility_studio import i18n  # noqa: E402
from facility_studio.localized_tk import tk, ttk  # noqa: E402
from facility_studio.simple_desktop import SimpleToolsApp, TOOLS  # noqa: E402

checks = []
TEXT_CLASSES = {"Label", "TLabel", "Button", "TButton", "TCheckbutton", "Checkbutton", "TRadiobutton"}
TOKEN = re.compile(r"[^\s　-鿿＀-￯]+|[　-鿿＀-￯]")
TOLERANCE = 2


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:300]))


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def font_of(widget):
    for lookup in (lambda: str(widget.cget("font")),
                   lambda: ttk.Style(widget).lookup(str(widget.cget("style")) or widget.winfo_class(), "font")):
        try:
            name = lookup()
            if name:
                return tkfont.Font(root=widget, font=name)
        except tk.TclError:
            pass
    return tkfont.nametofont("TkDefaultFont")


def clipped(top, skip=()):
    found = []
    for w in walk(top):
        if w.winfo_class() not in TEXT_CLASSES or not w.winfo_ismapped():
            continue
        if any(w is s or str(w).startswith(str(s) + ".") for s in skip):
            continue
        try:
            text = str(w.cget("text"))
        except tk.TclError:
            continue
        if not text.strip():
            continue
        font, width, height = font_of(w), w.winfo_width(), w.winfo_height()
        try:
            wrap = int(float(w.cget("wraplength") or 0))
        except (tk.TclError, ValueError):
            wrap = 0
        why = []
        if wrap == 0:
            need = max(font.measure(line) for line in text.split("\n"))
            if width + TOLERANCE < need and w.winfo_class() in ("Label", "TLabel", "Button", "TButton"):
                why.append(f"text {need}px wider than {width}px")
        else:
            longest = max((font.measure(token) for token in TOKEN.findall(text)), default=0)
            if width + TOLERANCE < longest:
                why.append(f"word {longest}px wider than {width}px")
            if height + 1 < w.winfo_reqheight():
                why.append(f"height {height}px below the {w.winfo_reqheight()}px its lines need")
        if why:
            found.append(f"{w.winfo_class()} {text.replace(chr(10), ' ')[:36]!r}: {'; '.join(why)}")
    return found


def inside(widget, parent):
    return (widget.winfo_rooty() >= parent.winfo_rooty() - 1
            and widget.winfo_rooty() + widget.winfo_height() <= parent.winfo_rooty() + parent.winfo_height() + 1
            and widget.winfo_height() >= widget.winfo_reqheight() - 1)


def packed_height(frame):
    """Height at which every packed child of the frame is fully visible."""
    total = 0
    for child in frame.winfo_children():
        if child.winfo_manager() == "pack":
            pad = child.pack_info()["pady"]
            total += child.winfo_reqheight() + (sum(map(int, pad)) if isinstance(pad, (tuple, list)) else 2 * int(pad))
    return total


def intersects(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


root = tk.Tk()
app = SimpleToolsApp(root)
LANGUAGES = (("zh-Hant", "繁體中文"), ("en", "English"))

# 1. Simple tools at their smallest window, every tool, both languages.
for language, label in LANGUAGES:
    i18n.set_language(language, persist=False)
    root.geometry(f"{root.minsize()[0]}x{root.minsize()[1]}+0+0")
    root.update()
    root.update()
    side = app.sidebar
    check(f"simple/{language}: tutorial button and author credit are fully inside the sidebar",
          inside(app.tutorial_button, side) and inside(app.author_credit, side),
          (app.tutorial_button.winfo_height(), app.tutorial_button.winfo_reqheight(),
           app.author_credit.winfo_height(), app.author_credit.winfo_reqheight()))
    check(f"simple/{language}: every navigation button is fully inside the sidebar",
          all(inside(b, side) for b in list(app.nav.values())),
          [k for k, b in app.nav.items() if not inside(b, side)])
    check(f"simple/{language}: window is at least as tall as the sidebar needs",
          root.winfo_height() >= packed_height(side), (root.winfo_height(), packed_height(side)))
    for key in TOOLS:
        app.show_tool(key)
        root.update()
        root.update()
        hidden = [page for page in app.pages.values() if page is not app.active_page()]
        problems = clipped(root, skip=hidden)
        check(f"simple/{language}/{key}: no clipped text at {root.winfo_width()}x{root.winfo_height()}", not problems, problems[:3])

# 2. Psychrometric chart captions at the narrow size and a wide size.
for language, label in LANGUAGES:
    i18n.set_language(language, persist=False)
    for geometry in (f"{root.minsize()[0]}x{root.minsize()[1]}", "1280x860"):
        root.geometry(geometry + "+0+0")
        app.show_tool("air")
        root.update()
        root.update()
        chart = app.pages["air"].air_chart
        width, left = chart.winfo_width(), 52
        legend, a_label, b_label = chart.bbox("legend"), chart.bbox("state_label"), chart.bbox("comparison_label")
        tag = f"chart/{language}/{geometry}"
        check(f"{tag}: legend stays inside the chart", legend and legend[0] >= 0 and legend[2] <= width, (legend, width))
        check(f"{tag}: A and B captions stay inside the chart",
              a_label and b_label and min(a_label[0], b_label[0]) >= 0 and max(a_label[2], b_label[2]) <= width, (a_label, b_label, width))
        check(f"{tag}: A caption does not cover the vertical axis numbers", a_label and a_label[0] >= left, (a_label, left))
        check(f"{tag}: A and B captions do not overlap", a_label and b_label and not intersects(a_label, b_label), (a_label, b_label))

# 3. Full workbench: sidebar, header toolbars, footer bar.
workbench = app.open_workbench()
wroot = workbench.root
for language, label in LANGUAGES:
    i18n.set_language(language, persist=False)
    for geometry in ("880x560", "1240x840"):
        wroot.geometry(geometry + "+20+20")
        for _ in range(6):
            wroot.update()
        tag = f"workbench/{language}/{geometry.split('x')[0]} wide"
        check(f"{tag}: window grew to the height its content needs ({wroot.winfo_height()} px)",
              wroot.winfo_height() >= wroot.minsize()[1], (wroot.winfo_height(), wroot.minsize()))
        side = workbench.nav[0].master
        credit = next(w for w in side.winfo_children() if isinstance(w, tk.Label) and "ANDY HUANG" in str(w.cget("text")))
        check(f"{tag}: author credit and every navigation button are fully visible",
              inside(credit, side) and all(inside(b, side) for b in workbench.nav if b.winfo_manager()),
              [b.cget("text")[:20] for b in workbench.nav if b.winfo_manager() and not inside(b, side)])
        foot = wroot.grid_slaves(row=2, column=1)[0]
        check(f"{tag}: footer bar is fully visible",
              foot.winfo_rooty() + foot.winfo_height() <= wroot.winfo_rooty() + wroot.winfo_height() + 1,
              (foot.winfo_rooty() + foot.winfo_height(), wroot.winfo_rooty() + wroot.winfo_height()))
        for page in range(9):
            workbench.show_page(page)
            for _ in range(2):
                wroot.update()
            problems = clipped(wroot)
            check(f"{tag}/page {page + 1}: no clipped text", not problems, problems[:3])

root.destroy()
failed = [c for c in checks if not c["passed"]]
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "Text_Clipping_Checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"text clipping checks (real Tk layout; sizes only, not Windows rendering): {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
