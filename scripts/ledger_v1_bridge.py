"""One-shot bridge from the coordination ledger to the local V1 controller.

One invocation. No loop, no daemon, no scheduler. The controller URL must be
loopback. The token is read from <home>/run/controller.token and is never
printed.

Exit 0 when the pass is idle or finished. Exit 2 when config or a mission
fails closed. Exit 75 when the controller cannot be reached; the next
invocation retries the same claim and idempotency key.

    python scripts/ledger_v1_bridge.py --home DIR --agent-id GOOGLE_WINDOWS \\
        --host-id WINDOWS_REMOTE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from courier_core.events import EFFECT_CLASSES, MAX_ATTEMPTS_LIMIT, MAX_ID_LENGTH
from courier_core.verification import ADAPTER_NAME
from scripts.coordination_ledger import (
    AgentID,
    CoordinationEvent,
    EventType,
    HostID,
    MissionStatus,
    parse_timestamp,
)
from scripts.coordination_resume import CLAIMED, claim_mission, discover_resumable, reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.handoff_spend import handoff_spend_block

MAX_STATE_BYTES = 1024 * 1024
MAX_LEASE_TTL_S = 3600
MAX_TIMEOUT_S = 7 * 24 * 3600
HTTP_TIMEOUT_S = 10.0
EXIT_CONFIG = 2
EXIT_RETRY = 75
DEFAULT_CONTROLLER = "http://127.0.0.1:8080"
TASK_FIELDS = ("adapter", "params", "effect_class", "max_attempts", "lease_ttl_s", "timeout_s")
TERMINAL_FAILURE = frozenset({"FAILED", "CANCELLED"})
GOAL_FIELDS = ("goal_id", "goal_fingerprint")
MAX_GOAL_LEN = 128
GOAL_TOKEN = re.compile(r"[A-Za-z0-9._:-]+\Z")
MISSION_STATUSES = frozenset({"POSTED", "FINAL_DONE", "BLOCKED", "ERROR"})
REASON_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,31}\Z")
INPUTS_FIELD = "inputs_from"
MAX_INPUTS = 16
MAX_INPUT_ARTIFACTS = 64  # keeps B's params far below the worker's 64 KiB envelope
MAX_ARTIFACT_PATH = 1024
SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")


class ConfigError(Exception):
    """Local config or a mission cannot be trusted. Nothing is posted."""


class ControllerDown(Exception):
    """The local controller could not be reached. Retry the same claim later."""


def main(argv=None, *, http=None, stdout=None, stderr=None) -> int:
    parser = argparse.ArgumentParser(description="One-shot coordination ledger to V1 task bridge")
    parser.add_argument("--home", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--host-id", required=True)
    parser.add_argument("--controller", default=DEFAULT_CONTROLLER)
    parser.add_argument("--timeout", type=float, default=HTTP_TIMEOUT_S)
    args = parser.parse_args(argv)
    home = Path(args.home)
    token = _read_token(home / "run" / "controller.token")
    say_out = lambda line: (stdout or _print)(_redact(line, token))
    say_err = lambda line: (stderr or _print_err)(_redact(line, token))
    if args.timeout <= 0 or not _loopback(args.controller):
        say_err("controller must be loopback and timeout must be positive")
        return EXIT_CONFIG
    agent = _authority(AgentID, args.agent_id)
    host = _authority(HostID, args.host_id)
    if agent is None or host is None:
        say_err("unknown agent or host")
        return EXIT_CONFIG
    if not token:
        say_err("controller token is missing")
        return EXIT_CONFIG
    try:
        specs = _load_specs(home / "ledger_tasks.json")
        state = _load_state(home / "ledger_bridge_state.json")
    except ConfigError:
        say_err("malformed ledger bridge config")
        return EXIT_CONFIG
    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    transport = http or _urllib_http

    def emit(record):
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        say_out(line)
        _append(home / "run" / "ledger_bridge.log", line + "\n")

    try:
        if not _feedback(store, state, specs, agent, host, args, transport, token, emit, home):
            return EXIT_CONFIG
        if not _dispatch(store, state, specs, agent, host, args, transport, token, emit, home):
            return EXIT_CONFIG
    except ControllerDown:
        say_err("controller unreachable")
        return EXIT_RETRY
    return 0


def _feedback(store, state, specs, agent, host, args, transport, token, emit, home) -> bool:
    reducer = reduce_store(store)
    ok = True
    for mission_id, mapping in list(state["missions"].items()):
        mission = reducer.get_mission(mission_id)
        if not isinstance(mapping, dict) or mission is None:
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "unmapped"})
            ok = False
            continue
        owner = mission.get("ownership")
        if owner not in (None, agent.value):
            continue
        # Accepted work stays open while this host is offline. A later run
        # finalizes the same task. It must not become DONE on the offline pass.
        if (
            _host_offline(home, host)
            and mapping.get("posted") is True
            and mapping.get("status") != "FINAL_DONE"
        ):
            emit({
                "mission_id": mission_id,
                "outcome": "blocked",
                "reason": "target_host_unavailable",
                "proof": "SYNTHETIC",
            })
            ok = False
            continue
        spec = specs.get(mission_id)
        goal_kind, goal_reason = _goal_binding(spec)
        if goal_kind == "blocked":
            _park_goal(store, reducer, mission, agent, host, goal_reason)
            _stamp(home / "ledger_bridge_state.json", state, mapping, "BLOCKED", _goal_reason_code(goal_reason))
            emit({"mission_id": mission_id, "outcome": "blocked", "reason": goal_reason})
            continue
        view = _task_view(transport, args, token, mapping.get("task_id"))
        if view is None:
            if mapping.get("posted"):
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": "task_missing"})
                ok = False
            continue
        event = _feedback_event(mission, mapping, spec, agent, host, view)
        if event is None and view.get("status") == "COMPLETE" and _verified_result_id(view) is None:
            if view.get("resolution") == "effect_confirmed":
                # A person confirmed the effect; that is not a verified result and never FINAL_DONE.
                emit({"mission_id": mission_id, "outcome": "human_confirmed", "task_id": mapping.get("task_id")})
            else:
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": "evidence_missing"})
                ok = False
            continue
        if event is None:
            if view.get("status") in ("COMPLETE", "BLOCKED", *TERMINAL_FAILURE):
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": "identity_missing"})
                ok = False
            continue
        if event.event_type == EventType.FINAL and view.get("status") != "COMPLETE":
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "not_final"})
            ok = False
            continue
        if (
            event.event_type == EventType.FINAL
            and mission.get("status") == MissionStatus.DONE
            and mapping.get("status") == "FINAL_DONE"
        ):
            # One FINAL. A later accepted_result_id must not append a second one.
            # A missing receipt is rewritten once. An unreadable log still fails closed.
            if _verified_result_id(view) != mapping.get("accepted_result_id"):
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": "result_changed"})
                ok = False
                continue
            if mapping.get("journal_proof") is None:
                # P2b backfill: FINAL_DONE written before P2b (or while /result was
                # unavailable) gets its journal proof once; no second FINAL is written.
                proof = _journal_proof_for(transport, args, token, mapping)
                if proof is not None:
                    _stamp(home / "ledger_bridge_state.json", state, mapping, "FINAL_DONE",
                           mapping.get("reason"), journal_proof=proof)
            try:
                if _receipt_present(home, mission_id, "final"):
                    continue
            except ConfigError:
                emit({
                    "mission_id": mission_id,
                    "outcome": "skipped",
                    "reason": "receipt_log_unreadable",
                })
                ok = False
                continue
            emit({"mission_id": mission_id, "outcome": "final", "task_id": mapping.get("task_id")})
            continue
        wrote = _write_new(store, reducer, event)
        outcome = event.event_type.value.lower()
        # The ledger line is durable before the log line. A crash in between
        # must still produce that receipt exactly once on the next invocation.
        # An unreadable log is not proof the receipt was written.
        # A rejected event must not stamp FINAL_DONE or emit final.
        if not wrote:
            try:
                if _receipt_present(home, mission_id, outcome):
                    continue
            except ConfigError:
                emit({
                    "mission_id": mission_id,
                    "outcome": "skipped",
                    "reason": "receipt_log_unreadable",
                })
                ok = False
                continue
            expected = {
                EventType.FINAL: MissionStatus.DONE,
                EventType.BLOCKED: MissionStatus.BLOCKED,
                EventType.ERROR: MissionStatus.ERROR,
            }.get(event.event_type)
            if mission.get("status") != expected:
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": "ledger_rejected"})
                ok = False
                continue
        status_name, reason_code = _status_for_outcome(event, view)
        proof_fields = {}
        if status_name == "FINAL_DONE":
            # P2b: release proof for the work queue. None keeps the workkey NOT_PROVEN.
            proof = _journal_proof_for(
                transport, args, token, {**mapping, "accepted_result_id": _result_id(view)})
            if proof is not None:
                proof_fields["journal_proof"] = proof
        _stamp(
            home / "ledger_bridge_state.json", state, mapping, status_name, reason_code,
            accepted_result_id=_result_id(view),
            attempt=view.get("attempt"),
            evidence_ref=event.evidence_ref,
            spec_fingerprint=mapping.get("spec_fingerprint") or _fingerprint(spec or {}),
            source_sha=_recorded_source(mapping, spec),
            **proof_fields,
        )
        emit({"mission_id": mission_id, "outcome": outcome, "task_id": mapping.get("task_id")})
    return ok


def _dispatch(store, state, specs, agent, host, args, transport, token, emit, home) -> bool:
    reducer = reduce_store(store)
    ok = True
    for checkpoint in discover_resumable(reducer, agent):
        mission_id = checkpoint.mission_id
        spec = specs.get(mission_id)
        if not _spec_ok(spec):
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "malformed_spec"})
            ok = False
            continue
        route_reason = _route_refusal(spec, agent, host)
        if route_reason:
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": route_reason})
            ok = False
            continue
        mapping = state["missions"].get(mission_id)
        if not (isinstance(mapping, dict) and mapping.get("posted") is True):
            # Every new dispatch takes the same decision. A missing estimate is
            # unknown; it is never filled in as 0. An already posted task is not
            # dispatched again.
            cost_reason = handoff_spend_block(spec)
            if cost_reason:
                emit({
                    "mission_id": mission_id,
                    "outcome": "blocked",
                    "reason": cost_reason,
                    "proof": "SYNTHETIC",
                })
                ok = False
                continue
        if _host_offline(home, host):
            mapping = state["missions"].get(mission_id)
            if isinstance(mapping, dict) and mapping.get("posted") is True:
                # The controller already accepted this task. Do not park it and
                # do not post it again; feedback finalizes it once the host is back.
                emit({
                    "mission_id": mission_id,
                    "outcome": "blocked",
                    "reason": "target_host_unavailable",
                    "proof": "SYNTHETIC",
                })
                ok = False
                continue
            mission = reducer.get_mission(mission_id)
            if mission is not None and mission.get("status") != MissionStatus.BLOCKED:
                _park_goal(store, reducer, mission, agent, host, "target_host_unavailable")
            emit({
                "mission_id": mission_id,
                "outcome": "blocked",
                "reason": "target_host_unavailable",
                "proof": "SYNTHETIC",
            })
            ok = False
            continue
        goal_kind, goal_value = _goal_binding(spec)
        if goal_kind == "blocked":
            mission = reducer.get_mission(mission_id)
            if mission is not None:
                _park_goal(store, reducer, mission, agent, host, goal_value)
            mapping = state["missions"].get(mission_id)
            if isinstance(mapping, dict):
                _stamp(
                    home / "ledger_bridge_state.json", state, mapping, "BLOCKED",
                    _goal_reason_code(goal_value),
                )
            emit({"mission_id": mission_id, "outcome": "blocked", "reason": goal_value})
            continue
        goal = goal_value if goal_kind == "ok" else None
        source = _recorded_source(state["missions"].get(mission_id) or {}, spec)
        if source is None:
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "source_sha_missing"})
            ok = False
            continue
        mapping = state["missions"].get(mission_id)
        inputs = None
        if INPUTS_FIELD in spec and mapping is None:
            inputs, why, fatal = _resolve_inputs(
                state, spec, reducer.get_mission(mission_id), transport, args, token, home,
            )
            if inputs is None:
                emit({"mission_id": mission_id, "outcome": "blocked", "reason": why})
                ok = ok and not fatal
                continue
        if INPUTS_FIELD in spec and mapping is not None and not isinstance(mapping.get("inputs"), list):
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "inputs_missing"})
            ok = False
            continue
        if mapping is None:
            claimed = claim_mission(store, agent, host, mission_id)
            if claimed.outcome != CLAIMED or not claimed.event_id:
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": claimed.outcome})
                continue
            key = "ledger:" + claimed.event_id
            if len(key) > MAX_ID_LENGTH:
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": "idempotency_key"})
                ok = False
                continue
            task_id = "task-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
            inputs_digest = _inputs_digest(inputs) if inputs is not None else None
            mapping = {
                "task_id": task_id,
                "claim_event_id": claimed.event_id,
                "idempotency_key": key,
                "posted": False,
                "accepted_result_id": None,
                "attempt": None,
                "spec_fingerprint": _fingerprint(spec),
                "source_sha": source,
                "evidence_ref": _identity(task_id, None, 0, _fingerprint(spec), source, goal, inputs_digest),
            }
            if goal is not None:
                mapping["goal_id"] = goal[0]
                mapping["goal_fingerprint"] = goal[1]
            if inputs is not None:
                # Stored at claim time and posted unchanged on every retry, so
                # the idempotency key always names the same inputs.
                mapping["inputs"] = inputs
                mapping["inputs_digest"] = inputs_digest
            state["missions"][mission_id] = mapping
            _save_state(home / "ledger_bridge_state.json", state)
        if mapping.get("status") == "BLOCKED":
            emit({
                "mission_id": mission_id,
                "outcome": "blocked",
                "reason": mapping.get("reason") or "BLOCKED",
            })
            ok = False
            continue
        if mapping.get("posted"):
            continue
        posted = _post_task(transport, args, token, spec, mapping["idempotency_key"], mapping.get("inputs"))
        if posted.get("rejected"):
            reason_code = posted.get("reason_code") or "CONTROLLER_REJECTED"
            if not _reason_ok(reason_code):
                reason_code = "CONTROLLER_REJECTED"
            mission = reducer.get_mission(mission_id)
            if mission is not None and mission.get("status") != MissionStatus.BLOCKED:
                _park_goal(store, reducer, mission, agent, host, reason_code)
            _stamp(home / "ledger_bridge_state.json", state, mapping, "BLOCKED", reason_code)
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "rejected"})
            ok = False
            continue
        view = _task_view(transport, args, token, mapping["task_id"])
        attempt = view.get("attempt") if isinstance(view, dict) else None
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 0:
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "attempt_missing"})
            ok = False
            continue
        result_id = _result_id(view)
        posted_fields = {
            "posted": True,
            "attempt": attempt,
            "accepted_result_id": result_id,
            "evidence_ref": _identity(
                mapping["task_id"], result_id, attempt, mapping["spec_fingerprint"], mapping["source_sha"], goal,
                _mapping_inputs_digest(mapping),
            ),
        }
        if goal is not None:
            posted_fields["goal_id"] = goal[0]
            posted_fields["goal_fingerprint"] = goal[1]
        _stamp(home / "ledger_bridge_state.json", state, mapping, "POSTED", None, **posted_fields)
        outcome = "duplicate" if posted.get("duplicate") is True else "queued"
        receipt = {"mission_id": mission_id, "outcome": outcome, "task_id": mapping["task_id"]}
        if "agent_id" in spec:
            receipt["proof"] = "SYNTHETIC"
            receipt["owner"] = agent.value
        emit(receipt)
    return ok


def _feedback_event(mission, mapping, spec, agent, host, view):
    status = view.get("status")
    attempt = view.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 0:
        return None
    source = _recorded_source(mapping, spec)
    fingerprint = mapping.get("spec_fingerprint") if isinstance(mapping.get("spec_fingerprint"), str) else None
    if not fingerprint and isinstance(spec, dict):
        fingerprint = _fingerprint(spec)
    task_id = view.get("task_id") or mapping.get("task_id")
    if not source or not fingerprint or not isinstance(task_id, str) or not task_id:
        return None
    result_id = _result_id(view)
    goal_kind, goal_value = _goal_binding(spec)
    goal = goal_value if goal_kind == "ok" else None
    evidence = _identity(task_id, result_id, attempt, fingerprint, source, goal, _mapping_inputs_digest(mapping))
    if status == "COMPLETE":
        # FINAL needs the verifier's accepted result, never a pending or human-confirmed one.
        result_id = _verified_result_id(view)
        if result_id is None:
            return None
        kind, event_type, mission_status = "final", EventType.FINAL, MissionStatus.DONE
        digest_key = f"{task_id}|{result_id}"
    elif status == "BLOCKED":
        kind, event_type, mission_status = "blocked", EventType.BLOCKED, MissionStatus.BLOCKED
        digest_key = f"{task_id}|{_blocker(view)}|{attempt}"
    elif status in TERMINAL_FAILURE:
        kind, event_type, mission_status = "error", EventType.ERROR, MissionStatus.ERROR
        digest_key = f"{task_id}|{status}"
    else:
        return None
    event_id = f"{kind}-" + hashlib.sha256(digest_key.encode("utf-8")).hexdigest()[:16]
    if event_type == EventType.FINAL and status != "COMPLETE":
        return None
    return CoordinationEvent(
        event_id=event_id,
        mission_id=mission["mission_id"],
        agent_id=agent,
        host_id=host,
        event_type=event_type,
        status=mission_status,
        depends_on=list(mission.get("depends_on") or []),
        head=mission.get("head"),
        evidence_ref=evidence,
        created_at=_not_before(mission.get("updated_at")),
        payload_hash=hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
        branch=mission.get("branch"),
        pr=mission.get("pr"),
        blocker=_blocker(view) if event_type == EventType.BLOCKED else None,
        ownership=agent.value,
    )


def _identity(task_id, result_id, attempt, fingerprint, source_sha, goal=None, inputs_digest=None) -> str:
    result = result_id if isinstance(result_id, str) and result_id else "none"
    text = (
        f"task_id={task_id};accepted_result_id={result};attempt={attempt};"
        f"spec_fingerprint={fingerprint};source_sha={source_sha}"
    )
    if goal:
        text += f";goal_id={goal[0]};goal_fingerprint={goal[1]}"
    if inputs_digest:
        text += f";inputs_digest={inputs_digest}"
    return text


def _resolve_inputs(state, spec, mission, transport, args, token, home):
    """Verified upstream outputs named by spec["inputs_from"].

    Returns (inputs, None, False), or (None, reason, fatal). An upstream that is
    not final yet is a wait, not a fault. An undeclared upstream, a result that
    is not the verified one, or bytes on disk that no longer match the journaled
    sha256 are faults: the dependent task is not posted.
    """
    declared = set(mission.get("depends_on") or []) if isinstance(mission, dict) else set()
    inputs = []
    for upstream in spec[INPUTS_FIELD]:
        if upstream not in declared:
            return None, "input_not_declared", True
        mapping = state["missions"].get(upstream)
        if not isinstance(mapping, dict) or mapping.get("status") != "FINAL_DONE":
            return None, "input_not_final", False
        task_id = mapping.get("task_id")
        accepted = mapping.get("accepted_result_id")
        result = _task_result(transport, args, token, task_id)
        if (result is None or result.get("task_id") != task_id or not isinstance(accepted, str)
                or result.get("result_id") != accepted):
            return None, "input_unverified", True
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return None, "input_unverified", True
        if len(inputs) + len(artifacts) > MAX_INPUT_ARTIFACTS:
            return None, "input_too_large", True
        for artifact in artifacts:
            path = artifact.get("path") if isinstance(artifact, dict) else None
            digest = artifact.get("sha256") if isinstance(artifact, dict) else None
            if not _artifact_path_ok(path) or not isinstance(digest, str) or not SHA256_HEX.fullmatch(digest):
                return None, "input_unverified", True
            if _file_sha256(home, path) != digest:
                return None, "input_digest_mismatch", True
            inputs.append({"mission_id": upstream, "task_id": task_id, "result_id": accepted,
                           "path": path, "sha256": digest})
    inputs.sort(key=lambda item: (item["mission_id"], item["path"]))
    return inputs, None, False


def _inputs_digest(inputs) -> str:
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _mapping_inputs_digest(mapping):
    value = mapping.get("inputs_digest") if isinstance(mapping, dict) else None
    return value if isinstance(value, str) and SHA256_HEX.fullmatch(value) else None


def _artifact_path_ok(path) -> bool:
    if not isinstance(path, str) or not path or len(path) > MAX_ARTIFACT_PATH or "\\" in path or "\x00" in path:
        return False
    parts = path.split("/")
    return len(parts) >= 3 and parts[0] == "artifacts" and all(part not in ("", ".", "..") for part in parts)


def _file_sha256(home, path):
    """sha256 of <home>/<path>, or None when it is missing, not a file, or escapes artifacts/."""
    root = (Path(home) / "artifacts").resolve()
    target = (Path(home) / path).resolve()
    if root not in target.parents or not target.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _result_id(view):
    if not isinstance(view, dict):
        return None
    # For a COMPLETE task, only a verifier-accepted result can finalize; pending results must never emit FINAL
    if view.get("status") == "COMPLETE":
        val = view.get("accepted_result_id")
        return val if isinstance(val, str) and val else None
    for key in ("accepted_result_id", "result_id", "pending_result_id"):
        value = view.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _verified_result_id(view):
    """The accepted result of a verified COMPLETE, else None.

    A missing resolution is not verified. Older views that omitted the field
    must not finalize.
    """
    if not isinstance(view, dict) or view.get("resolution") != "verified":
        return None
    value = view.get("accepted_result_id")
    return value if isinstance(value, str) and value else None


def _blocker(view) -> str:
    reason = view.get("last_reason") if isinstance(view, dict) else None
    if not isinstance(reason, str) or not reason.strip():
        return "BLOCKED"
    return reason.strip()[:500]


def _recorded_source(mapping, spec):
    recorded = mapping.get("source_sha") if isinstance(mapping, dict) else None
    if isinstance(recorded, str) and _sha_ok(recorded):
        return recorded
    if isinstance(spec, dict) and "source_sha" in spec:
        declared = spec.get("source_sha")
        return declared if _sha_ok(declared) else None
    found = _git_head()
    return found if _sha_ok(found) else None


def _git_head() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip().lower()


def _sha_ok(value) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def _with_admitted_estimate(spec, params):
    """The params the controller stores. A top-level estimate is copied in.

    A missing estimate is not replaced with 0. Goal fields and verified inputs
    stay out of this copy; the caller adds those itself.
    """
    copied = dict(params)
    if isinstance(spec, dict) and "estimated_cost_eur" not in copied and "estimated_cost_eur" in spec:
        copied["estimated_cost_eur"] = spec["estimated_cost_eur"]
    return copied


def _fingerprint(spec) -> str:
    """Identity of the posted task fields, including the admitted estimate.

    The estimate is part of the receipt. A top-level 0 and the same 0 inside
    params name one task. Goal fields and inputs are recorded beside this hash.
    """
    payload = {name: spec[name] for name in TASK_FIELDS if name in spec} if isinstance(spec, dict) else {}
    params = payload.get("params")
    if isinstance(params, dict):
        payload["params"] = _with_admitted_estimate(spec, params)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _event_admitted(reducer, event) -> bool:
    """True only when the reducer would accept this event as new mission truth.

    Called before any append. A duplicate, unknown authority, unusable
    timestamp, stale checkpoint, or conflicting live owner is not written.
    """
    if not isinstance(event, CoordinationEvent):
        return False
    if not isinstance(event.event_id, str) or not event.event_id:
        return False
    if not isinstance(event.mission_id, str) or not event.mission_id:
        return False
    if not isinstance(event.evidence_ref, str) or not isinstance(event.payload_hash, str):
        return False
    if event.event_id in reducer.processed_event_ids:
        return False
    if event.agent_id == AgentID.UNKNOWN or event.host_id == HostID.UNKNOWN:
        return False
    event_ts = parse_timestamp(event.created_at)
    if event_ts is None:
        return False
    mission = reducer.missions.get(event.mission_id)
    if mission is None:
        return True
    updated = parse_timestamp(mission.get("updated_at"))
    if updated is None or event_ts < updated:
        return False
    new_owner = event.ownership or event.agent_id.value
    current_owner = mission.get("ownership")
    if current_owner and current_owner != new_owner:
        if event.event_type == EventType.ASSIGNED:
            if mission.get("status") != MissionStatus.ERROR:
                return False
        elif event.event_type == EventType.CANCELLED:
            if (
                reducer.lease_ttl_s is not None
                and (event_ts - updated).total_seconds() < reducer.lease_ttl_s
            ):
                return False
        else:
            return False
    return True


def _write_new(store, reducer, event) -> bool:
    if not _event_admitted(reducer, event):
        return False
    if not store.write_event(event):
        raise ConfigError("ledger write failed")
    if not reducer.apply(event):
        raise ConfigError("ledger event rejected after validation")
    return True


def _task_view(transport, args, token, task_id):
    if not isinstance(task_id, str) or not task_id:
        return None
    url = args.controller.rstrip("/") + "/v1/tasks/" + urllib.parse.quote(task_id, safe="")
    status, raw = _request(transport, "GET", url, {"X-Courier-Token": token, "Accept": "application/json"}, None, args.timeout)
    if status == 404:
        return None
    if status != 200:
        raise ControllerDown()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ControllerDown() from exc
    if not isinstance(body, dict):
        raise ControllerDown()
    return body


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def journal_proof(result, accepted_result_id):
    """journal:<seq>:RESULT_ACCEPTED[|sha256:<hex>] for a verified result, else None.

    <seq> is the controller journal position of RESULT_ACCEPTED (task_result's
    accepted_seq). The digest is the single artifact's sha256, or the sha256 of
    the canonical sorted [{path, sha256}] list when there are several. Anything
    malformed or bound to another result yields None (fail closed: NOT_PROVEN).
    """
    if not isinstance(result, dict) or not isinstance(accepted_result_id, str) or not accepted_result_id:
        return None
    if result.get("result_id") != accepted_result_id:
        return None
    seq = result.get("accepted_seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        return None
    proof = f"journal:{seq}:RESULT_ACCEPTED"
    artifacts = result.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        pairs = []
        for item in artifacts:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) \
                    or not isinstance(item.get("sha256"), str) or not _HEX64.match(item["sha256"]):
                return proof  # seq alone is still a journal proof; no unverifiable digest
            pairs.append({"path": item["path"], "sha256": item["sha256"]})
        if len(pairs) == 1:
            digest = pairs[0]["sha256"]
        else:
            canon = json.dumps(sorted(pairs, key=lambda p: (p["path"], p["sha256"])),
                               sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()
        proof += f"|sha256:{digest}"
    return proof


def _journal_proof_for(transport, args, token, mapping):
    """Fetch /result for the mapped task and build its journal proof; None on any gap."""
    try:
        result = _task_result(transport, args, token, mapping.get("task_id"))
    except ControllerDown:
        return None
    return journal_proof(result, mapping.get("accepted_result_id"))


def _task_result(transport, args, token, task_id):
    """The controller's verified result for task_id, or None when it has none."""
    if not isinstance(task_id, str) or not task_id:
        return None
    url = args.controller.rstrip("/") + "/v1/tasks/" + urllib.parse.quote(task_id, safe="") + "/result"
    status, raw = _request(transport, "GET", url, {"X-Courier-Token": token, "Accept": "application/json"}, None, args.timeout)
    if status in (404, 409):
        return None
    if status != 200:
        raise ControllerDown()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ControllerDown() from exc
    return body if isinstance(body, dict) else None


