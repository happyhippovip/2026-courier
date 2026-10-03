from dataclasses import dataclass
from typing import List, Dict

@dataclass
class GoldenTestResult:
    test_id: str
    passed: bool
    is_deterministic: bool

class GoldenIntegrityRunner:
    """WK-02: Golden checks and isolate deterministic failures."""
    @staticmethod
    def evaluate_results(results: List[GoldenTestResult]) -> Dict[str, List[str]]:
        isolated_failures = []
        flaky_failures = []
        
        for res in results:
            if not res.passed:
                if res.is_deterministic:
                    isolated_failures.append(res.test_id)
                else:
                    flaky_failures.append(res.test_id)
                    
        return {
            "deterministic_failures": isolated_failures,
            "flaky_failures": flaky_failures,
            "integrity_status": "PASS" if not isolated_failures and not flaky_failures else "FAIL"
        }
