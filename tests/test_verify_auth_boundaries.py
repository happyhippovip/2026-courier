import sys
import json
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path
import runpy

from scripts.verify_auth_boundaries import verify_auth_boundaries

def run_script():
    repo_root = str(Path(__file__).resolve().parent.parent)
    script_path = Path(repo_root) / "scripts" / "verify_auth_boundaries.py"
    
    with patch("sys.exit", side_effect=SystemExit) as m_exit:
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit:
            pass
        return m_exit

def test_verify_auth_boundaries_success(capsys):
    mock_content = "def init():\n    if VERIFIER_API_KEY == API_KEY:\n        raise ValueError('Must be different')\n"
    
    with patch("builtins.open", mock_open(read_data=mock_content)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "AUTH BOUNDARIES VALID" in captured.out
    m_exit.assert_called_once_with(0)

def test_verify_auth_boundaries_failure(capsys):
    mock_content = "def init():\n    pass\n"
    
    with patch("builtins.open", mock_open(read_data=mock_content)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "AUTH BOUNDARIES FAILED:" in captured.out
    assert "server/app.py does not prevent VERIFIER_API_KEY from being the same as API_KEY." in captured.out
    m_exit.assert_called_once_with(1)


def test_auth_boundary_does_not_follow_a_symlink(tmp_path, monkeypatch, capsys):
    outside_text = "VERIFIER_API_KEY == API_KEY\nSECRET-APP\n"

    def run(root):
        monkeypatch.chdir(root)
        try:
            verify_auth_boundaries()
            err = None
        except ValueError as exc:
            err = str(exc)
        except SystemExit as exc:
            err = exc.code
        return err, capsys.readouterr().out

    file_root = tmp_path / "file-case"
    file_root.mkdir()
    outside = tmp_path / "outside-app.py"
    outside.write_text(outside_text, encoding="utf-8")
    app = file_root / "server" / "app.py"
    app.parent.mkdir(parents=True)
    app.symlink_to(outside)
    file_err, file_out = run(file_root)

    parent_root = tmp_path / "parent-case"
    parent_root.mkdir()
    outside_dir = tmp_path / "outside-server"
    outside_dir.mkdir()
    (outside_dir / "app.py").write_text(outside_text, encoding="utf-8")
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    (parent_root / "server").symlink_to(outside_dir)
    parent_err, parent_out = run(parent_root)
    names = sorted(path.name for path in outside_dir.iterdir())
    assert (
        file_err,
        "AUTH BOUNDARIES VALID" in file_out,
        parent_err,
        "AUTH BOUNDARIES VALID" in parent_out,
        "SECRET-APP" in outside.read_text(encoding="utf-8"),
        names,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        True,
        ["app.py", "keep.txt"],
    )
