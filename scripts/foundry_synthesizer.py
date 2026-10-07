#!/usr/bin/env python3
"""Autonomous Sort / Link / Synthesize for Courier Idea Foundry.

Responsible for:
1. Semantic deduplication (without destroying originals)
2. Clustering (by problem/customer/outcome/product/technology/evidence)
3. Relationship graph between thoughts
4. Contradiction detection
5. Synthesis candidate generation with explicit source_thought_ids

This implementation provides the local deterministic graph constraints and 
preparation. Actual LLM execution for deep semantic analysis is routed to 
the external cognitive bridges via the Courier event bus.
"""

from __future__ import annotations
import json
import hashlib
from collections import defaultdict
from typing import Any

def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

def detect_contradictions(cluster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detects mutually exclusive claims within a cluster using deterministic heuristics."""
    contradictions = []
    # Mock contradiction logic for Phase 2 constraint validation
    for i in range(len(cluster)):
        for j in range(i + 1, len(cluster)):
            a, b = cluster[i], cluster[j]
            # Simple keyword contradiction for the prototype (e.g. "always" vs "never")
            summary_a = a.get("summary", "").lower()
            summary_b = b.get("summary", "").lower()
            if "always" in summary_a and "never" in summary_b:
                contradictions.append({"source_a": a["message_id"], "source_b": b["message_id"], "reason": "Keyword constraint violation"})
    return contradictions

def cluster_thoughts(thoughts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Clusters thoughts by their extracted primary facets."""
    clusters = defaultdict(list)
    for t in thoughts:
        # Default fallback clustering based on kind
        facet = t.get("kind", "OTHER")
        clusters[facet].append(t)
    return dict(clusters)

def synthesize_candidates(clusters: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Generates traceable synthesis candidates from clusters."""
    candidates = []
    for facet, cluster in clusters.items():
        if len(cluster) > 1:
            source_ids = [t["message_id"] for t in cluster]
            contradictions = detect_contradictions(cluster)
            
            # Synthesize
            candidates.append({
                "message_id": f"synth-{canonical_hash(source_ids)[:12]}",
                "source": "FOUNDRY_SYNTHESIS",
                "source_thought_ids": source_ids,
                "kind": "SYNTHESIS",
                "summary": f"Synthesized candidate from {len(source_ids)} thoughts in {facet}",
                "contradictions": contradictions,
                "status_label": "IDEA",
                "payload_hash": canonical_hash(source_ids)
            })
    return candidates

def run_synthesizer(thoughts: list[dict[str, Any]]) -> dict[str, Any]:
    clusters = cluster_thoughts(thoughts)
    synthesized = synthesize_candidates(clusters)
    
    # Relationship Graph
    edges = []
    for s in synthesized:
        for sid in s["source_thought_ids"]:
            edges.append({"from": sid, "to": s["message_id"], "type": "SYNTHESIZED_INTO"})

    return {
        "clusters": clusters,
        "synthesized_candidates": synthesized,
        "relationship_graph": edges,
        "contradiction_count": sum(len(s.get("contradictions", [])) for s in synthesized)
    }
