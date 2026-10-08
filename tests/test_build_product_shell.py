import sys
from pathlib import Path
from unittest.mock import patch
from scripts.build_product_shell import build_product_shell


def test_gate_locked_file_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    with patch("scripts.build_product_shell.Path.resolve") as mock_resolve:
        mock_resolve.return_value = tmp_path / "scripts" / "build_product_shell.py"
        
        # File doesn't exist
        assert build_product_shell() == 1


def test_gate_locked_file_present_no_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    with patch("scripts.build_product_shell.Path.resolve") as mock_resolve:
        mock_resolve.return_value = tmp_path / "scripts" / "build_product_shell.py"
        
        gate_file = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
        gate_file.parent.mkdir(parents=True, exist_ok=True)
        gate_file.write_text("Some other content without the flag", encoding="utf-8")
        
        assert build_product_shell() == 1


def test_gate_unlocked_without_artifact_is_not_verified(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch("scripts.build_product_shell.Path.resolve") as mock_resolve:
        mock_resolve.return_value = tmp_path / "scripts" / "build_product_shell.py"

        gate_file = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
        gate_file.parent.mkdir(parents=True, exist_ok=True)
        gate_file.write_text("Stuff... PRODUCT_SHELL_UNLOCKED=YES ... stuff", encoding="utf-8")

        assert build_product_shell() != 0
        assert "Completed skeleton verification successfully" not in capsys.readouterr().out


def test_gate_unlocked_with_artifact(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch("scripts.build_product_shell.Path.resolve") as mock_resolve:
        mock_resolve.return_value = tmp_path / "scripts" / "build_product_shell.py"

        gate_file = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
        gate_file.parent.mkdir(parents=True, exist_ok=True)
        gate_file.write_text("Stuff... PRODUCT_SHELL_UNLOCKED=YES ... stuff", encoding="utf-8")
        artifact = tmp_path / "dist" / "courier-product-shell"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"product-shell")

        assert build_product_shell() == 0
        assert "Completed skeleton verification successfully" in capsys.readouterr().out


def test_main(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    with patch("sys.argv", ["build_product_shell.py"]):
        with patch("pathlib.Path.resolve") as mock_resolve:
            mock_resolve.return_value = tmp_path / "scripts" / "build_product_shell.py"
            
            gate_file = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
            gate_file.parent.mkdir(parents=True, exist_ok=True)
            gate_file.write_text("Stuff... PRODUCT_SHELL_UNLOCKED=YES ... stuff", encoding="utf-8")
            
            import runpy
            try:
                runpy.run_path(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))), "scripts", "build_product_shell.py"), run_name="__main__")
            except SystemExit as e:
                assert e.code not in (0, None)
