from dataclasses import dataclass
from typing import List, Dict
from enum import Enum

class MatchResult(str, Enum):
    MATCH = "MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    NO_MATCH = "NO_MATCH"
    UNKNOWN = "UNKNOWN"

@dataclass
class FailureFingerprint:
    fingerprint_id: str
    required_symptoms: List[str]
    required_os: str
    excluded_symptoms: List[str]

class FailureFingerprintMatcher:
    def __init__(self):
        self._known_fingerprints: Dict[str, FailureFingerprint] = {}
        
    def register_fingerprint(self, fp: FailureFingerprint):
        self._known_fingerprints[fp.fingerprint_id] = fp
        
    def match_incident(self, reported_os: str, reported_symptoms: List[str]) -> tuple[MatchResult, str]:
        """
        Conservatively matches a new incident against known fingerprints.
        Returns a tuple of (MatchResult, fingerprint_id)
        """
        if not reported_symptoms:
            return MatchResult.UNKNOWN, ""
            
        best_match_result = MatchResult.NO_MATCH
        best_match_id = ""
        
        for fp_id, fp in self._known_fingerprints.items():
            # 1. OS MUST match strictly.
            if fp.required_os != reported_os:
                continue
                
            # 2. Excluded symptoms immediately invalidate a match.
            # If the incident exhibits a symptom explicitly forbidden by the fingerprint, it's not a match.
            if any(sym in reported_symptoms for sym in fp.excluded_symptoms):
                continue
                
            # 3. Check for required symptoms
            matched_required = sum(1 for req in fp.required_symptoms if req in reported_symptoms)
            
            if matched_required == len(fp.required_symptoms):
                # If ALL required symptoms are present, it's a MATCH.
                # However, if there are extraneous symptoms, we must be careful.
                # For safety, if there are MORE reported symptoms than required,
                # it's a PARTIAL_MATCH because the extra symptoms could imply a different failure mode.
                if len(reported_symptoms) == len(fp.required_symptoms):
                    return MatchResult.MATCH, fp_id
                else:
                    best_match_result = MatchResult.PARTIAL_MATCH
                    best_match_id = fp_id
            
            elif matched_required > 0:
                # Only some required symptoms match
                best_match_result = MatchResult.PARTIAL_MATCH
                if not best_match_id:
                    best_match_id = fp_id
                    
        return best_match_result, best_match_id
