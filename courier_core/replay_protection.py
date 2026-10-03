import hashlib
from typing import Set

class ReplayProtectionGuard:
    """MAC-05: Detect and reject unsafe duplicate side effects."""
    def __init__(self):
        self._seen_signatures: Set[str] = set()

    def generate_signature(self, action_name: str, payload_str: str) -> str:
        data = f"{action_name}::{payload_str}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def check_and_record(self, action_name: str, payload_str: str) -> bool:
        """Returns True if safe to proceed, False if this is a replay."""
        sig = self.generate_signature(action_name, payload_str)
        if sig in self._seen_signatures:
            return False
        self._seen_signatures.add(sig)
        return True
