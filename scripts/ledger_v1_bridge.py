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
        spec = specs.get(mission_id)
        goal_kind, goal_reason = _goal_binding(spec)
        if goal_kind == "blocked":
            _park_goal(store, reducer, mission, agent, host, goal_reason)
            emit({"mission_id": mission_id, "outcome": "blocked", "reason": goal_reason})
            continue
        view = _task_view(transport, args, token, mapping.get("task_id"))
        if view is None:
            if mapping.get("posted"):
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": "task_missing"})
                ok = False
            continue
        event = _feedback_event(mission, mapping, spec, agent, host, view)
        if event is None:
            if view.get("status") in ("COMPLETE", "BLOCKED", *TERMINAL_FAILURE):
                emit({"mission_id": mission_id, "outcome": "skipped", "reason": "identity_missing"})
                ok = False
            continue
        if event.event_type == EventType.FINAL and view.get("status") != "COMPLETE":
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "not_final"})
            ok = False
            continue
        wrote = _write_new(store, reducer, event)
        mapping.update({
            "accepted_result_id": _result_id(view),
            "attempt": view.get("attempt"),
            "evidence_ref": event.evidence_ref,
            "spec_fingerprint": mapping.get("spec_fingerprint") or _fingerprint(specs.get(mission_id) or {}),
            "source_sha": _recorded_source(mapping, specs.get(mission_id)),
        })
        _save_state(home / "ledger_bridge_state.json", state)
        if wrote:
            emit({"mission_id": mission_id, "outcome": event.event_type.value.lower(), "task_id": mapping.get("task_id")})
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
        goal_kind, goal_value = _goal_binding(spec)
        if goal_kind == "blocked":
            mission = reducer.get_mission(mission_id)
            if mission is not None:
                _park_goal(store, reducer, mission, agent, host, goal_value)
            emit({"mission_id": mission_id, "outcome": "blocked", "reason": goal_value})
            continue
        goal = goal_value if goal_kind == "ok" else None
        source = _recorded_source(state["missions"].get(mission_id) or {}, spec)
        if source is None:
            emit({"mission_id": mission_id, "outcome": "skipped", "reason": "source_sha_missing"})
            ok = False
            continue
        mapping = state["missions"].get(mission_id)
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
            mapping = {
                "task_id": task_id,
                "claim_event_id": claimed.event_id,
                "idempotency_key": key,
                "posted": False,
                "accepted_result_id": None,
                "attempt": None,
                "spec_fingerprint": _fingerprint(spec),
                "source_sha": source,
                "evidence_ref": _identity(task_id, None, 0, _fingerprint(spec), source, goal),
            }
            if goal is not None:
                mapping["goal_id"] = goal[0]
                mapping["goal_fingerprint"] = goal[1]
            state["missions"][mission_id] = mapping
            _save_state(home / "ledger_bridge_state.json", state)
        if mapping.get("posted"):
            continue
        posted = _post_task(transport, args, token, spec, mapping["idempotency_key"])
        if posted.get("rejected"):
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
        mapping["posted"] = True
        mapping["attempt"] = attempt
        mapping["accepted_result_id"] = result_id
        mapping["evidence_ref"] = _identity(
            mapping["task_id"], result_id, attempt, mapping["spec_fingerprint"], mapping["source_sha"], goal,
        )
        _save_state(home / "ledger_bridge_state.json", state)
        outcome = "duplicate" if posted.get("duplicate") is True else "queued"
        emit({"mission_id": mission_id, "outcome": outcome, "task_id": mapping["task_id"]})
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
    evidence = _identity(task_id, result_id, attempt, fingerprint, source, goal)
    if status == "COMPLETE":
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


def _identity(task_id, result_id, attempt, fingerprint, source_sha, goal=None) -> str:
    result = result_id if isinstance(result_id, str) and result_id else "none"
    text = (
        f"task_id={task_id};accepted_result_id={result};attempt={attempt};"
        f"spec_fingerprint={fingerprint};source_sha={source_sha}"
    )
    if goal:
        text += f";goal_id={goal[0]};goal_fingerprint={goal[1]}"
    return text


def _result_id(view):
    if not isinstance(view, dict):
        return None
    for key in ("accepted_result_id", "result_id", "pending_result_id"):
        value = view.get(key)
        if isinstance(value, str) and value:
            return value
    return None


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


def _fingerprint(spec) -> str:
    payload = {name: spec[name] for name in TASK_FIELDS if name in spec}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write_new(store, reducer, event) -> bool:
    if event.event_id in reducer.processed_event_ids:
        return False
    if not store.write_event(event):
        raise ConfigError("ledger write failed")
    reducer.apply(event)
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


def _post_task(transport, args, token, spec, key):
    task = {name: spec[name] for name in TASK_FIELDS if name in spec}
    task["idempotency_key"] = key
    # The controller persists adapter, params, and the attempt fields. Goal
    # identity is copied into that payload and is not part of the idempotency key.
    kind, goal = _goal_binding(spec)
    if kind == "ok":
        params = dict(task["params"])
        params["goal_id"] = goal[0]
        params["goal_fingerprint"] = goal[1]
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
        return {"rejected": True}
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
    allowed = set(TASK_FIELDS) | {"source_sha", *GOAL_FIELDS}
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
