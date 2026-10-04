import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from memory_freshness_check import MemoryClaim, MemoryFreshnessChecker

def test_memory_freshness_preserves_still_valid_claims():
    def mock_fetcher(command):
        if command == "get-version":
            return "v1.0"
        return ""
        
    claims = [
        MemoryClaim(
            id="c1", 
            content="Version is v1.0", 
            requires_freshness=True, 
            status="VERIFIED",
            expected_evidence_command="get-version",
            last_verified_value="v1.0"
        )
    ]
    
    checker = MemoryFreshnessChecker(claims, mock_fetcher)
    result = checker.verify_freshness()
    
    assert result[0].status == "VERIFIED"
    assert "Version is v1.0" in result[0].content

def test_memory_freshness_marks_stale_claims_superseded():
    def mock_fetcher(command):
        if command == "get-version":
            return "v2.0" # Version changed locally!
        return ""
        
    claims = [
        MemoryClaim(
            id="c1", 
            content="Version is v1.0", 
            requires_freshness=True, 
            status="VERIFIED",
            expected_evidence_command="get-version",
            last_verified_value="v1.0"
        )
    ]
    
    checker = MemoryFreshnessChecker(claims, mock_fetcher)
    result = checker.verify_freshness()
    
    assert result[0].status == "SUPERSEDED"
    assert "[STALE]" in result[0].content
    assert "Current Truth: v2.0" in result[0].content

def test_skips_claims_not_requiring_freshness():
    def mock_fetcher(command):
        return "different"
        
    claims = [
        MemoryClaim(
            id="c1", 
            content="Historical note", 
            requires_freshness=False, 
            status="VERIFIED",
            expected_evidence_command="get-version",
            last_verified_value="old"
        )
    ]
    
    checker = MemoryFreshnessChecker(claims, mock_fetcher)
    result = checker.verify_freshness()
    
    assert result[0].status == "VERIFIED"
