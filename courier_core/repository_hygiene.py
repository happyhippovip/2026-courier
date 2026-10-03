import os
from typing import List

class HygieneScanner:
    """WK-04: Detect inappropriate runtime/session/history artifacts."""
    FORBIDDEN_FILES = {".DS_Store", "controller.token.bak", "id_rsa", "courier_crash.dump"}
    FORBIDDEN_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}

    def scan(self, root_dir: str) -> List[str]:
        violations = []
        for root, dirs, files in os.walk(root_dir):
            # Check directories
            for d in dirs:
                if d in self.FORBIDDEN_DIRS:
                    violations.append(os.path.join(root, d))
            
            # Check files
            for f in files:
                if f in self.FORBIDDEN_FILES:
                    violations.append(os.path.join(root, f))
        return violations
