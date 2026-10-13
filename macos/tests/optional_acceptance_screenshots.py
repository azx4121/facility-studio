"""Exercise optional screenshot failures without Tk or real screen capture.

The AST extraction runs the source helper, the language acceptance footer and
the nested usability capture callback directly, while avoiding their unrelated
GUI dependencies. No Pillow screen-grab implementation is imported.
"""

import ast
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


REPOSITORY = Path(__file__).resolve().parents[2]
SETTING = "FACILITY_STUDIO_ACCEPTANCE_SCREENSHOTS"
SOURCES = [
    REPOSITORY / platform / "facility_studio" / filename
    for platform in ("macos", "windows")
    for filename in ("language_acceptance.py", "usability_acceptance.py")
]


def source_namespace(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    helper = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_capture_optional_screenshot"
    )
    namespace = {"os": os, "subprocess": subprocess, "Path": Path}
    module = ast.Module(body=[helper], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return tree, namespace


def fake_pillow(grab):
    pillow = ModuleType("PIL")
    pillow.ImageGrab = SimpleNamespace(grab=grab)
    return patch.dict(sys.modules, {"PIL": pillow})


class OptionalAcceptanceScreenshots(unittest.TestCase):
    def test_permission_denied_reports_optional_evidence_and_returns(self):
        for path in SOURCES:
            with self.subTest(path=str(path)):
                _, namespace = source_namespace(path)
                denied = subprocess.CalledProcessError(
                    1, ["screencapture", "-x", "evidence.png"],
                    stderr="could not create image from display",
                )
                grab = Mock(side_effect=denied)
                warning = io.StringIO()
                with patch.dict(os.environ), fake_pillow(grab), redirect_stdout(warning):
                    os.environ.pop(SETTING, None)
                    self.assertFalse(namespace["_capture_optional_screenshot"](Path("evidence.png")))
                grab.assert_called_once_with()
                self.assertIn("Optional acceptance screenshot unavailable:", warning.getvalue())

    def test_disabled_screenshots_never_call_image_grab(self):
        for path in SOURCES:
            with self.subTest(path=str(path)):
                _, namespace = source_namespace(path)
                grab = Mock(side_effect=AssertionError("A disabled capture was attempted"))
                warning = io.StringIO()
                with patch.dict(os.environ, {SETTING: "0"}), fake_pillow(grab), redirect_stdout(warning):
                    self.assertFalse(namespace["_capture_optional_screenshot"](Path("evidence.png")))
                grab.assert_not_called()
                self.assertIn("Optional acceptance screenshot disabled:", warning.getvalue())

    def test_default_still_saves_optional_image(self):
        for path in SOURCES:
            with self.subTest(path=str(path)):
                _, namespace = source_namespace(path)
                image = Mock()
                grab = Mock(return_value=image)
                destination = Path("evidence.png")
                with patch.dict(os.environ), fake_pillow(grab):
                    os.environ.pop(SETTING, None)
                    self.assertTrue(namespace["_capture_optional_screenshot"](destination))
                grab.assert_called_once_with()
                image.save.assert_called_once_with(destination)

    def test_unrelated_assertion_failure_is_not_hidden(self):
        for path in SOURCES:
            with self.subTest(path=str(path)):
                _, namespace = source_namespace(path)
                grab = Mock(side_effect=AssertionError("Unexpected acceptance failure"))
                with patch.dict(os.environ), fake_pillow(grab):
                    os.environ.pop(SETTING, None)
                    with self.assertRaisesRegex(AssertionError, "Unexpected acceptance failure"):
                        namespace["_capture_optional_screenshot"](Path("evidence.png"))

    def test_language_acceptance_continues_to_language_restore_after_denial(self):
        for path in SOURCES:
            if path.name != "language_acceptance.py":
                continue
            with self.subTest(path=str(path)):
                tree, namespace = source_namespace(path)
                run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run")
                wrapper = ast.parse("def finish(pump, app, output, choose):\n    pass\n").body[0]
                wrapper.body = run.body[-2:]
                module = ast.Module(body=[wrapper], type_ignores=[])
                exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
                grab = Mock(side_effect=subprocess.CalledProcessError(1, "screencapture"))
                choose, pump, app = Mock(), Mock(), Mock()
                with patch.dict(os.environ), fake_pillow(grab), redirect_stdout(io.StringIO()):
                    os.environ.pop(SETTING, None)
                    namespace["finish"](pump, app, Path("Mac_Acceptance.json"), choose)
                self.assertEqual(grab.call_count, 2)
                self.assertEqual(pump.call_count, 2)
                app.show_tool.assert_called_once_with("air")
                choose.assert_called_once_with("zh-Hant")

    def test_disabled_capture_retains_windows_repaint_validation(self):
        path = REPOSITORY / "windows/facility_studio/usability_acceptance.py"
        tree, namespace = source_namespace(path)
        run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run")
        capture = next(node for node in run.body if isinstance(node, ast.FunctionDef) and node.name == "capture")
        module = ast.Module(body=[capture], type_ignores=[])
        with tempfile.TemporaryDirectory(prefix="facility-screenshot-regression-") as directory:
            namespace.update(output=Path(directory), pump=Mock())
            exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
            window = Mock()
            window._native_redraw.repaint.return_value = False
            grab = Mock(side_effect=AssertionError("A disabled capture was attempted"))
            with patch.dict(os.environ, {SETTING: "0"}), fake_pillow(grab):
                with self.assertRaisesRegex(AssertionError, "Windows client repaint failed"):
                    namespace["capture"](window, "V556_Workbench_Basic.png")
            grab.assert_not_called()
            window._native_redraw.repaint.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