def _post_task(transport, args, token, spec, key, inputs=None):
    task = {name: spec[name] for name in TASK_FIELDS if name in spec}
    task["idempotency_key"] = key
    # The controller persists adapter, params, and the attempt fields. Goal
    # identity, verified inputs, and the admitted estimate are copied into that
    # payload. The idempotency key was hashed from the spec before this copy.
    # The estimate lives in params because create_task rejects any other cost
    # field, and the ledger engine reads params.estimated_cost_eur. A missing
    # estimate is not filled in here; the cost gate already refused that spec.
    params = dict(task["params"])
    kind, goal = _goal_binding(spec)
    if kind == "ok":
        params["goal_id"] = goal[0]
        params["goal_fingerprint"] = goal[1]
    if inputs is not None:
        params["inputs"] = inputs
    params = _with_admitted_estimate(spec, params)
    task["params"] = params
    url = args.controller.rstrip("/") + "/v1/tasks"
    status, raw = _request(
        transport, "POST", url,
        {"X-Courier-Token": token, "Accept": "application/json", "Content-Type": "application/json"},
        json.dumps(task, sort_keys=True).encode("utf-8"), args.timeout,
    )
    if status >= 500 or status == 0:
        raise ControllerDown()
    try:
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeError, json.JSONDecodeError):
        body = {}
    if status not in (200, 201) or not isinstance(body, dict):
        raw_code = body.get("code") or body.get("error") if isinstance(body, dict) else None
        reason_code = "COST_BLOCKED" if raw_code == "cost_blocked" else "CONTROLLER_REJECTED"
        return {
            "rejected": True,
            "reason_code": reason_code,
            "reason": str(raw_code or f"HTTP_{status}"),
        }
    return body


