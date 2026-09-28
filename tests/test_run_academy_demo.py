import pytest
from pathlib import Path

def test_run_academy_demo(tmp_path, monkeypatch):
    import scripts.run_academy_demo as script
    
    # Mocking dependencies
    class MockTeacher:
        def __init__(self, *args, **kwargs):
            pass
        def propose_lesson(self, *args, **kwargs):
            return {"lesson_id": "l-1", "novelty_hash": "abcd"}
        def queue_or_deliver_lesson(self, *args, **kwargs):
            return {"delivery_id": "d-1", "status": "DELIVERED"}
            
    class MockDirector:
        def __init__(self, *args, **kwargs):
            pass
        def check_attendance(self):
            pass
        def review_lesson(self, *args, **kwargs):
            return {"status": "APPROVED_FOR_TEST"}
        def evaluate_lesson(self, *args, **kwargs):
            return {"verdict": "PASS", "metrics": {"measured_minutes_saved": 5}}
        def approve_adoption(self, *args, **kwargs):
            return {"adoption_id": "a-1"}
        def record_worker_acknowledgement(self, *args, **kwargs):
            return {"adoption_status": "ACKNOWLEDGED"}
            
    class MockSteward:
        def __init__(self, *args, **kwargs):
            pass
        def get_latest_snapshot(self):
            if not hasattr(self, "_called"):
                self._called = True
                return {"context_version": 1}
            return {"context_version": 2, "snapshot_hash": "hash123"}
            
    monkeypatch.setattr(script, "AcademyTeacher", MockTeacher)
    monkeypatch.setattr(script, "AcademyDirector", MockDirector)
    monkeypatch.setattr(script, "UpdateSteward", MockSteward)
    
    res = script.run_academy_demo()
    
    assert res["status"] == "COMPLETED"
    assert res["lesson_id"] == "l-1"
    assert res["context_version_after"] == 2
    assert res["eval_verdict"] == "PASS"

