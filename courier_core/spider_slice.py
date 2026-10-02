import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class ResearchRequest:
    request_id: str
    query: str
    target_source: str

@dataclass(frozen=True)
class Provenance:
    source_uri: str
    timestamp: float
    checksum: str

@dataclass(frozen=True)
class ExtractedResult:
    answer: str
    confidence: float

@dataclass(frozen=True)
class Evidence:
    raw_snippet: str

@dataclass(frozen=True)
class LedgerReceipt:
    request_id: str
    provenance: Provenance
    extracted_result: ExtractedResult
    evidence: Evidence

    def to_ledger_payload(self) -> Dict[str, Any]:
        """Formats the object into a dict suitable for appending to the Courier Journal."""
        return {
            "event_type": "SPIDER_RESEARCH_COMPLETED",
            "request_id": self.request_id,
            "provenance": {
                "uri": self.provenance.source_uri,
                "timestamp": self.provenance.timestamp,
                "checksum": self.provenance.checksum
            },
            "result": {
                "answer": self.extracted_result.answer,
                "confidence": self.extracted_result.confidence
            },
            "evidence": {
                "raw_snippet": self.evidence.raw_snippet
            }
        }

class SpiderEngine:
    """
    Offline Spider deterministic flow verifying:
    RESEARCH REQUEST -> TEST SOURCE -> PROVENANCE -> EXTRACTED RESULT -> EVIDENCE -> LEDGER-COMPATIBLE RECEIPT
    """
    
    @staticmethod
    def run(request: ResearchRequest, test_source: str, now: float = None) -> LedgerReceipt:
        timestamp = now if now is not None else time.time()
        
        # PROVENANCE
        checksum = hashlib.sha256(test_source.encode('utf-8')).hexdigest()
        provenance = Provenance(
            source_uri=request.target_source,
            timestamp=timestamp,
            checksum=checksum
        )
        
        # EXTRACTED RESULT & EVIDENCE
        # Deterministic dummy extraction: scan lines for the query string
        extracted_answer = "NOT_FOUND"
        evidence_snippet = ""
        
        for line in test_source.splitlines():
            if request.query.lower() in line.lower():
                extracted_answer = f"Found match: {line.strip()}"
                evidence_snippet = line.strip()
                break
                
        result = ExtractedResult(
            answer=extracted_answer, 
            confidence=1.0 if extracted_answer != "NOT_FOUND" else 0.0
        )
        evidence = Evidence(raw_snippet=evidence_snippet)
        
        # LEDGER-COMPATIBLE RECEIPT
        return LedgerReceipt(
            request_id=request.request_id,
            provenance=provenance,
            extracted_result=result,
            evidence=evidence
        )
