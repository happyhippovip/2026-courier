import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


def test_empty_unproven_without_evidence_forbidden():
    # 2. empty UNPROVEN_EDGES without qualifying evidence => CANONICAL_ACCEPTED is forbidden
    bundle = {
        "revision": 1,
        "record": {
            "PROVEN_EDGES": [],
            "UNPROVEN_EDGES": ["test-edge"]
        },
        "acceptance_guard": {
            "binding": {"current_sha": "abc1234", "runtime_identity": "test"},
            "evidence": [],
            "acceptance_predicate": {"results": {"ISSUE_STATE": {}}}
        }
    }
    
    # Mock update to avoid actual file I/O or use a temporary file
    # We can just test the logic directly by examining what would be passed to update()