def _request(transport, method, url, headers, body, timeout):
    try:
        return transport(method, url, headers, body, timeout)
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise ControllerDown() from exc


def _load_specs(path: Path):
    if not path.exists():
        raise ConfigError("missing specs")
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ConfigError("specs")
    specs = {}
    for mission_id, spec in data.items():
        if not isinstance(mission_id, str) or not mission_id:
            raise ConfigError("mission id")
        if not _spec_ok(spec):
            raise ConfigError(mission_id)
        specs[mission_id] = spec
    return specs


def _spec_ok(spec) -> bool:
    if not isinstance(spec, dict):
        return False
    allowed = set(TASK_FIELDS) | {
        "source_sha", INPUTS_FIELD, "agent_id", "host_id", "estimated_cost_eur", *GOAL_FIELDS,
    }
    if set(spec) - allowed or any(name not in spec for name in ("adapter", "params", "effect_class", "max_attempts", "lease_ttl_s")):
        return False
    adapter = spec.get("adapter")
    if not isinstance(adapter, str) or not ADAPTER_NAME.match(adapter):
        return False
    if not isinstance(spec.get("params"), dict):
        return False
    if spec.get("effect_class") not in EFFECT_CLASSES:
        return False
    if not _in_range(spec.get("max_attempts"), 1, MAX_ATTEMPTS_LIMIT):
        return False
    if not _in_range(spec.get("lease_ttl_s"), 1, MAX_LEASE_TTL_S):
        return False
    if "timeout_s" in spec and not _in_range(spec.get("timeout_s"), 1, MAX_TIMEOUT_S):
        return False
    if "source_sha" in spec and not _sha_ok(spec.get("source_sha")):
        return False
    if "agent_id" in spec and _authority(AgentID, spec.get("agent_id")) is None:
        return False
    if "host_id" in spec and _authority(HostID, spec.get("host_id")) is None:
        return False
    if "estimated_cost_eur" in spec:
        cost = spec.get("estimated_cost_eur")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            return False
    if INPUTS_FIELD in spec:
        upstream = spec.get(INPUTS_FIELD)
        if (not isinstance(upstream, list) or not 1 <= len(upstream) <= MAX_INPUTS
                or len(set(map(str, upstream))) != len(upstream)
                or not all(isinstance(item, str) and 0 < len(item) <= MAX_ID_LENGTH for item in upstream)):
            return False
    return True


