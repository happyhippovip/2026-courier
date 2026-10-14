"""Goal Contract: the human-confirmed anchor a task must fit.

A person confirms the terms once. Courier may split work inside those terms.
It may not change what success means. An extension needs another human
confirmation. A task with no checkable acceptance anchor is not verifiable
and is never accepted. The fingerprint identifies the terms for a Proof Card;
confirming them does not change it.

This module records a confirmation the caller already collected. It never
invents one. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

MAX_FILE_BYTES = 1024 * 1024
_MAX_TEXT = 4000

_FINGERPRINT_FIELDS = (
    "goal_id",
    "end_result",
    "allowed_scope",
    "forbidden_scope",
    "constraints",
    "acceptance_criteria",
    "side_effect_limits",
    "gates",
)
_TASK_FIELDS = frozenset({
    "goal_id",
    "goal_fingerprint",
    "scope",
    "acceptance_ids",
    "evidence_class",
})
_AMEND_FIELDS = frozenset({
    "end_result",
    "allowed_scope",
    "forbidden_scope",
    "constraints",
    "acceptance_criteria",
    "side_effect_limits",
    "gates",
})


class GoalContractError(ValueError):
    """The contract, the task, or the stored record is not acceptable."""


class Verdict(str, Enum):
    ACCEPTED = "ACCEPTED"
    HUMAN_CONFIRMATION_REQUIRED = "HUMAN_CONFIRMATION_REQUIRED"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"


@dataclass(frozen=True)
class Validation:
    verdict: Verdict
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    check: str
    evidence_class: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "criterion id"))
        object.__setattr__(self, "check", _text(self.check, "criterion check"))
        object.__setattr__(self, "evidence_class", _text(self.evidence_class, "evidence class"))

    def to_record(self) -> dict:
        return {"id": self.id, "check": self.check, "evidence_class": self.evidence_class}

    @classmethod
    def from_record(cls, record: object) -> "AcceptanceCriterion":
        data = _object(record, "acceptance criterion", {"id", "check", "evidence_class"})
        return cls(data["id"], data["check"], data["evidence_class"])


@dataclass(frozen=True)
class Confirmation:
    actor_kind: str
    actor_ref: str
    at: str

    def __post_init__(self) -> None:
        if self.actor_kind != "human":
            raise GoalContractError("only a human confirmation can be recorded")
        object.__setattr__(self, "actor_ref", _text(self.actor_ref, "actor_ref"))
        object.__setattr__(self, "at", _text(self.at, "confirmation time"))

    def to_record(self) -> dict:
        return {"actor_kind": self.actor_kind, "actor_ref": self.actor_ref, "at": self.at}

    @classmethod
    def from_record(cls, record: object) -> "Confirmation":
        data = _object(record, "confirmation", {"actor_kind", "actor_ref", "at"})
        return cls(data["actor_kind"], data["actor_ref"], data["at"])


@dataclass(frozen=True)
class Gates:
    human: bool
    money: bool
    safety: bool

    def __post_init__(self) -> None:
        for name in ("human", "money", "safety"):
            if type(getattr(self, name)) is not bool:
                raise GoalContractError(f"gate {name} must be true or false")

    def to_record(self) -> dict:
        return {"human": self.human, "money": self.money, "safety": self.safety}

    @classmethod
    def from_record(cls, record: object) -> "Gates":
        data = _object(record, "gates", {"human", "money", "safety"})
        return cls(data["human"], data["money"], data["safety"])


@dataclass(frozen=True)
class GoalContract:
    goal_id: str
    end_result: str
    allowed_scope: tuple[str, ...] | list[str]
    forbidden_scope: tuple[str, ...] | list[str]
    constraints: tuple[str, ...] | list[str]
    acceptance_criteria: tuple[AcceptanceCriterion, ...] | list[AcceptanceCriterion]
    side_effect_limits: tuple[str, ...] | list[str]
    gates: Gates
    confirmations: tuple[Confirmation, ...] | list[Confirmation] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", _text(self.goal_id, "goal_id"))
        object.__setattr__(self, "end_result", _text(self.end_result, "end result"))
        allowed = _norm_list(self.allowed_scope, "allowed scope")
        forbidden = _norm_list(self.forbidden_scope, "forbidden scope")
        if set(allowed) & set(forbidden):
            raise GoalContractError("a scope item cannot be both allowed and forbidden")
        object.__setattr__(self, "allowed_scope", allowed)
        object.__setattr__(self, "forbidden_scope", forbidden)
        object.__setattr__(self, "constraints", _norm_list(self.constraints, "constraints"))
        object.__setattr__(self, "side_effect_limits", _norm_list(self.side_effect_limits, "side-effect limits"))
        if not isinstance(self.gates, Gates):
            raise GoalContractError("gates are required")
        criteria = _criteria(self.acceptance_criteria)
        if not criteria:
            raise GoalContractError("acceptance criteria are required")
        object.__setattr__(self, "acceptance_criteria", criteria)
        object.__setattr__(self, "confirmations", _confirmations(self.confirmations))

    @property
    def human_confirmed(self) -> bool:
        return any(item.actor_kind == "human" for item in self.confirmations)

    def fingerprint(self) -> str:
        """sha256 of the terms. Confirmation events are not part of the terms."""
        return _digest(self.terms_record())

    def terms_record(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "end_result": self.end_result,
            "allowed_scope": list(self.allowed_scope),
            "forbidden_scope": list(self.forbidden_scope),
            "constraints": list(self.constraints),
            "acceptance_criteria": [item.to_record() for item in self.acceptance_criteria],
            "side_effect_limits": list(self.side_effect_limits),
            "gates": self.gates.to_record(),
        }

    def to_record(self) -> dict:
        record = self.terms_record()
        record["confirmations"] = [item.to_record() for item in self.confirmations]
        return record

    @classmethod
    def from_record(cls, record: object) -> "GoalContract":
        data = _object(record, "goal contract", set(_FINGERPRINT_FIELDS) | {"confirmations"})
        return cls(
            goal_id=data["goal_id"],
            end_result=data["end_result"],
            allowed_scope=data["allowed_scope"],
            forbidden_scope=data["forbidden_scope"],
            constraints=data["constraints"],
            acceptance_criteria=[AcceptanceCriterion.from_record(item) for item in _as_list(data["acceptance_criteria"], "acceptance criteria")],
            side_effect_limits=data["side_effect_limits"],
            gates=Gates.from_record(data["gates"]),
            confirmations=[Confirmation.from_record(item) for item in _as_list(data["confirmations"], "confirmations")],
        )

    def confirm(self, actor_ref: str, at: str, actor_kind: str = "human") -> "GoalContract":
        """Append one human confirmation supplied by the caller."""
        confirmation = Confirmation(actor_kind, actor_ref, at)
        return GoalContract(
            goal_id=self.goal_id,
            end_result=self.end_result,
            allowed_scope=self.allowed_scope,
            forbidden_scope=self.forbidden_scope,
            constraints=self.constraints,
            acceptance_criteria=self.acceptance_criteria,
            side_effect_limits=self.side_effect_limits,
            gates=self.gates,
            confirmations=(*self.confirmations, confirmation),
        )

    def amend(self, **changes) -> "GoalContract":
        """New terms, same Goal-ID, no carried confirmation."""
        unknown = set(changes) - _AMEND_FIELDS
        if unknown:
            raise GoalContractError(f"unknown amendment field: {', '.join(sorted(unknown))}")
        if not changes:
            raise GoalContractError("amendment changes nothing")
        values = {
            "end_result": self.end_result,
            "allowed_scope": self.allowed_scope,
            "forbidden_scope": self.forbidden_scope,
            "constraints": self.constraints,
            "acceptance_criteria": self.acceptance_criteria,
            "side_effect_limits": self.side_effect_limits,
            "gates": self.gates,
        }
        values.update(changes)
        amended = GoalContract(goal_id=self.goal_id, confirmations=(), **values)
        if amended.fingerprint() == self.fingerprint():
            raise GoalContractError("amendment does not change the contract")
        return amended

    def validate_task(self, task_spec: object) -> Validation:
        """Decide whether this task still fits the confirmed terms."""
        fingerprint = _declared_fingerprint(task_spec)
        if fingerprint is not None and fingerprint != self.fingerprint():
            return Validation(Verdict.REVALIDATION_REQUIRED, ("stale_fingerprint",))
        if not self.human_confirmed:
            return Validation(Verdict.HUMAN_CONFIRMATION_REQUIRED, ("unconfirmed",))
        if not isinstance(task_spec, dict):
            return Validation(Verdict.NOT_VERIFIABLE, ("task_spec_invalid",))

        unverifiable: list[str] = []
        extension: list[str] = []
        unknown = sorted(set(task_spec) - _TASK_FIELDS)
        if unknown:
            unverifiable.append("unknown_field")
        if task_spec.get("goal_id") != self.goal_id:
            unverifiable.append("goal_id_mismatch" if "goal_id" in task_spec else "missing_goal_id")
        if fingerprint is None:
            unverifiable.append("missing_fingerprint")

        scope = task_spec.get("scope")
        scope_items = _task_scope(scope)
        if scope_items is None:
            unverifiable.append("scope_invalid")
        else:
            if scope_items & set(self.forbidden_scope):
                extension.append("forbidden_scope")
            if not scope_items <= set(self.allowed_scope):
                extension.append("scope_widened")

        known = {item.id: item for item in self.acceptance_criteria}
        anchors = _task_ids(task_spec.get("acceptance_ids"))
        if anchors is None:
            unverifiable.append("missing_acceptance_anchor")
        elif any(item not in known for item in anchors):
            extension.append("criteria_changed")

        evidence = task_spec.get("evidence_class")
        if not isinstance(evidence, str) or not evidence.strip():
            unverifiable.append("missing_evidence_class")
        elif anchors is not None and anchors and all(item in known for item in anchors):
            required = {known[item].evidence_class for item in anchors}
            if required != {evidence.strip()}:
                unverifiable.append("evidence_class_mismatch")

        if unverifiable:
            return Validation(Verdict.NOT_VERIFIABLE, tuple(unverifiable + extension))
        if extension:
            return Validation(Verdict.HUMAN_CONFIRMATION_REQUIRED, tuple(extension))
        return Validation(Verdict.ACCEPTED, ())


class GoalContractStore:
    """Append-only JSONL. A file over 1 MiB, or a record that does not match, is refused."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, contract: GoalContract) -> None:
        if not isinstance(contract, GoalContract):
            raise GoalContractError("not a goal contract")
        line = _envelope(contract).encode("utf-8")
        if len(line) > MAX_FILE_BYTES:
            raise GoalContractError("record exceeds 1 MiB")
        existing = self._size()
        if existing > MAX_FILE_BYTES or existing + len(line) > MAX_FILE_BYTES:
            raise GoalContractError("record file exceeds 1 MiB")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(line)

    def read(self) -> tuple[GoalContract, ...]:
        if not self.path.exists():
            return ()
        raw = self._read_bounded()
        if not raw:
            return ()
        if not raw.endswith(b"\n"):
            raise GoalContractError("record file is truncated")
        try:
            text = raw.decode("utf-8")
        except UnicodeError as exc:
            raise GoalContractError("record file is not utf-8") from exc
        lines = text.split("\n")[:-1]
        if not lines or any(line == "" for line in lines):
            raise GoalContractError("record file has an empty line")
        return tuple(_parse_envelope(line) for line in lines)

    def _size(self) -> int:
        if not self.path.exists():
            return 0
        size = self.path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise GoalContractError("record file exceeds 1 MiB")
        return size

    def _read_bounded(self) -> bytes:
        with self.path.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise GoalContractError("record file exceeds 1 MiB")
        return data


