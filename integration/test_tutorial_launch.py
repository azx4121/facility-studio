"""Tutorial extraction and launch contracts; never starts an external browser.

These tests simulate source/frozen module paths, not native browser acceptance.
"""
import importlib
import importlib.util
from pathlib import Path
import shutil
import sys
from unittest.mock import Mock
from urllib.parse import parse_qs, unquote, urlsplit
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=("windows", "macos"))
def tutorial(request, monkeypatch, tmp_path):
    # Isolate both platform copies without changing facility_studio imports used
    # by the rest of the integration suite.
    name = "_tutorial_launch_" + request.param
    package = ROOT / request.param / "facility_studio"
    spec = importlib.util.spec_from_file_location(name, package / "__init__.py",
                                                  submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    help_module = importlib.import_module(name + ".tutorial_help")
    messages = importlib.import_module(name + ".localized_tk").messagebox
    monkeypatch.setattr(messages, "showinfo", Mock())
    monkeypatch.setattr(messages, "showerror", Mock())
    # Even an accidentally unpatched call in a new test must not launch a browser.
    monkeypatch.setattr(help_module.webbrowser, "open", Mock(side_effect=AssertionError("Unexpected browser launch")))
    monkeypatch.setattr(help_module, "app_data", lambda: tmp_path / "測試資料 folder # %")
    monkeypatch.setattr(help_module.i18n, "language", lambda: "zh-Hant")
    yield help_module, messages
    for key in tuple(sys.modules):
        if key.startswith(name + "."):
            sys.modules.pop(key, None)


@pytest.mark.parametrize("language", ["zh-Hant", "en"])
def test_all_chapters_use_valid_local_uri_and_selected_language(tutorial, monkeypatch, language):
    module, messages = tutorial
    monkeypatch.setattr(module.i18n, "language", lambda: language)
    module.webbrowser.open.side_effect = None
    module.webbrowser.open.return_value = True
    parent = object()
    for section in sorted(module.SECTIONS):
        folder = module.open_tutorial(parent, section)
        assert folder is not None
        url = urlsplit(module.webbrowser.open.call_args.args[0])
        assert url.scheme == "file" and url.netloc == ""
        assert unquote(url.path) == unquote(urlsplit((folder / "START_HERE.html").resolve().as_uri()).path)
        assert parse_qs(url.query) == {"language": [language]}
        assert url.fragment == section
    messages.showinfo.assert_not_called()
    messages.showerror.assert_not_called()


def test_invalid_chapter_falls_back_to_start(tutorial):
    module, messages = tutorial
    module.webbrowser.open.side_effect = None
    module.webbrowser.open.return_value = True
    assert module.open_tutorial(section="unknown") is not None
    assert urlsplit(module.webbrowser.open.call_args.args[0]).fragment == "start"
    messages.showerror.assert_not_called()


def test_unavailable_browser_shows_local_path(tutorial):
    module, messages = tutorial
    module.webbrowser.open.side_effect = None
    module.webbrowser.open.return_value = False
    parent = object()
    folder = module.open_tutorial(parent, "first-case")
    assert folder is not None
    messages.showinfo.assert_called_once()
    assert str(folder / "START_HERE.html") in messages.showinfo.call_args.args[1]
    assert messages.showinfo.call_args.kwargs == {"parent": parent}
    messages.showerror.assert_not_called()


@pytest.mark.parametrize("failure", [OSError("launch failed"), RuntimeError("launch denied")])
def test_launch_failures_show_error_without_retry(tutorial, failure):
    module, messages = tutorial
    module.webbrowser.open.side_effect = failure
    parent = object()
    assert module.open_tutorial(parent) is None
    module.webbrowser.open.assert_called_once()
    messages.showerror.assert_called_once()
    assert str(failure) in messages.showerror.call_args.args[1]
    assert messages.showerror.call_args.kwargs == {"parent": parent}
    messages.showinfo.assert_not_called()


def test_browser_error_is_visible_instead_of_escaping_tk_callback(tutorial):
    module, messages = tutorial
    module.webbrowser.open.side_effect = module.webbrowser.Error("browser controller unavailable")
    assert module.open_tutorial() is None
    module.webbrowser.open.assert_called_once()
    messages.showerror.assert_called_once()
    assert "browser controller unavailable" in messages.showerror.call_args.args[1]
    messages.showinfo.assert_not_called()


def test_preparation_error_does_not_launch_browser(tutorial, monkeypatch):
    module, messages = tutorial
    monkeypatch.setattr(module, "prepare_tutorial", Mock(side_effect=zipfile.BadZipFile("corrupt archive")))
    assert module.open_tutorial() is None
    module.webbrowser.open.assert_not_called()
    messages.showerror.assert_called_once()


def test_frozen_resource_path_and_practice_preservation(tutorial, monkeypatch, tmp_path):
    module, messages = tutorial
    bundle = tmp_path / "Facility Studio 測試.app" / "Contents" / "Frameworks"
    package = bundle / "facility_studio"
    resources = package / "resources"
    resources.mkdir(parents=True)
    shutil.copyfile(Path(module.__file__).with_name("resources") / "beginner_tutorial.zip",
                    resources / "beginner_tutorial.zip")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(module, "__file__", str(package / "tutorial_help.py"))
    destination = tmp_path / "isolated-user-data"
    folder = module.prepare_tutorial(destination)
    assert {p.name for p in folder.iterdir()} == module.TUTORIAL_FILES
    assert (folder / "START_HERE.html").read_text(encoding="utf-8").startswith("<!doctype html>")
    practice = folder / "01_Practice_AHU.json"
    practice.write_text('{"preserve": "user practice"}', encoding="utf-8")
    assert module.prepare_tutorial(destination) == folder
    assert practice.read_text(encoding="utf-8") == '{"preserve": "user practice"}'
    module.webbrowser.open.assert_not_called()
