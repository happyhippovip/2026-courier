import pytest
from pathlib import Path
import json

def test_propose_lesson(tmp_path, monkeypatch):
    import scripts.run_academy as script
    
    events_dir = tmp_path / "events/academy"
    events_dir.mkdir(parents=True)
    monkeypatch.setattr(script, "COURIER_DIR", tmp_path)
    
    teacher = script.AcademyTeacher(repo_dir=tmp_path, memory_dir=tmp_path)
    
    lesson = teacher.propose_lesson(
        topic="Error Handling",
        title="Avoid Bare Excepts",
        summary="Use specific exceptions.",
        target_agent="linux",
        impact_area="code_quality",
        source="code_review"
    )
    
    assert lesson["status"] == "PROPOSED"
    assert lesson["target_agent"] == "linux"
    
    # Check novelty hash exists
    assert "novelty_hash" in lesson
    
def test_approve_adoption(tmp_path, monkeypatch):
    import scripts.run_academy as script
    
    events_dir = tmp_path / "events/academy"
    events_dir.mkdir(parents=True)
    
    lessons_dir = tmp_path / "lessons"
    lessons_dir.mkdir()
    monkeypatch.setattr(script, "LESSONS_DIR", lessons_dir)
    
    lesson_file = lessons_dir / "l-2.json"
    lesson_file.write_text(json.dumps({
        "lesson_id": "l-2",
        "topic": "test",
        "status": "EVAL_PASS"
    }))
    
    director = script.AcademyDirector(repo_dir=tmp_path, memory_dir=tmp_path)
    
    # Needs a mock steward
    class MockSteward:
        def update_visual_state(self, *args, **kwargs):
            pass
            
    director.steward = MockSteward()
    director.update_visual_state = lambda *args, **kwargs: None
    
    approval = director.approve_adoption("l-2")
    
    assert approval["verdict"] == "APPROVED"
    assert json.loads(lesson_file.read_text())["status"] == "ADOPTED"
