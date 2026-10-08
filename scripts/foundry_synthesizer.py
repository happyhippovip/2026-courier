#!/usr/bin/env python3
"""Idea Foundry Phase 2 — Autonomous Sort / Link / Synthesize (Issue #3).

Pre-Courier intelligence layer. Deterministic, local, idempotent:

* Originals are never modified or deleted; every output is a *derived* record
  that references source ``message_id`` values.
* Semantic dedup links exact/near duplicates (``DUPLICATE_OF``) instead of
  dropping them.
* Relationship edges are typed. ``SHARED_PROBLEM`` / ``SHARED_BUYER_OUTCOME``
  are *strong* edges derived from explicit structured facets. ``RELATED_TEXT``
  is a *weak* keyword edge that is recorded for review but can NEVER create a
  synthesis candidate (Issue #3: pure keyword overlap must not create
  Frankenstein products).
* Contradictions are detected symmetrically and attached to candidates as open
  questions; they are never silently resolved.
* Synthesis candidates carry explicit ``source_thought_ids``; unknown facets
  stay ``UNKNOWN``.
* Candidates then pass the Red Team / Kill Engine and Portfolio Scoring.

Output is advisory evidence only. It does not enter the memory proposal and
it does not create Courier goals; Courier remains the only orchestrator.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from typing import Any

from foundry_kill_engine import run_kill_engine
from foundry_portfolio_scoring import run_portfolio_scoring

FOUNDRY_KINDS = {"IDEA", "INTENT", "OPEN_QUESTION"}
FACET_KEYS = ("problem", "customer", "outcome", "product", "technology", "evidence")
NEAR_DUPLICATE_JACCARD = 0.8
RELATED_TEXT_JACCARD = 0.3
NEGATIONS = {"never", "not", "no", "dont", "don't", "avoid", "without", "cannot", "cant", "can't", "stop"}
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "with", "is", "are", "be", "should",
    "must", "we", "it", "this", "that", "use", "used", "using", "always", "by", "as", "at", "from", "our",
} | NEGATIONS
UNKNOWN = "UNKNOWN"


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _raw_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


@lru_cache(maxsize=65536)
def content_tokens(text: str) -> frozenset[str]:
    return frozenset(_stem(t) for t in _raw_tokens(text) if t not in STOPWORDS and len(t) > 1)


@lru_cache(maxsize=65536)
def _negated(text: str) -> bool:
    return any(t in NEGATIONS or t.endswith("n't") for t in _raw_tokens(text))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _facet(thought: dict[str, Any], key: str) -> str | None:
    value = (thought.get("facets") or {}).get(key)
    if value is None:
        return None
    value = " ".join(str(value).lower().split())
    return value or None


def select_thoughts(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Foundry input: idea-like thoughts, or any thought carrying explicit facets."""
    return [c for c in candidates if c.get("kind") in FOUNDRY_KINDS or c.get("facets")]


