"""Judge a journal for the Gate G3 measurements.

PASS and FAIL are local words for this judge. ``verified`` is always false.
A fixture that passes the judge does not prove Gate 3, and a skipped Windows
run is not a pass.

The measured human relay count is the number of EFFECT_CONFIRMED and
RETRY_AUTHORIZED events in the journal. A count supplied by the caller is
not accepted. An unknown journal, an unknown ledger, or an unknown event
type fails with the count left unmeasured.
"""

from __future__ import annotations

from dataclasses import dataclass

from courier_core.events import HUMAN_DECISIONS, EventType

CANONICAL_WINDOWS_CORE_COMMIT = "ad7dbc2c42273b755d8daefa16ad8762e55b1a07"

WINDOWS_CORE_SKIP_REASON = (
    "The canonical Windows-core A→B service proof is commit "
    "ad7dbc2c42273b755d8daefa16ad8762e55b1a07. It was read and is not modified. "
    "It needs that commit's LiveService worker loop, depends_on, and from_input, "
    "which are not in this tree, plus a Windows worker host. "
    "Skipping is not a pass and is not VERIFIED."
)


@dataclass(frozen=True)
class GateG3Assessment:
    status: str
    human_relay_count: int | None
    ledger_ok: bool | None
    replay: bool | None
    reason: str

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "FAIL"}:
            raise ValueError("Gate G3 assessment status must be PASS or FAIL")

    @property
    def verified(self) -> bool:
        return False


def assess_gate_g3(journal) -> GateG3Assessment:
    """Return FAIL unless every measured check holds. Never reports verified."""
    if journal is None:
        return _fail("unknown journal")
    verify = getattr(journal, "verify_chain", None)
    read = getattr(journal, "events", None)
    if not callable(verify) or not callable(read):
        return _fail("unknown journal")
    try:
        chain = verify()
    except Exception as exc:
        return _fail(f"unknown ledger: {type(exc).__name__}")
    ledger_ok = getattr(chain, "ok", None)
    if ledger_ok is None:
        return _fail("unknown ledger")
    if ledger_ok is not True:
        return _fail("incomplete ledger", ledger=False)
    try:
        raw_events = list(read())
    except Exception as exc:
        return _fail(f"unknown events: {type(exc).__name__}", ledger=True)

    parsed: list[tuple[int, EventType, str | None, dict]] = []
    for event in raw_events:
        kind = _known_type(getattr(event, "type", None))
        seq = getattr(event, "seq", None)
        payload = getattr(event, "payload", None)
        if kind is None or isinstance(seq, bool) or not isinstance(seq, int) or not isinstance(payload, dict):
            return _fail("unknown event type", ledger=True)
        parsed.append((seq, kind, getattr(event, "task_id", None), payload))
    if len({seq for seq, _, _, _ in parsed}) != len(parsed):
        return _fail("unknown event", ledger=True)
    parsed.sort(key=lambda item: item[0])

    human = sum(1 for _, kind, _, _ in parsed if kind in HUMAN_DECISIONS)
    reasons: list[str] = []
    if human != 0:
        reasons.append(f"human_relay_count measured {human}")

    starts = [seq for seq, kind, _, _ in parsed if kind is EventType.CONTROLLER_STARTED]
    restart = starts[1] if len(starts) >= 2 else None
    if restart is None:
        reasons.append("restart was not shown")

    created = [
        (seq, task_id, payload)
        for seq, kind, task_id, payload in parsed
        if kind is EventType.TASK_CREATED and isinstance(task_id, str)
    ]
    if len(created) != 2 or created[0][1] == created[1][1]:
        reasons.append("A and B were not both recorded")
        return _finish(human, True, None, reasons)

    _, task_a, _ = created[0]
    created_b, task_b, payload_b = created[1]
    link = payload_b.get("depends_on")
    if link is None:
        reasons.append("depends_on was not recorded")
    elif link != task_a:
        reasons.append("depends_on does not name A")
    if restart is None or created_b >= restart:
        reasons.append("B was not prepared before the restart")

    claim_a = _seqs(parsed, EventType.TASK_CLAIMED, task_a)
    claimed_again = len(claim_a) > 1 or (restart is not None and any(seq >= restart for seq in claim_a))
    if claimed_again:
        replay = True
        reasons.append("replay of A")
    elif restart is not None:
        replay = False
    else:
        replay = None

    _require_verified_completion(parsed, "A", task_a, reasons)
    _require_verified_completion(parsed, "B", task_b, reasons)
    done_a = _seqs(parsed, EventType.TASK_COMPLETE, task_a)
    claim_b = _seqs(parsed, EventType.TASK_CLAIMED, task_b)
    if len(done_a) != 1 or restart is None or done_a[0] >= restart:
        reasons.append("A did not finish before the restart")
    if len(done_a) == 1 and len(claim_b) == 1 and claim_b[0] <= done_a[0]:
        reasons.append("B was not claimed after A completed")
    if len(claim_b) != 1 or restart is None or claim_b[0] <= restart:
        reasons.append("B was not claimed after the restart")
    if any(kind is EventType.TASK_BLOCKED and task_id in {task_a, task_b}
           for _, kind, task_id, _ in parsed):
        reasons.append("blocked is not a Gate G3 pass")
    return _finish(human, True, replay, reasons)


def _require_verified_completion(parsed, label: str, task_id: str, reasons: list[str]) -> None:
    claimed = _seqs(parsed, EventType.TASK_CLAIMED, task_id)
    accepted = _seqs(parsed, EventType.RESULT_ACCEPTED, task_id)
    complete = _seqs(parsed, EventType.TASK_COMPLETE, task_id)
    if len(claimed) != 1 or len(accepted) != 1 or len(complete) != 1:
        reasons.append(f"{label} did not complete")
        return
    if not (claimed[0] < accepted[0] < complete[0]):
        reasons.append(f"{label} did not complete")


def _seqs(parsed, kind: EventType, task_id: str) -> list[int]:
    return [seq for seq, event_type, owner, _ in parsed if event_type is kind and owner == task_id]


def _known_type(raw) -> EventType | None:
    if isinstance(raw, EventType):
        return raw
    if isinstance(raw, str):
        try:
            return EventType(raw)
        except ValueError:
            return None
    return None


def _fail(reason: str, *, human: int | None = None, ledger: bool | None = None,
          replay: bool | None = None) -> GateG3Assessment:
    return GateG3Assessment("FAIL", human, ledger, replay, reason)


def _finish(human: int, ledger: bool, replay: bool | None, reasons: list[str]) -> GateG3Assessment:
    unique = list(dict.fromkeys(reasons))
    if human != 0 or ledger is not True or replay is not False or unique:
        if not unique:
            unique = ["measured checks are incomplete"]
        return GateG3Assessment("FAIL", human, ledger, replay, "; ".join(unique))
    return GateG3Assessment(
        "PASS", human, ledger, replay,
        "human_relay_count measured 0; ledger complete; A was not claimed after restart",
    )