def _goal_binding(spec):
    """Return ('absent', None), ('ok', (id, fingerprint)), or ('blocked', reason).

    Neither field is the default. Exactly one field, or a field that is not a
    short token, parks the mission instead of posting it.
    """
    if not isinstance(spec, dict):
        return "absent", None
    present = [name for name in GOAL_FIELDS if name in spec]
    if not present:
        return "absent", None
    if len(present) != len(GOAL_FIELDS):
        return "blocked", "goal_id and goal_fingerprint must both be present"
    for name in GOAL_FIELDS:
        if not _goal_token(spec.get(name)):
            return "blocked", f"{name} must be at most {MAX_GOAL_LEN} characters matching [A-Za-z0-9._:-]+"
    return "ok", (spec["goal_id"], spec["goal_fingerprint"])


def _goal_token(value) -> bool:
    return isinstance(value, str) and len(value) <= MAX_GOAL_LEN and GOAL_TOKEN.fullmatch(value) is not None


def _route_refusal(spec, agent, host):
    """A declared agent or host that is not this bridge must not be posted here."""
    if not isinstance(spec, dict):
        return None
    if "agent_id" in spec and spec.get("agent_id") != agent.value:
        return "wrong_agent"
    if "host_id" in spec and spec.get("host_id") != host.value:
        return "wrong_host"
    return None


