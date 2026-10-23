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


def test_gate_unlocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    with patch("scripts.build_product_shell.Path.resolve") as mock_resolve:
        mock_resolve.return_value = tmp_path / "scripts" / "build_product_shell.py"
        
        gate_file = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
        gate_file.parent.mkdir(parents=True, exist_ok=True)
        gate_file.write_text("Stuff... PRODUCT_SHELL_UNLOCKED=YES ... stuff", encoding="utf-8")
        
        assert build_product_shell() == 0


def test_gate_does_not_follow_a_symlink(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("scripts.build_product_shell.Path.resolve") as mock_resolve:
        mock_resolve.return_value = tmp_path / "scripts" / "build_product_shell.py"
        outside = tmp_path / "outside.md"
        outside.write_text("PRODUCT_SHELL_UNLOCKED=YES\n", encoding="utf-8")
        gate = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
        gate.parent.mkdir(parents=True)
        gate.symlink_to(outside)

        outside_dir = tmp_path / "outside-dir"
        outside_dir.mkdir()
        nested = outside_dir / "PILOT_READINESS_DECLARATION.md"
        nested.write_text("PRODUCT_SHELL_UNLOCKED=YES\n", encoding="utf-8")
        parent_root = tmp_path / "parent-case"
        ops = parent_root / "ops"
        ops.mkdir(parents=True)
        (ops / "ai").symlink_to(outside_dir)

        code_file = build_product_shell()
        out_file = capsys.readouterr().out
        mock_resolve.return_value = parent_root / "scripts" / "build_product_shell.py"
        code_parent = build_product_shell()
        out_parent = capsys.readouterr().out

    assert (
        code_file == 1 and "refusing to follow a symlink" in out_file and "Completed skeleton" not in out_file
        and code_parent == 1 and "refusing to follow a symlink" in out_parent and "Completed skeleton" not in out_parent
        and gate.is_symlink() and (ops / "ai").is_symlink()
        and outside.read_text(encoding="utf-8") == "PRODUCT_SHELL_UNLOCKED=YES\n"
    ), (code_file, out_file, code_parent, out_parent)

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
                assert e.code == 0
