import pytest
from pathlib import Path
import json

def test_evaluate_lesson_pass(tmp_path, monkeypatch):
    import scripts.run_academy as script
    
    # Mock dirs
    lessons_dir = tmp_path / "lessons"
    evals_dir = tmp_path / "evals"
    lessons_dir.mkdir()
    evals_dir.mkdir()
    
    monkeypatch.setattr(script, "LESSONS_DIR", lessons_dir)
    monkeypatch.setattr(script, "EVALS_DIR", evals_dir)
    
    # Needs a lesson file
    lesson_file = lessons_dir / "l-1.json"
    lesson_file.write_text(json.dumps({}))
    
    class MockDirector(script.AcademyDirector):
        def update_visual_state(self, *args, **kwargs):
            pass
            
    director = MockDirector()
    
    base_metrics = {"runtime_seconds": 20.0, "error_count": 1, "test_pass_rate": 0.9}
    cand_metrics = {"runtime_seconds": 10.0, "error_count": 0, "test_pass_rate": 1.0}
    
    eval_rec = director.evaluate_lesson("l-1", base_metrics, cand_metrics)
    
    assert eval_rec["verdict"] == "PASS"
    assert eval_rec["metrics"]["measured_minutes_saved"] > 0
    
    assert json.loads(lesson_file.read_text())["status"] == "EVAL_PASS"

def test_evaluate_lesson_fail(tmp_path, monkeypatch):
    import scripts.run_academy as script
    
    lessons_dir = tmp_path / "lessons"
    evals_dir = tmp_path / "evals"
    lessons_dir.mkdir()
    evals_dir.mkdir()
    
    monkeypatch.setattr(script, "LESSONS_DIR", lessons_dir)
    monkeypatch.setattr(script, "EVALS_DIR", evals_dir)
    
    lesson_file = lessons_dir / "l-1.json"
    lesson_file.write_text(json.dumps({}))
    
    class MockDirector(script.AcademyDirector):
        def update_visual_state(self, *args, **kwargs):
            pass
            
    director = MockDirector()
    
    base_metrics = {"runtime_seconds": 20.0, "error_count": 0, "test_pass_rate": 1.0}
    cand_metrics = {"runtime_seconds": 10.0, "error_count": 1, "test_pass_rate": 1.0}
    
    eval_rec = director.evaluate_lesson("l-1", base_metrics, cand_metrics)
    
    # Fails because error_count increased
    assert eval_rec["verdict"] == "FAIL"
    assert json.loads(lesson_file.read_text())["status"] == "EVAL_FAIL"

