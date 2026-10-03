from dataclasses import dataclass
from courier_core.snapshot_level_0 import SnapshotLevel0

@dataclass
class IdentityBoundSnapshot:
    """WK-11: Bind process/start-time/workkey/session identity."""
    workkey: str
    session_id: str
    owner_process_id: int
    l0_state: SnapshotLevel0

    def verify_binding(self, expected_workkey: str, expected_session: str) -> bool:
        return self.workkey == expected_workkey and self.session_id == expected_session