def _host_offline(home: Path, host) -> bool:
    marker = Path(home) / "hosts" / f"{host.value}.offline"
    return marker.is_symlink() or marker.is_file()


def _park_goal(store, reducer, mission, agent, host, reason) -> bool:
    evidence = f"goal_blocked;reason={reason}"
    digest = hashlib.sha256(f"{mission['mission_id']}|{reason}".encode("utf-8")).hexdigest()[:16]
    event = CoordinationEvent(
        event_id=f"blocked-{digest}",
        mission_id=mission["mission_id"],
        agent_id=agent,
        host_id=host,
        event_type=EventType.BLOCKED,
        status=MissionStatus.BLOCKED,
        depends_on=list(mission.get("depends_on") or []),
        head=mission.get("head"),
        evidence_ref=evidence,
        created_at=_not_before(mission.get("updated_at")),
        payload_hash=hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
        branch=mission.get("branch"),
        pr=mission.get("pr"),
        blocker=reason,
        ownership=agent.value,
    )
    return _write_new(store, reducer, event)


def _in_range(value, low, high) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and low <= value <= high


def _load_state(path: Path):
    if not path.exists():
        return {"missions": {}}
    data = _read_json(path)
    if not isinstance(data, dict) or set(data) - {"missions"}:
        raise ConfigError("state")
    missions = data.get("missions", {})
    if not isinstance(missions, dict):
        raise ConfigError("state")
    for mission_id, mapping in missions.items():
        if not isinstance(mission_id, str) or not isinstance(mapping, dict):
            raise ConfigError("state")
        if not isinstance(mapping.get("task_id"), str) or not isinstance(mapping.get("idempotency_key"), str):
            raise ConfigError("state")
        if "status" in mapping and mapping["status"] not in MISSION_STATUSES:
            raise ConfigError("state")
        if "reason" in mapping and mapping["reason"] is not None and not _reason_ok(mapping["reason"]):
            raise ConfigError("state")
        if "updated_at" in mapping and not _time_ok(mapping["updated_at"]):
            raise ConfigError("state")
        if "status" not in mapping:
            derived, derived_reason = _derive_mission_status(mapping)
            if derived is not None:
                mapping["status"] = derived
                mapping["reason"] = derived_reason
        elif "reason" not in mapping:
            mapping["reason"] = None
    return {"missions": missions}


