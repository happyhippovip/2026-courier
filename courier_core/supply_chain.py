from typing import Dict
import hashlib

class BundleVerifier:
    """WK-05: Verify runtime bundle dependencies and reproducibility."""
    @staticmethod
    def verify_manifest(manifest: Dict[str, str], actual_files: Dict[str, bytes]) -> bool:
        for filepath, expected_hash in manifest.items():
            if filepath not in actual_files:
                return False
            actual_hash = hashlib.sha256(actual_files[filepath]).hexdigest()
            if actual_hash != expected_hash:
                return False
        return True
