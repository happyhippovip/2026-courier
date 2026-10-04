import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from evidence_index import EvidenceIndex, EvidenceReference

def test_evidence_index_registration_and_lookup():
    idx = EvidenceIndex()
    
    ref1 = EvidenceReference(
        evidence_id="ev-1",
        payload_uri="file:///data/ev1.json",
        checksum="hash1",
        workkey="wk-1",
        os="windows",
        sha="sha-a"
    )
    
    ref2 = EvidenceReference(
        evidence_id="ev-2",
        payload_uri="file:///data/ev2.json",
        checksum="hash2",
        workkey="wk-2",
        os="windows",
        sha="sha-b",
        component="installer"
    )
    
    idx.register(ref1)
    idx.register(ref2)
    
    # Test single parameter lookups
    assert len(idx.find_by_os("windows")) == 2
    assert len(idx.find_by_os("linux")) == 0
    
    assert len(idx.find_by_sha("sha-a")) == 1
    assert idx.find_by_sha("sha-a")[0].evidence_id == "ev-1"
    
    assert len(idx.find_by_component("installer")) == 1
    assert idx.find_by_component("installer")[0].evidence_id == "ev-2"

def test_evidence_index_intersection_search():
    idx = EvidenceIndex()
    
    ref1 = EvidenceReference(
        evidence_id="ev-1",
        payload_uri="s3://data/ev1",
        checksum="hash1",
        os="windows",
        sha="sha-x",
        readiness_criterion="build_success"
    )
    
    ref2 = EvidenceReference(
        evidence_id="ev-2",
        payload_uri="s3://data/ev2",
        checksum="hash2",
        os="linux",
        sha="sha-x",
        readiness_criterion="build_success"
    )
    
    idx.register(ref1)
    idx.register(ref2)
    
    # Search for SHA (should return both)
    results = idx.search(sha="sha-x")
    assert len(results) == 2
    
    # Intersection: SHA + OS
    results = idx.search(sha="sha-x", os="windows")
    assert len(results) == 1
    assert results[0].evidence_id == "ev-1"
    
    # Intersection: SHA + OS + Criterion
    results = idx.search(sha="sha-x", os="linux", readiness_criterion="build_success")
    assert len(results) == 1
    assert results[0].evidence_id == "ev-2"
    
    # No match intersection
    results = idx.search(sha="sha-x", os="mac")
    assert len(results) == 0