def dedupe(thoughts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return canonical thoughts plus ``duplicate_id -> canonical_id`` links. Nothing is deleted."""
    canonical: list[dict[str, Any]] = []
    links: dict[str, str] = {}
    for thought in sorted(thoughts, key=lambda t: t["message_id"]):
        tokens = content_tokens(thought.get("summary", ""))
        match = next(
            (c for c in canonical
             if _negated(c["summary"]) == _negated(thought["summary"])
             and _jaccard(content_tokens(c["summary"]), tokens) >= NEAR_DUPLICATE_JACCARD),
            None,
        )
        if match is None:
            canonical.append(thought)
        else:
            links[thought["message_id"]] = match["message_id"]
    return canonical, links


def link(thoughts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keyed = [(t["message_id"], _facet(t, "problem"), _facet(t, "customer"), _facet(t, "outcome"), content_tokens(t.get("summary", "")))
             for t in thoughts]
    edges = []
    for i, (ida, pa, ca, oa, ta) in enumerate(keyed):
        for idb, pb, cb, ob, tb in keyed[i + 1:]:
            first, second = sorted((ida, idb))
            if pa and pa == pb:
                edges.append({"from": first, "to": second, "type": "SHARED_PROBLEM", "strength": "STRONG", "basis": pa})
            elif ca and ca == cb and oa and oa == ob:
                edges.append({"from": first, "to": second, "type": "SHARED_BUYER_OUTCOME", "strength": "STRONG", "basis": f"{ca} -> {oa}"})
            elif _jaccard(ta, tb) >= RELATED_TEXT_JACCARD:
                edges.append({"from": first, "to": second, "type": "RELATED_TEXT", "strength": "WEAK", "basis": "keyword overlap only"})
    return edges


def strong_clusters(thoughts: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[str]]:
    """Connected components over STRONG edges only, size >= 2, deterministic order."""
    parent = {t["message_id"]: t["message_id"] for t in thoughts}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for edge in edges:
        if edge["strength"] == "STRONG":
            ra, rb = find(edge["from"]), find(edge["to"])
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    groups: dict[str, list[str]] = {}
    for mid in parent:
        groups.setdefault(find(mid), []).append(mid)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: g[0])


def detect_contradictions(thoughts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Symmetric polarity conflict: same subject tokens, opposite negation."""
    found = []
    for i, a in enumerate(thoughts):
        for b in thoughts[i + 1:]:
            if _negated(a["summary"]) == _negated(b["summary"]):
                continue
            shared = content_tokens(a["summary"]) & content_tokens(b["summary"])
            if len(shared) >= 2:
                pair = sorted((a["message_id"], b["message_id"]))
                found.append({"source_a": pair[0], "source_b": pair[1], "shared_subject": sorted(shared), "reason": "opposite polarity on shared subject"})
    return found


def _consensus(thoughts: list[dict[str, Any]], key: str) -> str:
    values = {_facet(t, key) for t in thoughts} - {None}
    return values.pop() if len(values) == 1 else UNKNOWN


def synthesize(thoughts: list[dict[str, Any]], clusters: list[list[str]], duplicate_links: dict[str, str]) -> list[dict[str, Any]]:
    by_id = {t["message_id"]: t for t in thoughts}
    candidates = []
    for cluster in clusters:
        members = [by_id[m] for m in cluster]
        sources = sorted(set(cluster) | {d for d, c in duplicate_links.items() if c in cluster})
        merged_flags: dict[str, Any] = {}
        merged_metrics: dict[str, Any] = {}
        for m in members:
            merged_flags.update((m.get("facets") or {}).get("risk_flags") or {})
            merged_metrics.update((m.get("facets") or {}).get("metrics") or {})
        contradictions = detect_contradictions(members)
        candidates.append({
            "candidate_id": "fcand-" + canonical_hash(sources)[:16],
            "source_thought_ids": sources,
            "problem_hypothesis": _consensus(members, "problem"),
            "target_user_hypothesis": _consensus(members, "customer"),
            "expected_outcome": _consensus(members, "outcome"),
            "evidence": sorted({_facet(m, "evidence") for m in members} - {None}),
            "contradictions": contradictions,
            "open_questions": [f"Resolve contradiction between {c['source_a']} and {c['source_b']}" for c in contradictions],
            "risk_flags": merged_flags,
            "metrics": merged_metrics,
            "confidence": UNKNOWN,
            "status": "CANDIDATE",
        })
    return candidates


def run_foundry(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Phase 2 entry point used by the Thought Memory Mesh. Pure and idempotent."""
    thoughts = select_thoughts(candidates)
    canonical, duplicate_links = dedupe(thoughts)
    edges = link(canonical)
    edges += [{"from": d, "to": c, "type": "DUPLICATE_OF", "strength": "DERIVED", "basis": "near-duplicate text"} for d, c in sorted(duplicate_links.items())]
    clusters = strong_clusters(canonical, edges)
    synthesized = synthesize(canonical, clusters, duplicate_links)
    red_team = run_kill_engine(synthesized)
    portfolio = run_portfolio_scoring(red_team["experiment_ready"])
    return {
        "schema_version": "foundry-phase2-1.0",
        "thoughts_considered": len(thoughts),
        "duplicate_links": duplicate_links,
        "relationship_graph": edges,
        "strong_clusters": clusters,
        "weak_links_not_synthesized": sum(1 for e in edges if e["strength"] == "WEAK"),
        "synthesized_candidates": synthesized,
        "red_team": red_team,
        "portfolio": portfolio,
    }
