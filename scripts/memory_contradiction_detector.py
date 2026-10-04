from dataclasses import dataclass
from typing import Dict, Any, List
import datetime

@dataclass
class ContradictionResult:
    contradiction: str
    source_a: str
    source_b: str
    freshness: str
    evidence_strength: str
    requires_reverify: str # "YES" or "NO"
    resolved_state: str = None # If resolution is possible

def detect_and_resolve_contradiction(record_a: Dict[str, Any], record_b: Dict[str, Any]) -> ContradictionResult:
    """
    Detects contradictions between two authoritative memory records about the same workkey.
    Returns structured details about the contradiction and resolves if evidence strongly points to one.
    """
    if record_a.get("workkey") != record_b.get("workkey"):
        return None # No contradiction if they are about different subjects
        
    state_a = record_a.get("state")
    state_b = record_b.get("state")
    
    if state_a == state_b:
        return None # No contradiction
        
    # We have a contradiction!
    contradiction_desc = f"Record A states {state_a} while Record B states {state_b} for {record_a.get('workkey')}."
    source_a = record_a.get("source", "Unknown A")
    source_b = record_b.get("source", "Unknown B")
    
    # Assess Freshness
    time_a = record_a.get("timestamp", "")
    time_b = record_b.get("timestamp", "")
    freshness = f"A: {time_a} | B: {time_b}"
    newer_record = "A" if time_a > time_b else "B" if time_b > time_a else "TIE"
    
    # Assess Evidence Strength
    prov_a = 1 if record_a.get("has_provenance") else 0
    prov_b = 1 if record_b.get("has_provenance") else 0
    strength = f"A has provenance: {bool(prov_a)} | B has provenance: {bool(prov_b)}"
    stronger_evidence = "A" if prov_a > prov_b else "B" if prov_b > prov_a else "TIE"
    
    # Determine reverification logic
    requires_reverify = "YES"
    resolved_state = None
    
    # If one has strict provenance and the other doesn't, we can cautiously resolve
    if stronger_evidence != "TIE" and newer_record == stronger_evidence:
        # The newer record is also the only one with provenance
        requires_reverify = "NO"
        resolved_state = state_a if stronger_evidence == "A" else state_b
    
    return ContradictionResult(
        contradiction=contradiction_desc,
        source_a=source_a,
        source_b=source_b,
        freshness=freshness,
        evidence_strength=strength,
        requires_reverify=requires_reverify,
        resolved_state=resolved_state
    )

def analyze_memory_for_contradictions(memory_records: List[Dict[str, Any]]) -> List[ContradictionResult]:
    contradictions = []
    
    # Group by workkey
    by_workkey = {}
    for r in memory_records:
        wk = r.get("workkey")
        if wk:
            if wk not in by_workkey:
                by_workkey[wk] = []
            by_workkey[wk].append(r)
            
    # Check for contradictions within same workkeys
    for wk, records in by_workkey.items():
        if len(records) > 1:
            # For simplicity, compare all pairs
            for i in range(len(records)):
                for j in range(i+1, len(records)):
                    result = detect_and_resolve_contradiction(records[i], records[j])
                    if result:
                        contradictions.append(result)
                        
    return contradictions
