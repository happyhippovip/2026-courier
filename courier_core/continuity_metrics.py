"""Pure continuity metrics for relay count, restart success, and next-day return.

No I/O and no clock. Callers pass the sample. A bare integer, agent prose, an
empty sample, or a verified flag that disagrees with the signed body is not
a measurement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

SCHEMA = "courier.continuity_metrics.v1"
STATUSES = frozenset({"measured", "unmeasured", "rejected"})

RELAY_LABELS = frozenset({"human_relay", "paste", "manual_forward", "relay"})
GATE_LABELS = frozenset({
    "human_gate",
    "effect_confirmed",
    "retry_authorized",
    "cancel",
    "approval",
    "gate",
    "task_cancelled",
    "task_cancel_requested",
})
NEUTRAL_LABELS = frozenset({"worker", "system", "controller"})
PROSE_LABELS = frozenset({"prose", "agent_claim"})
SUCCESS_OUTCOME = "resumed_without_replay"
KNOWN_OUTCOMES = frozenset({
    "resumed_without_replay",
    "replayed",
    "failed",
    "uncertain",
})


@dataclass(frozen=True)
class MetricVerdict:
    metric: str
    status: str
    count: int | None
    successes: int | None
    measured: int | None
    classified: int
    reason: str
    verified: bool
    digest: str

    def to_json(self) -> str:
        return json.dumps(
            _payload(self),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def from_json(text: str) -> "MetricVerdict":
        return _from_json(text)


def count_human_relays(sample: Any, *, sample_complete: bool = False) -> MetricVerdict:
    """Count human paste/forward relays. A human gate is not a relay."""
    events, reason = _event_sample(sample, sample_complete=sample_complete)
    if reason:
        return _unmeasured("human_relays", reason)
    relays = 0
    for event in events:
        kind = _classify_relay_event(event)
        if kind == "relay":
            relays += 1
        elif kind in {"gate", "neutral"}:
            continue
        elif kind == "prose":
            return _unmeasured("human_relays", "prose_not_receipt")
        else:
            return _unmeasured("human_relays", "unknown_event")
    return _measured("human_relays", count=relays, classified=len(events))


def restart_success_rate(sample: Any) -> MetricVerdict:
    """Successes over measured attempts. Success is resume without replay.

    An empty sample is not 100%. Uncertain and replayed attempts are measured
    and are not successes. The result is a count pair, never a float.
    """
    attempts, reason = _attempt_sample(sample)
    if reason:
        return _unmeasured("restart_success", reason)
    seen: set[str] = set()
    successes = 0
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            return _unmeasured("restart_success", "invalid_input")
        outcome = attempt.get("outcome")
        if not isinstance(outcome, str) or outcome not in KNOWN_OUTCOMES:
            return _unmeasured("restart_success", "missing_outcome")
        attempt_id = attempt.get("attempt_id")
        if attempt_id is not None:
            if not isinstance(attempt_id, str) or attempt_id in seen:
                return _unmeasured("restart_success", "duplicate_attempt")
            seen.add(attempt_id)
        if outcome == SUCCESS_OUTCOME:
            successes += 1
    return _measured(
        "restart_success",
        successes=successes,
        measured_n=len(attempts),
        classified=len(attempts),
    )


def prepare_next_day_return(sample: Any) -> MetricVerdict:
    """Prepare a next-day return measurement from an explicit cohort sample.

    No clock and no contact. A missing later calendar day stays unmeasured.
    """
    if isinstance(sample, str):
        return _unmeasured("next_day_return", "prose_not_receipt")
    if not isinstance(sample, Mapping):
        return _unmeasured("next_day_return", "invalid_input")
    prior_day_id = sample.get("prior_day_id")
    if not isinstance(prior_day_id, str) or not prior_day_id:
        return _unmeasured("next_day_return", "missing_prior_day")
    prior = _parse_date(sample.get("prior_date"))
    if prior is None:
        return _unmeasured("next_day_return", "invalid_input")
    if "subjects" not in sample:
        return _unmeasured("next_day_return", "not_yet")
    subjects = sample.get("subjects")
    if not isinstance(subjects, list):
        return _unmeasured("next_day_return", "invalid_input")
    if not subjects:
        return _unmeasured("next_day_return", "not_yet")
    seen: set[str] = set()
    returned = 0
    for subject in subjects:
        if not isinstance(subject, Mapping):
            return _unmeasured("next_day_return", "invalid_input")
        subject_id = subject.get("subject_id")
        if not isinstance(subject_id, str) or not subject_id:
            return _unmeasured("next_day_return", "invalid_input")
        if subject_id in seen:
            return _unmeasured("next_day_return", "duplicate_subject")
        seen.add(subject_id)
        if subject.get("checked") is not True:
            return _unmeasured("next_day_return", "not_yet")
        observed = _parse_date(subject.get("observation_date"))
        if observed is None:
            return _unmeasured("next_day_return", "not_yet")
        if observed == prior:
            return _unmeasured("next_day_return", "same_calendar_day")
        if observed < prior:
            return _unmeasured("next_day_return", "not_later_day")
        came_back = subject.get("returned")
        if not isinstance(came_back, bool):
            return _unmeasured("next_day_return", "prose_signal")
        if came_back:
            returned += 1
    return _measured(
        "next_day_return",
        successes=returned,
        measured_n=len(subjects),
        classified=len(subjects),
    )


def _event_sample(sample: Any, *, sample_complete: bool) -> tuple[list[Any] | None, str | None]:
    if isinstance(sample, bool) or isinstance(sample, int):
        return None, "hardcoded_counter"
    if isinstance(sample, str):
        return None, "prose_not_receipt"
    if sample is None:
        return None, "invalid_input"
    if isinstance(sample, list):
        if not sample and not sample_complete:
            return None, "empty_sample"
        return list(sample), None
    if isinstance(sample, Mapping):
        if "execution_counters" in sample and "events" not in sample:
            return None, "hardcoded_counter"
        if "events" not in sample:
            return None, "invalid_input"
        events = sample.get("events")
        if not isinstance(events, list):
            return None, "invalid_input"
        complete = sample.get("sample_complete", sample_complete)
        if not isinstance(complete, bool):
            return None, "invalid_input"
        if not events and complete is not True:
            return None, "empty_sample"
        return list(events), None
    return None, "invalid_input"


def _attempt_sample(sample: Any) -> tuple[list[Any] | None, str | None]:
    if isinstance(sample, str):
        return None, "prose_not_receipt"
    if sample is None or isinstance(sample, bool) or isinstance(sample, int):
        return None, "invalid_input"
    if isinstance(sample, list):
        if not sample:
            return None, "empty_sample"
        return list(sample), None
    if isinstance(sample, Mapping):
        attempts = sample.get("attempts")
        if not isinstance(attempts, list):
            return None, "invalid_input"
        if not attempts:
            return None, "empty_sample"
        return list(attempts), None
    return None, "invalid_input"


def _classify_relay_event(event: Any) -> str:
    if not isinstance(event, Mapping):
        return "unknown"
    labels: list[str] = []
    for key in ("kind", "role", "type"):
        value = event.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            return "unknown"
        labels.append(value.strip())
    if not labels:
        return "unknown"
    classes = {_label_class(label) for label in labels}
    if "unknown" in classes:
        return "unknown"
    if "prose" in classes:
        return "prose"
    if "relay" in classes and "gate" in classes:
        return "unknown"
    if "relay" in classes:
        return "relay"
    if "gate" in classes:
        return "gate"
    if classes <= {"neutral"}:
        return "neutral"
    return "unknown"


def _label_class(label: str) -> str:
    lowered = label.lower()
    if lowered in PROSE_LABELS:
        return "prose"
    if lowered in RELAY_LABELS:
        return "relay"
    if lowered in GATE_LABELS:
        return "gate"
    if lowered in NEUTRAL_LABELS:
        return "neutral"
    return "unknown"


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _measured(
    metric: str,
    *,
    count: int | None = None,
    successes: int | None = None,
    measured_n: int | None = None,
    classified: int,
) -> MetricVerdict:
    return _seal(
        metric,
        "measured",
        "measured",
        count=count,
        successes=successes,
        measured_n=measured_n,
        classified=classified,
    )


def _unmeasured(metric: str, reason: str) -> MetricVerdict:
    return _seal(metric, "unmeasured", reason)


def _seal(
    metric: str,
    status: str,
    reason: str,
    *,
    count: int | None = None,
    successes: int | None = None,
    measured_n: int | None = None,
    classified: int = 0,
) -> MetricVerdict:
    verdict = MetricVerdict(
        metric=metric,
        status=status,
        count=count,
        successes=successes,
        measured=measured_n,
        classified=classified,
        reason=reason,
        verified=status == "measured",
        digest="",
    )
    digest = _digest(_body(verdict))
    return MetricVerdict(
        metric=metric,
        status=status,
        count=count,
        successes=successes,
        measured=measured_n,
        classified=classified,
        reason=reason,
        verified=status == "measured",
        digest=digest,
    )


def _body(verdict: MetricVerdict) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "metric": verdict.metric,
        "status": verdict.status,
        "count": verdict.count,
        "successes": verdict.successes,
        "measured": verdict.measured,
        "classified": verdict.classified,
        "reason": verdict.reason,
    }


def _payload(verdict: MetricVerdict) -> dict[str, Any]:
    payload = _body(verdict)
    payload["verified"] = verdict.verified
    payload["digest"] = verdict.digest
    return payload


def _digest(body: Mapping[str, Any]) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("count must be a non-negative integer")
    return value


def _from_json(text: str) -> MetricVerdict:
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
        count = _opt_int(raw.get("count"))
        successes = _opt_int(raw.get("successes"))
        measured_n = _opt_int(raw.get("measured"))
        classified = raw.get("classified")
        if isinstance(classified, bool) or not isinstance(classified, int) or classified < 0:
            raise ValueError("classified")
    except ValueError:
        return _seal(metric, "rejected", "tampered")
    body = {
        "schema": SCHEMA,
        "metric": metric,
        "status": status,
        "count": count,
        "successes": successes,
        "measured": measured_n,
        "classified": classified,
        "reason": reason,
    }
    verified_flag = raw.get("verified")
    if raw.get("digest") != _digest(body) or verified_flag not in {True, False}:
        return _seal(metric, "rejected", "tampered")
    if verified_flag is True and status != "measured":
        return _seal(metric, "rejected", "tampered")
    if status == "measured":
        return _seal(
            metric,
            "measured",
            reason,
            count=count,
            successes=successes,
            measured_n=measured_n,
            classified=classified,
        )
    if status == "unmeasured":
        return _seal(metric, "unmeasured", reason, classified=classified)
    return _seal(metric, "rejected", "tampered")
