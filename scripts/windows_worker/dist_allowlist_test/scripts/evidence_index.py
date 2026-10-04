from dataclasses import dataclass
from typing import List, Dict, Set, Optional

@dataclass
class EvidenceReference:
    """
    Lightweight reference pointing to the actual evidence payload on disk or in a blob store,
    containing just enough metadata to be indexed and verified.
    """
    evidence_id: str
    payload_uri: str # e.g. "file:///path/to/payload.json" or "s3://bucket/..."
    checksum: str # Integrity metadata
    
    # Indexed attributes
    workkey: Optional[str] = None
    component: Optional[str] = None
    sha: Optional[str] = None
    host: Optional[str] = None
    os: Optional[str] = None
    test: Optional[str] = None
    incident: Optional[str] = None
    readiness_criterion: Optional[str] = None


class EvidenceIndex:
    def __init__(self):
        self._references: Dict[str, EvidenceReference] = {}
        
        # Indexes
        self._by_workkey: Dict[str, Set[str]] = {}
        self._by_component: Dict[str, Set[str]] = {}
        self._by_sha: Dict[str, Set[str]] = {}
        self._by_host: Dict[str, Set[str]] = {}
        self._by_os: Dict[str, Set[str]] = {}
        self._by_test: Dict[str, Set[str]] = {}
        self._by_incident: Dict[str, Set[str]] = {}
        self._by_readiness_criterion: Dict[str, Set[str]] = {}

    def _add_to_index(self, index: Dict[str, Set[str]], key: Optional[str], ev_id: str):
        if key:
            if key not in index:
                index[key] = set()
            index[key].add(ev_id)

    def register(self, ref: EvidenceReference):
        """Registers an evidence reference into the searchable index without storing the payload."""
        self._references[ref.evidence_id] = ref
        
        self._add_to_index(self._by_workkey, ref.workkey, ref.evidence_id)
        self._add_to_index(self._by_component, ref.component, ref.evidence_id)
        self._add_to_index(self._by_sha, ref.sha, ref.evidence_id)
        self._add_to_index(self._by_host, ref.host, ref.evidence_id)
        self._add_to_index(self._by_os, ref.os, ref.evidence_id)
        self._add_to_index(self._by_test, ref.test, ref.evidence_id)
        self._add_to_index(self._by_incident, ref.incident, ref.evidence_id)
        self._add_to_index(self._by_readiness_criterion, ref.readiness_criterion, ref.evidence_id)

    def _lookup(self, index: Dict[str, Set[str]], key: str) -> List[EvidenceReference]:
        ev_ids = index.get(key, set())
        return [self._references[eid] for eid in ev_ids]

    # Search methods
    def find_by_workkey(self, workkey: str) -> List[EvidenceReference]:
        return self._lookup(self._by_workkey, workkey)

    def find_by_component(self, component: str) -> List[EvidenceReference]:
        return self._lookup(self._by_component, component)

    def find_by_sha(self, sha: str) -> List[EvidenceReference]:
        return self._lookup(self._by_sha, sha)

    def find_by_host(self, host: str) -> List[EvidenceReference]:
        return self._lookup(self._by_host, host)

    def find_by_os(self, os: str) -> List[EvidenceReference]:
        return self._lookup(self._by_os, os)

    def find_by_test(self, test: str) -> List[EvidenceReference]:
        return self._lookup(self._by_test, test)

    def find_by_incident(self, incident: str) -> List[EvidenceReference]:
        return self._lookup(self._by_incident, incident)

    def find_by_readiness_criterion(self, criterion: str) -> List[EvidenceReference]:
        return self._lookup(self._by_readiness_criterion, criterion)
        
    def search(self, **kwargs) -> List[EvidenceReference]:
        """
        Intersection search across multiple indices.
        e.g. search(os="windows", sha="abc")
        """
        if not kwargs:
            return list(self._references.values())
            
        result_sets = []
        for key, value in kwargs.items():
            index = getattr(self, f"_by_{key}", None)
            if index is not None:
                result_sets.append(index.get(value, set()))
            else:
                return [] # Invalid search key
                
        if not result_sets:
            return []
            
        intersection = set.intersection(*result_sets)
        return [self._references[eid] for eid in intersection]
