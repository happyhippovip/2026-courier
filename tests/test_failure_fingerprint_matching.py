import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from failure_fingerprint_matching import FailureFingerprintMatcher, FailureFingerprint, MatchResult

def setup_matcher():
    matcher = FailureFingerprintMatcher()
    matcher.register_fingerprint(
        FailureFingerprint(
            fingerprint_id="WIN_UAC_DEADLOCK",
            required_os="windows",
            required_symptoms=["Process frozen", "CPU at 0%", "No logs"],
            excluded_symptoms=["Access Denied error output", "Out of Memory"]
        )
    )
    return matcher

def test_match_result_is_exact_match():
    matcher = setup_matcher()
    result, fp_id = matcher.match_incident(
        reported_os="windows",
        reported_symptoms=["Process frozen", "CPU at 0%", "No logs"]
    )
    assert result == MatchResult.MATCH
    assert fp_id == "WIN_UAC_DEADLOCK"

def test_match_result_partial_due_to_extra_symptoms():
    matcher = setup_matcher()
    result, fp_id = matcher.match_incident(
        reported_os="windows",
        reported_symptoms=["Process frozen", "CPU at 0%", "No logs", "Unexpected blue screen"]
    )
    # Even though all required symptoms are there, the extra symptom implies a potentially different failure.
    # Therefore, it is conservative and returns PARTIAL_MATCH.
    assert result == MatchResult.PARTIAL_MATCH
    assert fp_id == "WIN_UAC_DEADLOCK"

def test_no_match_due_to_excluded_symptom():
    matcher = setup_matcher()
    result, fp_id = matcher.match_incident(
        reported_os="windows",
        reported_symptoms=["Process frozen", "CPU at 0%", "No logs", "Access Denied error output"]
    )
    # The excluded symptom completely invalidates the match.
    assert result == MatchResult.NO_MATCH

def test_no_match_due_to_wrong_os():
    matcher = setup_matcher()
    result, fp_id = matcher.match_incident(
        reported_os="linux",
        reported_symptoms=["Process frozen", "CPU at 0%", "No logs"]
    )
    assert result == MatchResult.NO_MATCH

def test_unknown_when_no_symptoms_provided():
    matcher = setup_matcher()
    result, fp_id = matcher.match_incident(
        reported_os="windows",
        reported_symptoms=[]
    )
    assert result == MatchResult.UNKNOWN
