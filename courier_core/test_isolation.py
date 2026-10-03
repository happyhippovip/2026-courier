import os
from typing import Dict, Set

class TestIsolationEnforcer:
    """MAC-29: Detect hidden environmental coupling and shared-state leakage."""
    def __init__(self):
        self._initial_env_keys: Set[str] = set(os.environ.keys())
        self._forbidden_shared_state = False

    def snapshot_env(self) -> Set[str]:
        return set(os.environ.keys())

    def detect_leakage(self, current_env_keys: Set[str]) -> Set[str]:
        return current_env_keys - self._initial_env_keys

    def enforce_isolation(self, pre_test_env: Set[str], post_test_env: Set[str]) -> bool:
        leaked_keys = post_test_env - pre_test_env
        if leaked_keys:
            return False
        return True
