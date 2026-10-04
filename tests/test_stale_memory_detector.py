import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from stale_memory_detector import StaleMemoryDetector

def get_mock_fetchers():
    return {
        "current_pr_head": lambda: "commit-new-pr",
        "branch_head_sha": lambda: "commit-new-branch",
        "current_binary_hash": lambda: "hash-new-binary",
        "current_timestamp": lambda: "2026-10-03T14:00:00Z",
        "current_active_blockers": lambda: ["BLOCKER-2", "BLOCKER-3"]
    }

def test_detect_stale_pr_head():
    detector = StaleMemoryDetector(get_mock_fetchers())
    
    res = detector.evaluate_claim({"pr_head": "commit-old-pr"})
    assert res.is_stale is True
    assert "Stored PR head" in res.reason
    
    res_valid = detector.evaluate_claim({"pr_head": "commit-new-pr"})
    assert res_valid.is_stale is False

def test_detect_stale_sha():
    detector = StaleMemoryDetector(get_mock_fetchers())
    
    res = detector.evaluate_claim({"sha": "commit-old-branch"})
    assert res.is_stale is True
    assert "Stored SHA" in res.reason
    
    res_valid = detector.evaluate_claim({"sha": "commit-new-branch"})
    assert res_valid.is_stale is False

def test_detect_stale_binary_hash():
    detector = StaleMemoryDetector(get_mock_fetchers())
    
    res = detector.evaluate_claim({"binary_hash": "hash-old-binary"})
    assert res.is_stale is True
    assert "older binary" in res.reason
    
    res_valid = detector.evaluate_claim({"binary_hash": "hash-new-binary"})
    assert res_valid.is_stale is False

def test_detect_expired_writer_ownership():
    detector = StaleMemoryDetector(get_mock_fetchers())
    
    # 5 hours ago relative to current_timestamp (14:00:00Z)
    res = detector.evaluate_claim({"writer_timestamp": "2026-10-03T09:00:00Z"})
    assert res.is_stale is True
    assert "ownership expired" in res.reason
    
    # 2 hours ago
    res_valid = detector.evaluate_claim({"writer_timestamp": "2026-10-03T12:00:00Z"})
    assert res_valid.is_stale is False

def test_detect_disappeared_blocker():
    detector = StaleMemoryDetector(get_mock_fetchers())
    
    res = detector.evaluate_claim({"blocker_id": "BLOCKER-1"})
    assert res.is_stale is True
    assert "no longer in active blockers" in res.reason
    
    res_valid = detector.evaluate_claim({"blocker_id": "BLOCKER-2"})
    assert res_valid.is_stale is False
