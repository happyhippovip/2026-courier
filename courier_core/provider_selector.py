"""Rank qualified providers by total cost.

The selector reads a capacity governor. It does not admit jobs and it does
not copy governor policy. UNKNOWN and ORANGE pressure exclude HEAVY
candidates. An unqualified or stale qualification is never chosen. When no
qualified candidate can be admitted, the decision parks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from courier_core.provider_identity import ProviderIdentity
from courier_core.provider_qualification import (
    STATUS_QUALIFIED,
    STATUS_STALE,
    QualificationError,
    QualificationRecord,
    QualificationStore,
)

STATUS_SELECTED = "SELECTED"
STATUS_NO_QUALIFIED = "NO_QUALIFIED_CANDIDATE"
STATUS_NO_ELIGIBLE = "NO_ELIGIBLE_CANDIDATE"

REASON_UNQUALIFIED = "unqualified"
REASON_STALE = "stale"
REASON_HEAVY = "heavy_excluded"
REASON_METERED = "metered_requires_escalation"
REASON_HIGHER_COST = "higher_cost"
REASON_TIE = "tie_broken"

WEIGHT_LIGHT = "LIGHT"
WEIGHT_MEDIUM = "MEDIUM"
WEIGHT_HEAVY = "HEAVY"
_WEIGHTS = frozenset({WEIGHT_LIGHT, WEIGHT_MEDIUM, WEIGHT_HEAVY})
_HEAVY_BLOCKED = frozenset({"UNKNOWN", "ORANGE"})
_QUALIFICATION_REASONS = frozenset({REASON_UNQUALIFIED, REASON_STALE})
_MAX_REASON = 200


class SelectorError(ValueError):
    """A candidate or argument is not usable."""


@dataclass(frozen=True)
class ProviderCandidate:
    identity: ProviderIdentity
    total_cost: int
    weight: str
    metered: bool

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ProviderIdentity):
            raise SelectorError("identity must be a provider identity")
        if isinstance(self.total_cost, bool) or not isinstance(self.total_cost, int) or self.total_cost < 0:
            raise SelectorError("total_cost must be a non-negative integer")
        if self.weight not in _WEIGHTS:
            raise SelectorError("weight is not a known value")
        if not isinstance(self.metered, bool):
            raise SelectorError("metered must be a boolean")


@dataclass(frozen=True)
class Rejection:
    provider_id: str
    config_hash: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "config_hash": self.config_hash,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SelectionDecision:
    status: str
    governor_pressure: str
    selected_provider_id: str | None
    selected_config_hash: str | None
    total_cost: int | None
    weight: str | None
    metered: bool | None
    escalation_reason: str | None
    rejections: tuple[Rejection, ...]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "governor_pressure": self.governor_pressure,
            "selected_provider_id": self.selected_provider_id,
            "selected_config_hash": self.selected_config_hash,
            "total_cost": self.total_cost,
            "weight": self.weight,
            "metered": self.metered,
            "escalation_reason": self.escalation_reason,
            "rejections": [item.to_dict() for item in self.rejections],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def read_pressure(governor: object) -> str:
    """Read governor pressure without admitting a job.

    A ``pressure`` method is used when present. Otherwise
    ``measure_pressure`` is used, which is the read method on the host
    pressure controller. A missing or failed read is UNKNOWN.
    """
    if governor is None:
        return "UNKNOWN"
    for name in ("pressure", "measure_pressure"):
        reader = getattr(governor, name, None)
        if not callable(reader):
            continue
        try:
            value = reader()
        except Exception:
            return "UNKNOWN"
        if isinstance(value, str) and value.strip() and len(value.strip()) <= 32 and "\n" not in value:
            return value.strip()
        return "UNKNOWN"
    return "UNKNOWN"


def select(
    candidates,
    store: QualificationStore,
    governor: object,
    *,
    escalation_reason: str | None = None,
) -> SelectionDecision:
    """Choose the lowest total cost among candidates that may receive work.

    Ties break by provider id, then identity fingerprint, then input order.
    """
    if not isinstance(store, QualificationStore):
        raise SelectorError("store must be a qualification store")
    rows = _candidates(candidates)
    pressure = read_pressure(governor)
    escalation = _escalation(escalation_reason)
    records, readable = _records(store)
    rejections: list[Rejection] = []
    eligible: list[tuple[int, ProviderCandidate]] = []
    for index, candidate in enumerate(rows):
        reason = _reject_reason(candidate, records, readable, pressure, escalation)
        if reason is None:
            eligible.append((index, candidate))
            continue
        rejections.append(_rejection(candidate, reason))
    if not eligible:
        status = STATUS_NO_QUALIFIED if _only_qualification_failures(rejections) else STATUS_NO_ELIGIBLE
        return _parked(status, pressure, rejections)
    eligible.sort(key=lambda item: _rank_key(item[1], item[0]))
    winner_index, winner = eligible[0]
    for index, candidate in eligible[1:]:
        reason = REASON_TIE if candidate.total_cost == winner.total_cost else REASON_HIGHER_COST
        rejections.append(_rejection(candidate, reason))
    ordered = tuple(sorted(rejections, key=_rejection_key))
    return SelectionDecision(
        status=STATUS_SELECTED,
        governor_pressure=pressure,
        selected_provider_id=winner.identity.provider_id,
        selected_config_hash=winner.identity.fingerprint(),
        total_cost=winner.total_cost,
        weight=winner.weight,
        metered=winner.metered,
        escalation_reason=escalation if winner.metered else None,
        rejections=ordered,
    )


def _candidates(candidates) -> tuple[ProviderCandidate, ...]:
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, (list, tuple)):
        raise SelectorError("candidates must be a list")
    rows = tuple(candidates)
    for candidate in rows:
        if not isinstance(candidate, ProviderCandidate):
            raise SelectorError("candidates must contain provider candidates")
    return rows


def _records(store: QualificationStore) -> tuple[tuple[QualificationRecord, ...], bool]:
    try:
        return store.read(), True
    except QualificationError:
        return (), False


def _reject_reason(
    candidate: ProviderCandidate,
    records: tuple[QualificationRecord, ...],
    readable: bool,
    pressure: str,
    escalation: str | None,
) -> str | None:
    qualification = _qualification_reason(candidate, records, readable)
    if qualification is not None:
        return qualification
    if candidate.weight == WEIGHT_HEAVY and pressure in _HEAVY_BLOCKED:
        return REASON_HEAVY
    if candidate.metered and escalation is None:
        return REASON_METERED
    return None


def _qualification_reason(
    candidate: ProviderCandidate,
    records: tuple[QualificationRecord, ...],
    readable: bool,
) -> str | None:
    if not readable:
        return REASON_UNQUALIFIED
    identity = candidate.identity
    fingerprint = identity.fingerprint()
    matched = [
        record
        for record in records
        if record.name == identity.provider_id and record.config_hash == fingerprint
    ]
    if len(matched) == 1 and matched[0].status == STATUS_QUALIFIED:
        return None
    if len(matched) == 1 and matched[0].status == STATUS_STALE:
        return REASON_STALE
    return REASON_UNQUALIFIED


def _only_qualification_failures(rejections: list[Rejection]) -> bool:
    return all(item.reason in _QUALIFICATION_REASONS for item in rejections)


def _parked(status: str, pressure: str, rejections: list[Rejection]) -> SelectionDecision:
    return SelectionDecision(
        status=status,
        governor_pressure=pressure,
        selected_provider_id=None,
        selected_config_hash=None,
        total_cost=None,
        weight=None,
        metered=None,
        escalation_reason=None,
        rejections=tuple(sorted(rejections, key=_rejection_key)),
    )


def _rejection(candidate: ProviderCandidate, reason: str) -> Rejection:
    return Rejection(
        provider_id=candidate.identity.provider_id,
        config_hash=candidate.identity.fingerprint(),
        reason=reason,
    )


def _rank_key(candidate: ProviderCandidate, index: int) -> tuple:
    return (
        candidate.total_cost,
        candidate.identity.provider_id,
        candidate.identity.fingerprint(),
        index,
    )


def _rejection_key(item: Rejection) -> tuple:
    return (item.provider_id, item.config_hash, item.reason)


def _escalation(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > _MAX_REASON
        or any(ch in value for ch in "\n\r\x00")
    ):
        raise SelectorError("escalation reason must be a single line")
    return value.strip()