def _envelope(contract: GoalContract) -> str:
    record = contract.to_record()
    return _canonical({"contract": record, "sha256": _digest(record)}) + "\n"


def _parse_envelope(line: str) -> GoalContract:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError as exc:
        raise GoalContractError("record is not json") from exc
    data = _object(parsed, "stored record", {"contract", "sha256"})
    fields = set(_FINGERPRINT_FIELDS) | {"confirmations"}
    _object(data["contract"], "goal contract", fields)
    digest = data["sha256"]
    if not isinstance(digest, str) or digest != _digest(data["contract"]):
        raise GoalContractError("record was tampered")
    return GoalContract.from_record(data["contract"])


def _digest(record: dict) -> str:
    return hashlib.sha256(_canonical(record).encode("utf-8")).hexdigest()


def _canonical(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > _MAX_TEXT or "\n" in value or "\r" in value:
        raise GoalContractError(f"{label} must be a single line")
    return value.strip()


def _norm_list(value: object, label: str) -> tuple[str, ...]:
    items = _as_list(value, label)
    return tuple(sorted({_text(item, label) for item in items}))


def _as_list(value: object, label: str) -> list:
    if not isinstance(value, (list, tuple)):
        raise GoalContractError(f"{label} must be a list")
    return list(value)


def _criteria(value: object) -> tuple[AcceptanceCriterion, ...]:
    items = _as_list(value, "acceptance criteria")
    criteria = []
    for item in items:
        if not isinstance(item, AcceptanceCriterion):
            raise GoalContractError("acceptance criterion is invalid")
        criteria.append(item)
    criteria.sort(key=lambda item: item.id)
    ids = [item.id for item in criteria]
    if len(ids) != len(set(ids)):
        raise GoalContractError("acceptance criterion ids must be unique")
    return tuple(criteria)


def _confirmations(value: object) -> tuple[Confirmation, ...]:
    items = _as_list(value, "confirmations")
    confirmed = []
    for item in items:
        if not isinstance(item, Confirmation):
            raise GoalContractError("confirmation is invalid")
        confirmed.append(item)
    return tuple(confirmed)


def _object(value: object, label: str, fields: set[str]) -> dict:
    if not isinstance(value, dict):
        raise GoalContractError(f"{label} must be an object")
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        raise GoalContractError(f"{label} has unknown field: {', '.join(unknown)}")
    if missing:
        raise GoalContractError(f"{label} is missing {', '.join(missing)}")
    return value


def _declared_fingerprint(task_spec: object) -> str | None:
    if not isinstance(task_spec, dict) or "goal_fingerprint" not in task_spec:
        return None
    value = task_spec.get("goal_fingerprint")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _task_scope(value: object) -> set[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    items = set()
    for item in value:
        if not isinstance(item, str) or not item.strip() or "\n" in item:
            return None
        items.add(item.strip())
    return items


def _task_ids(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, (list, tuple)) or not value:
        return None
    ids = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or "\n" in item:
            return None
        ids.append(item.strip())
    return tuple(ids)
