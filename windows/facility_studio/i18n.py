"""Presentation-only localization. Project keys, enum values and numbers stay canonical."""

import json
import base64
import os
from pathlib import Path
import re
import sys
import weakref

from .english_catalog import TEXT

LANGUAGES = {"zh-Hant": "繁體中文", "en": "English"}
_language = "zh-Hant"
_initialized = False
_listeners = weakref.WeakSet()
_pattern = None
_save_warning = None
_verbatim_pattern = re.compile(r"\ue000([A-Za-z0-9_=-]+)\ue001")


class LocalizedReport(str):
    """A rendered string that retains its source for a later language switch."""

    def __new__(cls, rendered, source):
        item = super().__new__(cls, rendered)
        item.source = source
        return item


def verbatim(value, default=None):
    """Keep user-supplied names and notes out of the translation catalog."""
    text = str(value)
    if default is not None and text == str(default):
        return text
    encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")
    return "\ue000" + encoded + "\ue001" if encoded else ""


def preference_path():
    override = os.environ.get("FACILITY_STUDIO_PREFERENCES")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "Facility_Studio" / "preferences.json"


def initialize():
    global _initialized, _language
    if _initialized:
        return
    _initialized = True
    try:
        path = preference_path()
        if path.stat().st_size > 4096:
            return
        settings = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(settings, dict) and settings.get("language") in LANGUAGES:
            _language = settings["language"]
    except (OSError, ValueError, TypeError):
        pass


def language():
    return _language


def subscribe(listener):
    _listeners.add(listener)


def set_language(value, *, persist=True):
    global _language, _initialized, _save_warning
    if value not in LANGUAGES:
        raise ValueError("Unsupported language: " + str(value))
    _initialized = True
    _language = value
    _save_warning = None
    if persist:
        try:
            from .utils import atomic_text

            path = preference_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_text(path, json.dumps({"language": value}, indent=2))
        except (OSError, ValueError) as error:
            # Read-only profiles may still switch for the current session.
            _save_warning = str(error)
    for listener in list(_listeners):
        if hasattr(listener, "winfo_exists") and not listener.winfo_exists():
            continue
        listener.refresh_language()


def saving_warning():
    return _save_warning


def translate(value, lang=None):
    """Translate authored text; use a single pass so substitutions never cascade.

    Catalog keys include exact messages and engineering terms used in dynamic
    reports. This function is intentionally never called on stored project data.
    """
    text = getattr(value, "source", str(value))
    if _verbatim_pattern.search(text):
        from html import escape

        is_html = text.startswith("<!doctype html>")
        protected = {}

        def preserve(match):
            token = "\x00FSKEEP" + str(len(protected)) + "\x00"
            decoded = base64.urlsafe_b64decode(match[1]).decode("utf-8")
            protected[token] = escape(decoded) if is_html else decoded
            return token

        rendered = translate(_verbatim_pattern.sub(preserve, text), lang)
        for token, decoded in protected.items():
            rendered = rendered.replace(token, decoded)
        return rendered
    if (lang or _language) != "en":
        return text
    if text in TEXT:
        return TEXT[text]
    global _pattern
    if _pattern is None:
        _pattern = re.compile(
            "|".join(re.escape(k) for k in sorted(TEXT, key=len, reverse=True))
        )

    def replace(match):
        key = match.group()
        value = TEXT[key]
        # Dynamic engineering labels often join Chinese words without spaces.
        # Separate translated terms so English remains readable.
        if re.search(r"[\u3400-\u9fff]", key):
            return " " + value.strip() + " "
        return value

    return _pattern.sub(replace, text).strip()


def canonical_choice(value, options):
    """Accept either language in a schedule without changing canonical enums."""
    if value in options:
        return value
    matches = [item for item in options if translate(item, "en") == value]
    if len(matches) == 1:
        return matches[0]
    return value


def localized_report(function):
    """Localize a public text report without mutating its calculation result."""
    from functools import wraps

    @wraps(function)
    def wrapped(*args, language=None, **kwargs):
        source = function(*args, **kwargs)
        code = language or _language
        rendered = translate(source, code)
        if rendered.startswith("<!doctype html>"):
            rendered = re.sub(
                r'<html lang="[^"]+">', '<html lang="' + code + '">', rendered, count=1
            )
        return LocalizedReport(rendered, source)

    return wrapped
