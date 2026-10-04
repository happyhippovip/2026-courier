import pytest
from pathlib import Path

def setup_dummy_files(tmp_path):
    files = [
        'build_channel_workflow_tasks.py',
        'resource_policy.py',
        'run_demo_workflow.py',
        'run_content_production_pipeline.py',
        'run_codex_bridge.py',
        'run_bodyguards.py',
        'run_antigravity_bridge.py',
    ]
    for f in files:
        (tmp_path / f).write_text("dummy content", encoding="utf-8")
    return files


def test_script_execution_no_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_dummy_files(tmp_path)
    
    import runpy
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "fix_save_json.py"))
    # If it runs without raising exception, it passed


def test_regex_replacement_with_dumps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_dummy_files(tmp_path)
    
    target = tmp_path / "resource_policy.py"
    target.write_text("""
def save_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(path)
""", encoding="utf-8")
    
    import runpy
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "fix_save_json.py"))
    
    new_content = target.read_text(encoding="utf-8")
    assert "temp.unlink()" in new_content
    assert "temp.replace(path)" in new_content
    assert "temp.write_text(json.dumps(data, indent=2), encoding=\"utf-8\")" in new_content


def test_regex_replacement_no_dumps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_dummy_files(tmp_path)
    
    target = tmp_path / "run_bodyguards.py"
    target.write_text("""
def save_json(path: Path, some_str: str) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(some_str, encoding="utf-8")
    temp.replace(path)
""", encoding="utf-8")
    
    import runpy
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "fix_save_json.py"))
    
    new_content = target.read_text(encoding="utf-8")
    assert "temp.write_text(some_str, encoding=\"utf-8\")" in new_content
    assert "temp.unlink()" in new_content


def test_unmatching_signature(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_dummy_files(tmp_path)
    
    target = tmp_path / "run_codex_bridge.py"
    target.write_text("""
def save_json(path: Path, data) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    temp.replace(path)
""", encoding="utf-8")
    
    import runpy
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "fix_save_json.py"))
    
    new_content = target.read_text(encoding="utf-8")
    # Should not be replaced because `data` lacks type hint `data: dict`
    assert "temp.unlink()" not in new_content


def test_unmatching_write_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_dummy_files(tmp_path)
    
    target = tmp_path / "run_demo_workflow.py"
    target.write_text("""
def save_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data)) # Missing encoding="utf-8"
    temp.replace(path)
""", encoding="utf-8")
    
    import runpy
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "fix_save_json.py"))
    
    new_content = target.read_text(encoding="utf-8")
    # Should not be replaced
    assert "temp.unlink()" not in new_content
