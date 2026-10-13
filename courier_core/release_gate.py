"""Pure release gate for a final candidate, required tests, and PRE_CODEX_READY.

No I/O and no clock. A shared SHA with a different content hash does not
match. Exit code 0 does not excuse a required skip. A hardcoded relay count
is not a ready proof.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

SCHEMA = "courier.release_gate.v1"
PASS_STATUSES = frozenset({"matched", "clear"})
STATUSES = frozenset({"matched", "mismatched", "clear", "blocked", "unmeasured", "rejected"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KNOWN_OUTCOMES = frozenset({"passed", "failed", "error", "skipped"})


@dataclass(frozen=True)
class ReleaseVerdict:
    metric: str
    status: str
    matched: bool | None
    skipped: int | None
    ready: bool | None
    reason: str
    verified: bool
    digest: str

    def to_json(self) -> str:
        return json.dumps(_payload(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def from_json(text: str) -> "ReleaseVerdict":
        return _from_json(text)


def compare_final_candidates(left: Any, right: Any) -> ReleaseVerdict:
    """Match only when SHA and content hash are both present and equal."""
    if isinstance(left, str) or isinstance(right, str):
        return _unmeasured("final_candidate", "prose_not_receipt")
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return _unmeasured("final_candidate", "invalid_input")
    left_fp, left_reason = _fingerprint(left)
    right_fp, right_reason = _fingerprint(right)
    if left_reason or right_reason:
        return _unmeasured("final_candidate", left_reason or right_reason)
    if left_fp == right_fp:
        return _seal("final_candidate", "matched", "matched", matched=True)
    return _seal("final_candidate", "mismatched", "mismatched", matched=False)


def assess_required_tests(report: Any) -> ReleaseVerdict:
    """A required skip, failure, or absence blocks. Exit code 0 cannot override it."""
    if isinstance(report, str):
        return _unmeasured("required_tests", "prose_not_receipt")
    if not isinstance(report, Mapping):
        return _unmeasured("required_tests", "invalid_input")
    required = report.get("required")
    results = report.get("results")
    if not isinstance(required, list) or not required:
        return _unmeasured("required_tests", "no_required_set")
    if not isinstance(results, list):
        return _unmeasured("required_tests", "invalid_input")
    if any(not isinstance(item, str) or not item for item in required):
        return _unmeasured("required_tests", "invalid_input")
    if len(required) != len(set(required)):
        return _unmeasured("required_tests", "invalid_input")
    skipped = 0
    failed = 0
    missing = 0
    for req in required:
        matches = [item for item in results if isinstance(item, Mapping) and _covers(item.get("nodeid"), req)]
        if not matches:
            missing += 1
            continue
        for item in matches:
            outcome = item.get("outcome")
            if outcome not in _KNOWN_OUTCOMES:
                return _unmeasured("required_tests", "unknown_outcome")
            if outcome == "skipped":
                skipped += 1
            elif outcome in {"failed", "error"}:
                failed += 1
    if "skipped" in report and report.get("skipped") != skipped:
        return _unmeasured("required_tests", "summary_mismatch")
    if skipped:
        return _seal("required_tests", "blocked", "required_skip", skipped=skipped, ready=False)
    if failed:
        return _seal("required_tests", "blocked", "required_failed", skipped=0, ready=False)
    if missing:
        return _seal("required_tests", "blocked", "required_missing", skipped=0, ready=False)
    return _seal("required_tests", "clear", "clear", skipped=0, ready=True)


def prove_pre_codex_ready(sample: Any) -> ReleaseVerdict:
    """Ready only when the fingerprint matches, required tests are clear, and relays are measured."""
    if isinstance(sample, str):
        return _unmeasured("pre_codex_ready", "prose_not_receipt")
    if not isinstance(sample, Mapping):
        return _unmeasured("pre_codex_ready", "invalid_input")
    if "claimed" not in sample or "observed" not in sample:
        return _unmeasured("pre_codex_ready", "fingerprint_unmeasured")
    compared = compare_final_candidates(sample.get("claimed"), sample.get("observed"))
    if compared.status == "unmeasured":
        return _unmeasured("pre_codex_ready", compared.reason)
    if compared.status != "matched":
        return _seal("pre_codex_ready", "blocked", "mismatched", matched=False, ready=False)
    if "tests" not in sample:
        return _unmeasured("pre_codex_ready", "no_required_set")
    tests = assess_required_tests(sample.get("tests"))
    if tests.status == "unmeasured":
        return _unmeasured("pre_codex_ready", tests.reason)
    if tests.status != "clear":
        return _seal(
            "pre_codex_ready",
            "blocked",
            tests.reason,
            matched=True,
            skipped=tests.skipped,
            ready=False,
        )
    if "human_relays" not in sample:
        return _unmeasured("pre_codex_ready", "relay_unmeasured")
    from courier_core.continuity_metrics import count_human_relays

    relays = count_human_relays(sample.get("human_relays"))
    if not relays.verified:
        return _unmeasured("pre_codex_ready", "relay_unmeasured")
    if relays.count:
        return _seal(
            "pre_codex_ready",
            "blocked",
            "human_relay_present",
            matched=True,
            skipped=0,
            ready=False,
        )
    return _seal(
        "pre_codex_ready",
        "clear",
        "clear",
        matched=True,
        skipped=0,
        ready=True,
    )


def _fingerprint(candidate: Mapping[str, Any]) -> tuple[str | None, str | None]:
    sha = candidate.get("candidate_sha")
    sha_ok = isinstance(sha, str) and bool(sha) and not any(char.isspace() for char in sha)
    if "content_hash" not in candidate or candidate.get("content_hash") is None:
        return None, "invalid_sha" if not sha_ok else "content_hash_missing"
    if not sha_ok:
        return None, "invalid_sha"
    content = candidate.get("content_hash")
    if not isinstance(content, str) or _SHA256.fullmatch(content) is None:
        return None, "invalid_content_hash"
    body = {"candidate_sha": sha, "content_hash": content}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest(), None


def _covers(nodeid: Any, required: str) -> bool:
    return isinstance(nodeid, str) and (nodeid == required or nodeid.startswith(required + "::"))


def _unmeasured(metric: str, reason: str) -> ReleaseVerdict:
    return _seal(metric, "unmeasured", reason)


def _seal(
    metric: str,
    status: str,
    reason: str,
    *,
    matched: bool | None = None,
    skipped: int | None = None,
    ready: bool | None = None,
) -> ReleaseVerdict:
    verified = status in PASS_STATUSES
    verdict = ReleaseVerdict(metric, status, matched, skipped, ready, reason, verified, "")
    return ReleaseVerdict(
        metric, status, matched, skipped, ready, reason, verified, _digest(_body(verdict))
    )


def _body(verdict: ReleaseVerdict) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "metric": verdict.metric,
        "status": verdict.status,
        "reason": verdict.reason,
    }
    if verdict.matched is not None:
        body["matched"] = verdict.matched
    if verdict.skipped is not None:
        body["skipped"] = verdict.skipped
    if verdict.ready is not None:
        body["ready"] = verdict.ready
    return body


def _payload(verdict: ReleaseVerdict) -> dict[str, Any]:
    payload = _body(verdict)
    payload["verified"] = verdict.verified
    payload["digest"] = verdict.digest
    return payload


def _digest(body: Mapping[str, Any]) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _opt_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError("flag")
    return value


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("count")
    return value


def _from_json(text: str) -> ReleaseVerdict:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return _seal("unknown", "rejected", "tampered")
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        return _seal("unknown", "rejected", "tampered")
    metric = raw.get("metric")
    status = raw.get("status")
    reason = raw.get("reason")
    if not isinstance(metric, str) or status not in STATUSES or not isinstance(reason, str):
        return _seal("unknown", "rejected", "tampered")
    try:
        matched = _opt_bool(raw.get("matched"))
        ready = _opt_bool(raw.get("ready"))
        skipped = _opt_int(raw.get("skipped"))
    except ValueError:
        return _seal(metric, "rejected", "tampered")
    body = {"schema": SCHEMA, "metric": metric, "status": status, "reason": reason}
    if matched is not None:
        body["matched"] = matched
    if skipped is not None:
        body["skipped"] = skipped
    if ready is not None:
        body["ready"] = ready
    verified_flag = raw.get("verified")
    if raw.get("digest") != _digest(body) or verified_flag not in {True, False}:
        return _seal(metric, "rejected", "tampered")
    if verified_flag is True and status not in PASS_STATUSES:
        return _seal(metric, "rejected", "tampered")
    return _seal(metric, status, reason, matched=matched, skipped=skipped, ready=ready)