def _read_json(path: Path):
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ConfigError("unreadable") from exc
    if size > MAX_STATE_BYTES:
        raise ConfigError("oversize")
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_STATE_BYTES + 1)
    except OSError as exc:
        raise ConfigError("unreadable") from exc
    if len(raw) > MAX_STATE_BYTES:
        raise ConfigError("oversize")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError("json") from exc


def _derive_mission_status(mapping):
    """Legacy entries have no status. A result is FINAL_DONE; a post with none is POSTED."""
    result = mapping.get("accepted_result_id")
    if isinstance(result, str) and result:
        return "FINAL_DONE", None
    if mapping.get("posted") is True:
        return "POSTED", None
    return None, None


def _status_for_outcome(event, view):
    if event.event_type == EventType.FINAL:
        return "FINAL_DONE", None
    if event.event_type == EventType.BLOCKED:
        return "BLOCKED", "CONTROLLER_BLOCKED"
    if event.event_type == EventType.ERROR:
        code = "CANCELLED" if view.get("status") == "CANCELLED" else "FAILED"
        return "ERROR", code
    raise ConfigError("status")


def _goal_reason_code(reason) -> str:
    if reason == "goal_id and goal_fingerprint must both be present":
        return "GOAL_PAIR"
    return "GOAL_TOKEN"


