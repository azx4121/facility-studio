from pathlib import Path
from unittest.mock import patch
import pytest
from inspect_python_launch import inspect_launch_environment, NAMES

@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('folder', ['System32', 'System', ''])
def test_reports_reachable_alias_even_outside_path(tmp_path, name, folder):
    directory = tmp_path / folder; directory.mkdir(exist_ok=True)
    (directory / name).write_bytes(b'synthetic')
    safe = tmp_path / 'empty'; safe.mkdir()
    env = dict(SystemRoot=str(tmp_path), PATH=str(safe))
    with patch('inspect_python_launch.shutil.which', return_value=None):
        result = inspect_launch_environment(env)
    assert not result['path_and_implicit_directory_scan_passed']
    assert any(row['name'] == name for row in result['reachable_candidates'])
    assert result['machine_python_absence_claimed'] is False

@pytest.mark.parametrize('path', ['', '.', 'relative'])
def test_reject_relative_or_empty_path(path, tmp_path):
    result = inspect_launch_environment(dict(PATH=path, SystemRoot=str(tmp_path)))
    assert result['unsafe_path_entries']
    assert not result['path_and_implicit_directory_scan_passed']

def test_controller_cwd_resolution_is_explicit(tmp_path):
    with patch('inspect_python_launch.shutil.which', return_value='controller-only/python.exe'):
        result = inspect_launch_environment(dict(PATH=str(tmp_path), SystemRoot=str(tmp_path)))
    assert result['path_and_implicit_directory_scan_passed']
    assert result['controller_which']['python.exe'] == 'controller-only/python.exe'
    assert result['process_execution_policy_enforced'] is False
