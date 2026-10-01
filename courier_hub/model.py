"""Customer-facing projection of canonical runtime truth (lane L5).

Pure functions: TaskState + the task's journaled events in, plain dicts out.
Nothing here stores state, decides anything or talks to the network; the
controller (courier_core) stays the only writer and the only authority.

Home has three piles and they are PROJECTIONS, not states of their own:

    BLOCKED                                   -> needs_you
    COMPLETE / FAILED / CANCELLED             -> done
    QUEUED / CLAIMED / RUNNING / VERIFYING /
    ACCEPTED / RETRY_PENDING                  -> working

Done keeps the runtime's distinctions (never one generic success):

    COMPLETE + resolution verified            -> verified        "Checked by Courier"
    COMPLETE + resolution effect_confirmed    -> human_confirmed "Confirmed by <actor>"
    FAILED                                    -> could_not_complete
    CANCELLED + cancelled_effect_unknown      -> outcome_uncertain
    CANCELLED                                 -> stopped

Internal identifiers (dispatch, attempt, worker, effect key, event names)
only appear in the ``support`` section of an item.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

PILE_NEEDS_YOU = "needs_you"
PILE_WORKING = "working"
PILE_DONE = "done"

WORKING_STATUSES = frozenset({"QUEUED", "CLAIMED", "RUNNING", "VERIFYING", "ACCEPTED", "RETRY_PENDING"})
DONE_STATUSES = frozenset({"COMPLETE", "FAILED", "CANCELLED"})

OUTCOME_VERIFIED = "verified"
OUTCOME_HUMAN_CONFIRMED = "human_confirmed"
OUTCOME_COULD_NOT_COMPLETE = "could_not_complete"
OUTCOME_STOPPED = "stopped"
OUTCOME_UNCERTAIN = "outcome_uncertain"
OUTCOME_COMPLETED_UNLABELLED = "completed"  # COMPLETE without a resolution (older journals): no check mark

DECISIONS = ("effect_confirmed", "retry_authorized", "cancel")

# What a repeated attempt would mean in the customer's world, per adapter. An
# adapter whose repeat could move money never gets a one-tap retry here.
ADAPTER_COPY = {
    "synthetic": {
        "title": "Synthetic test task",
        "action": "write the test file",
        "repeat_consequence": "The test file may be written a second time.",
        "retry_offered": True,
    },
}
DEFAULT_COPY = {
    "title": "Courier task",
    "action": "carry out the action",
    "repeat_consequence": "The action may happen twice.",
    "retry_offered": True,
}

_PLAIN_STEPS = {
    "TASK_CREATED": "You asked Courier to do this",
    "TASK_CLAIMED": None,  # internal hand-off; shown only as part of "started"
    "TASK_STARTED": "Courier started the work",
    "TASK_PROGRESS": None,
    "RESULT_READY": "A result came back",
    "RESULT_ACCEPTED": "Courier checked the result",
    "RESULT_REJECTED": "Courier did not accept the result",
    "TASK_COMPLETE": "Finished",
    "LEASE_EXPIRED": "The work was interrupted",
    "TASK_RETRY_SCHEDULED": "Courier resumed after an interruption",
    "TASK_BLOCKED": "Courier stopped and asked you to decide",
    "TASK_FAILED": "Courier couldn't complete this safely",
    "TASK_CANCEL_REQUESTED": "Stop was requested",
    "TASK_CANCELLED": "Stopped",
    "EFFECT_CONFIRMED": "A person confirmed it happened",
    "RETRY_AUTHORIZED": "A person authorised one more attempt",
    "LATE_RESULT_DISCARDED": "A late report arrived after Courier stopped waiting",
}


def _get(task: Any, name: str, default: Any = None) -> Any:
    if isinstance(task, dict):
        return task.get(name, default)
    return getattr(task, name, default)


def _status(task: Any) -> str:
    status = _get(task, "status")
    return getattr(status, "value", status)


def _type(event: Any) -> str:
    kind = _get(event, "type")
    return getattr(kind, "value", kind)


def _payload(event: Any) -> dict:
    payload = _get(event, "payload") or {}
    return payload if isinstance(payload, dict) else {}


def copy_for(task: Any) -> dict:
    return ADAPTER_COPY.get(_get(task, "adapter"), DEFAULT_COPY)


def title_of(task: Any) -> str:
    params = _get(task, "params") or {}
    title = params.get("title") if isinstance(params, dict) else None
    if isinstance(title, str) and title.strip():
        return title.strip()[:120]
    return copy_for(task)["title"]


def pile_of(task: Any) -> str:
    status = _status(task)
    if status == "BLOCKED":
        return PILE_NEEDS_YOU
    if status in DONE_STATUSES:
        return PILE_DONE
    if status in WORKING_STATUSES:
        return PILE_WORKING
    raise ValueError(f"unknown task status {status!r}")


def done_outcome(task: Any) -> str:
    status, resolution = _status(task), _get(task, "resolution")
    if status == "COMPLETE":
        if resolution == "verified":
            return OUTCOME_VERIFIED
        if resolution == "effect_confirmed":
            return OUTCOME_HUMAN_CONFIRMED
        return OUTCOME_COMPLETED_UNLABELLED
    if status == "FAILED":
        return OUTCOME_COULD_NOT_COMPLETE
    if status == "CANCELLED":
        return OUTCOME_UNCERTAIN if resolution == "cancelled_effect_unknown" else OUTCOME_STOPPED
    raise ValueError(f"task status {status!r} is not terminal")


def outcome_copy(task: Any) -> dict:
    """Label, explanation and mark for a Done item. Only 'verified' gets the check mark."""
    outcome = done_outcome(task)
    who = display_actor(_get(task, "decided_by"))
    table = {
        OUTCOME_VERIFIED: ("Checked by Courier", "Courier checked the result against the evidence.", "check"),
        OUTCOME_HUMAN_CONFIRMED: (f"Confirmed by {who}",
                                  f"{who} confirmed it happened. Courier did not verify it.", "signature"),
        OUTCOME_COULD_NOT_COMPLETE: ("Couldn't complete this safely",
                                     "Courier stopped because it could not finish this safely.", "open-ring"),
        OUTCOME_STOPPED: ("Stopped", "This was stopped before it finished.", "gate"),
        OUTCOME_UNCERTAIN: ("Outcome uncertain",
                            "Courier stopped trying. The earlier action may already have happened.", "gate-question"),
        OUTCOME_COMPLETED_UNLABELLED: ("Completed", "Finished, but this record does not say how it was checked.",
                                       "neutral"),
    }
    label, explanation, mark = table[outcome]
    return {"outcome": outcome, "label": label, "explanation": explanation, "mark": mark}


def display_actor(actor: Optional[str]) -> str:
    """'desktop:ana' -> 'ana'. The full actor id stays in support details."""
    if not actor:
        return "a person"
    return actor.split(":", 1)[1] if ":" in actor and actor.split(":", 1)[1] else actor


def working_phase(task: Any) -> dict:
    status = _status(task)
    if _get(task, "cancel_requested"):
        return {"phase": "stopping", "label": "Stopping",
                "next": "Courier is stopping at the next safe point."}
    if status == "QUEUED":
        return {"phase": "waiting", "label": "Waiting to start",
                "next": "Courier starts this as soon as a worker is free."}
    if status in ("CLAIMED", "RUNNING", "RETRY_PENDING"):
        # RETRY_PENDING is an internal recovery step: the card does not change for it.
        return {"phase": "in_progress", "label": "In progress",
                "next": "Courier expects a result from the running work."}
    if status in ("VERIFYING", "ACCEPTED"):
        return {"phase": "checking", "label": "Checking the result",
                "next": "Courier is checking the result against the evidence."}
    raise ValueError(f"task status {status!r} is not working")


def authority_of(task: Any) -> dict:
    """What Courier may do without asking again, and what it must ask about.

    Only what the current runtime enforces is stated as authority. Standing,
    user-granted authority is not implemented yet and is never implied.
    """
    action = copy_for(task)["action"]
    if _get(task, "effect_class") == "idempotent":
        may = [action.capitalize(), "Try again by itself after an interruption (repeating is safe for this task)"]
        must_ask = ["Nothing else: this task has no step that needs your approval"]
    else:
        may = [f"{action.capitalize()} once"]
        must_ask = ["Anything after an unclear outcome: it never repeats this on its own"]
    return {"may": may, "must_ask": must_ask,
            "note": "Standing permissions you grant ahead of time are not available yet."}


def needs_you_card(task: Any, events: Iterable[Any]) -> dict:
    copy = copy_for(task)
    events = list(events)
    late = [e for e in events if _type(e) == "LATE_RESULT_DISCARDED"]
    choices = [{"decision": "effect_confirmed", "label": "It happened",
                "explains": "Mark it done as confirmed by you. Courier will not run it again."}]
    retry_blocked = None
    if not copy["retry_offered"]:
        retry_blocked = "Trying again is not offered for this kind of action."
    elif _get(task, "cancel_requested"):
        retry_blocked = "Stop was already requested, so Courier won't try again."
    elif (_get(task, "attempt") or 0) >= 100:
        retry_blocked = "The attempt limit is reached."
    if retry_blocked is None:
        choices.append({"decision": "retry_authorized", "label": "Try once more",
                        "explains": "One more try, authorised by you. " + copy["repeat_consequence"],
                        "confirm": (f"Courier couldn't tell whether it managed to {copy['action']}. "
                                    f"Trying again could repeat it. {copy['repeat_consequence']}")})
    choices.append({"decision": "cancel", "label": "Stop here",
                    "explains": "Courier stops trying. The earlier action may still have happened."})
    evidence = [{"what": "A late report arrived", "outcome": _payload(e).get("outcome"),
                 "at": _get(e, "ts_utc")} for e in late]
    return {
        "question": f"Did Courier manage to {copy['action']}?",
        "why": "Courier lost contact with the work before it could confirm whether the action happened.",
        "consequence": copy["repeat_consequence"],
        "choices": choices,
        "retry_unavailable_reason": retry_blocked,
        "evidence": evidence,
        "blocked_attempt": _get(task, "attempt"),
    }


def _last_change(events: List[Any]) -> Optional[dict]:
    for event in reversed(events):
        step = _PLAIN_STEPS.get(_type(event))
        if step:
            return {"what": step, "at": _get(event, "ts_utc")}
    return None


def card(task: Any, events: Iterable[Any]) -> dict:
    """The Home card for one task."""
    events = list(events)
    pile = pile_of(task)
    base = {"id": _get(task, "task_id"), "title": title_of(task), "pile": pile,
            "last_change": _last_change(events)}
    if pile == PILE_NEEDS_YOU:
        base["needs_you"] = needs_you_card(task, events)
        base["label"] = "Courier needs you to decide something"
    elif pile == PILE_WORKING:
        phase = working_phase(task)
        base.update({"label": phase["label"], "phase": phase["phase"], "next": phase["next"],
                     "authority": authority_of(task),
                     "stop": {"label": "Stop",
                              "explains": "Courier stops at the next safe point. If the action already "
                                          "started, its result may still arrive."}})
    else:
        base.update(outcome_copy(task))
    return base


def receipt(task: Any, events: Iterable[Any]) -> dict:
    """The seven customer questions, answered only from recorded events."""
    events = list(events)
    copy = copy_for(task)
    pile = pile_of(task)
    steps = []
    for event in events:
        step = _PLAIN_STEPS.get(_type(event))
        if step and (not steps or steps[-1]["what"] != step):
            steps.append({"what": step, "at": _get(event, "ts_utc")})
    decisions = []
    for event in events:
        kind, payload = _type(event), _payload(event)
        if kind in ("EFFECT_CONFIRMED", "RETRY_AUTHORIZED") or (
                kind in ("TASK_CANCEL_REQUESTED", "TASK_CANCELLED") and payload.get("actor")):
            if kind == "TASK_CANCEL_REQUESTED" and any(
                    _type(e) == "TASK_CANCELLED" and _payload(e).get("actor") == payload.get("actor") for e in events):
                continue  # one human "stop" decision, not two lines
            decisions.append({"who": display_actor(payload.get("actor")),
                              "decided": _PLAIN_STEPS[kind] if kind != "TASK_CANCELLED" else "Chose to stop",
                              "reason": payload.get("reason"), "at": _get(event, "ts_utc")})
    accepted = [e for e in events if _type(e) == "RESULT_ACCEPTED"]
    if accepted:
        how = "Checked by Courier: " + (str(_payload(accepted[-1]).get("reason") or "the evidence matched"))
    elif pile == PILE_DONE and done_outcome(task) == OUTCOME_HUMAN_CONFIRMED:
        how = f"Confirmed by {display_actor(_get(task, 'decided_by'))}. Courier did not verify it."
    elif pile == PILE_DONE:
        how = "Courier has no verified evidence that this happened."
    else:
        how = "Not known yet."
    # "Resumed" only when Courier actually continued after an interruption; an
    # interruption that ended in a question for a person is not a resumption.
    resumed = any(_type(e) == "TASK_RETRY_SCHEDULED" for e in events)
    if pile == PILE_DONE:
        happened = outcome_copy(task)["label"]
    elif pile == PILE_NEEDS_YOU:
        happened = "Unclear: Courier is waiting for your decision"
    else:
        happened = working_phase(task)["label"]
    authority = authority_of(task)
    later = [{"what": _PLAIN_STEPS["LATE_RESULT_DISCARDED"], "at": _get(e, "ts_utc")}
             for e in events if _type(e) == "LATE_RESULT_DISCARDED"]
    evidence = []
    for event in events:
        if _type(event) == "RESULT_READY":
            for artifact in _payload(event).get("artifacts") or []:
                if isinstance(artifact, dict) and artifact.get("path"):
                    evidence.append({"name": str(artifact["path"]).rsplit("/", 1)[-1],
                                     "accepted": any(_get(a, "result_id") == _get(event, "result_id")
                                                     for a in accepted)})
    return {
        "understood": f"Courier was asked to {copy['action']} ({title_of(task)}).",
        "authorized": authority,
        "tried": steps,
        "resumed": resumed,
        "happened": happened,
        "how_known": how,
        "decisions": decisions,
        "changed_later": later,
        "evidence": evidence,
    }


def support(task: Any, events: Iterable[Any]) -> dict:
    """Diagnostics for support: internal ids and raw event names live only here."""
    record = task.to_record() if hasattr(task, "to_record") else dict(task)
    return {
        "task": {k: record.get(k) for k in ("task_id", "status", "resolution", "decided_by", "attempt",
                                            "dispatch_id", "worker_id", "effect_class", "adapter",
                                            "last_reason", "late_results")},
        "events": [{"seq": _get(e, "seq"), "type": _type(e), "attempt": _get(e, "attempt"),
                    "dispatch_id": _get(e, "dispatch_id"), "result_id": _get(e, "result_id"),
                    "at": _get(e, "ts_utc"), "hash": _get(e, "hash")} for e in events],
    }


def home(tasks: Iterable[Any], events_by_task: dict, done_limit: int = 50) -> dict:
    piles = {PILE_NEEDS_YOU: [], PILE_WORKING: [], PILE_DONE: []}
    for task in tasks:
        piles[pile_of(task)].append(card(task, events_by_task.get(_get(task, "task_id"), [])))

    def changed(c):
        return (c.get("last_change") or {}).get("at") or ""

    piles[PILE_NEEDS_YOU].sort(key=changed)  # oldest decision first
    piles[PILE_WORKING].sort(key=changed, reverse=True)
    piles[PILE_DONE].sort(key=changed, reverse=True)
    piles[PILE_DONE] = piles[PILE_DONE][:done_limit]
    return {"needs_you": piles[PILE_NEEDS_YOU], "working": piles[PILE_WORKING], "done": piles[PILE_DONE],
            "counts": {k: len(v) for k, v in piles.items()}}