def _reason_ok(value) -> bool:
    return isinstance(value, str) and REASON_CODE.fullmatch(value) is not None


def _time_ok(value) -> bool:
    return (
        isinstance(value, str) and value.endswith("Z") and "\n" not in value
        and len(value) <= 40 and parse_timestamp(value) is not None
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp(path, state, mapping, status, reason, **fields) -> bool:
    """Write status, reason, and the other fields in one save. Skip when nothing changed."""
    if status not in MISSION_STATUSES:
        raise ConfigError("status")
    if reason is not None and not _reason_ok(reason):
        raise ConfigError("reason")
    fields["status"] = status
    fields["reason"] = reason
    changed = False
    for key, value in fields.items():
        if key not in mapping or mapping[key] != value:
            mapping[key] = value
            changed = True
    if not changed:
        return False
    mapping["updated_at"] = _utc_now()
    _save_state(path, state)
    return True


def _save_state(path: Path, state) -> None:
    _atomic_write(path, json.dumps(state, sort_keys=True, indent=2) + "\n")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _receipt_present(home, mission_id, outcome) -> bool:
    path = home / "run" / "ledger_bridge.log"
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size > MAX_STATE_BYTES:
        raise ConfigError("receipt log oversize")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigError("receipt log unreadable") from exc
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("mission_id") == mission_id and record.get("outcome") == outcome:
            return True
    return False


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()


def _read_token(path: Path) -> str:
    try:
        token = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    if len(token) < 32 or "\n" in token:
        return ""
    return token


def _authority(enum_cls, value):
    try:
        found = enum_cls(value)
    except ValueError:
        return None
    if found == enum_cls.UNKNOWN:
        return None
    return found


def _loopback(url) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if parsed.username or parsed.password:
        return False
    return parsed.scheme in ("http", "https") and parsed.hostname in ("127.0.0.1", "localhost", "::1")


def _not_before(updated_at) -> str:
    now = datetime.now(timezone.utc)
    floor = parse_timestamp(updated_at)
    if floor is not None and now < floor:
        now = floor
    return now.isoformat().replace("+00:00", "Z")


def _redact(text, token):
    if token:
        return text.replace(token, "[redacted]")
    return text


def _print(line):
    print(line, flush=True)


def _print_err(line):
    import sys
    print(line, file=sys.stderr, flush=True)


def _urllib_http(method, url, headers, body, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_STATE_BYTES + 1)
            if len(raw) > MAX_STATE_BYTES:
                raise OSError("response too large")
            return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_STATE_BYTES + 1)
        return exc.code, raw[:MAX_STATE_BYTES]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


if __name__ == "__main__":
    import sys
    sys.exit(main())
