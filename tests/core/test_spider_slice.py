import pytest
import hashlib
from courier_core.spider_slice import (
    ResearchRequest, SpiderEngine, LedgerReceipt
)

def test_spider_end_to_end_flow_successful_match():
    # 1. RESEARCH REQUEST
    request = ResearchRequest(
        request_id="req-spider-01",
        query="api endpoint",
        target_source="local://dummy_docs.txt"
    )
    
    # 2. TEST SOURCE (offline, fake data)
    test_source = """
    Welcome to the docs.
    The main API endpoint is https://api.local/v1
    Please use a bearer token.
    """
    
    # Run the spider
    receipt: LedgerReceipt = SpiderEngine.run(request, test_source, now=1000.0)
    
    # 3. PROVENANCE Check
    expected_checksum = hashlib.sha256(test_source.encode('utf-8')).hexdigest()
    assert receipt.provenance.source_uri == "local://dummy_docs.txt"
    assert receipt.provenance.timestamp == 1000.0
    assert receipt.provenance.checksum == expected_checksum
    
    # 4. EXTRACTED RESULT
    assert receipt.extracted_result.confidence == 1.0
    assert "The main API endpoint is https://api.local/v1" in receipt.extracted_result.answer
    
    # 5. EVIDENCE
    assert receipt.evidence.raw_snippet == "The main API endpoint is https://api.local/v1"
    
    # 6. LEDGER-COMPATIBLE RECEIPT Check
    payload = receipt.to_ledger_payload()
    assert payload["event_type"] == "SPIDER_RESEARCH_COMPLETED"
    assert payload["request_id"] == "req-spider-01"
    assert payload["provenance"]["checksum"] == expected_checksum
    assert "https://api.local/v1" in payload["evidence"]["raw_snippet"]


def test_spider_end_to_end_flow_not_found():
    request = ResearchRequest(
        request_id="req-spider-02",
        query="quantum capacitor",
        target_source="local://hardware_specs.txt"
    )
    
    test_source = "CPU: 4 cores\nRAM: 16GB"
    
    receipt = SpiderEngine.run(request, test_source)
    
    assert receipt.extracted_result.answer == "NOT_FOUND"
    assert receipt.extracted_result.confidence == 0.0
    assert receipt.evidence.raw_snippet == ""
    
    payload = receipt.to_ledger_payload()
    assert payload["result"]["confidence"] == 0.0
    assert payload["evidence"]["raw_snippet"] == ""

