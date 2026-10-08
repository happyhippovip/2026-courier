"""Ledger-driven host loop.

Each tick reads the canonical work queue (``courier_core.work_queue``), claims
one ready item, runs the first usable headless provider, verifies it, and
releases the lease with one receipt. The queue is the only work list. This
module does not write a second catalog or claim ledger.

A crash resumes from ``home/host_loop_state.json``. That file is a cursor for
this host (which item, which phase), not a queue. Claim and release on the
work queue stay idempotent, so a replay does not append a second effect.

Run from the repo root::

    python -m courier_worker.host_loop --once --host-config host.json
    python -m courier_worker.host_loop --forever --host-config host.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from courier_core.work_queue import (
    DEFAULT_ITEMS,
    DEFAULT_SCHEMA,
    WorkQueue,
    WorkQueueError,
    claim,
    list_ready,
    release,
    renew,
    render_prompt,
)
from courier_worker.adapters import provider_exec

EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_CONFIG = 3

STRIKE_LIMIT = 3
BACKOFF_S = (5, 10, 20, 40, 60)
DEFAULT_PROVIDERS = ("agy", "muse", "cursor-agent")
DEFAULT_TIMEOUT_S = 300.0
MAX_TIMEOUT_S = 1800.0
DEFAULT_LEASE_S = 3600
REFUSAL_MARKERS = ("refused", "no-op", "noop", "no op", "did not write")
IMMEDIATE_UNAVAILABLE = frozenset({"PROVIDER_NOT_ALLOWLISTED", "BINARY_MISSING"})
DEFERRED_REASONS = frozenset({
    "ADMISSION_DENIED",
    "PROVIDER_BUSY",
    "WORKDIR_UNAVAILABLE",
})
ADMIT_PRESSURE = frozenset({"GREEN", "YELLOW"})
CLAIM_SKIP = frozenset({"DUPLICATE_CLAIM", "NOT_CLAIMABLE", "SCOPE_OVERLAP", "UNKNOWN_ITEM"})
_TOKEN = re.compile(r"^[A-Za-z0-9._:-]+$")
_HOOKS = ("before_claim", "after_claim", "after_provider_exit", "after_receipt")


class ConfigError(Exception):
    """Host config or the work-queue catalog cannot be trusted."""


class FailClosedGitHub:
    """No live lookup. Unknown open-PR paths block a new claim."""

    def open_pr_paths(self):
        return None

    def done_prs(self):
        return None

    def branch_exists(self, branch: str) -> bool:
        return False

    def draft_pr(self, branch: str):
        return None


def build_provider_params(provider: str, prompt: str, timeout_s: float) -> dict:
    """Params handed to provider_exec. Sandbox stays inside that adapter."""
    return {"provider": provider, "prompt": prompt, "timeout_s": timeout_s}


def main(
    argv=None,
    *,
    sleep=None,
    github=None,
    tests_runner=None,
    governor=None,
    now=None,
    hooks=None,
    max_ticks=None,
    until_idle=False,
) -> int:
    """``--once`` is a single tick. ``--forever`` keeps claiming until stop."""
    try:
        args = _parse(argv)
        config = _load_config(args.host_config)
    except ConfigError:
        print("host loop config error", file=sys.stderr)
        return EXIT_CONFIG
    sleeper = sleep or time.sleep
    remote = github if github is not None else FailClosedGitHub()
    runner = tests_runner or _default_tests
    clock = now or _utc_now
    streak = 0
    ticks = 0
    while True:
        if max_ticks is not None and ticks >= max_ticks:
            return EXIT_OK
        ticks += 1
        try:
            outcome = _tick(config, remote, runner, governor, clock, hooks or {})
        except ConfigError:
            print("host loop config error", file=sys.stderr)
            return EXIT_CONFIG
        if outcome == "blocked":
            print("host blocked", file=sys.stderr)
            return EXIT_BLOCKED
        if outcome == "stop":
            return EXIT_OK
        if args.once:
            return EXIT_OK
        if outcome == "progressed":
            streak = 0
            continue
        if until_idle:
            return EXIT_OK
        sleeper(BACKOFF_S[min(streak, len(BACKOFF_S) - 1)])
        streak += 1


def _parse(argv):
    class _Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ConfigError(message)

    parser = _Parser(prog="courier_worker.host_loop")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--forever", action="store_true")
    parser.add_argument("--host-config", required=True)
    return parser.parse_args(argv)


def _utc_now():
    return datetime.now(timezone.utc)


def _tick(config, github, tests_runner, governor, now, hooks) -> str:
    home = config["home"]
    state = _load_state(home / "host_loop_state.json")
    if state["host_status"] == "BLOCKED" and not state.get("in_flight"):
        return "blocked"
    if state.get("in_flight"):
        return _resume(config, state, github, tests_runner, governor, now, hooks)
    if int(state.get("consecutive_all_failed") or 0) >= STRIKE_LIMIT:
        _mark_blocked(state, home)
        return "blocked"
    if _flag(home, "STOP"):
        return "stop"
    if not _admitted(governor):
        return "idle"
    if _flag(home, "PAUSE"):
        return "idle"
    listed = _queue_view(github)
    if listed is None:
        return "idle"
    paths, done = listed
    moment = _moment(now)
    queue = _queue(config)
    try:
        ready = list_ready(queue, open_pr_files=paths, done_prs=done, now=moment)
    except WorkQueueError as exc:
        raise ConfigError(exc.code) from exc
    for item in ready:
        item_id = item["id"]
        if item_id in state["skipped"]:
            continue
        try:
            prompt = render_prompt(item, config["holder"])
        except Exception as exc:
            raise ConfigError("prompt") from exc
        if not isinstance(prompt, str) or not prompt.strip() or prompt.startswith("-"):
            state["skipped"].append(item_id)
            _save_state(home / "host_loop_state.json", state)
            continue
        _fire(hooks, "before_claim")
        try:
            claimed = claim(
                queue, item_id, config["holder"], config["lease_ttl_s"],
                host=config["host"], now=moment, done_prs=done, open_pr_files=paths,
            )
        except WorkQueueError as exc:
            if exc.code in CLAIM_SKIP:
                continue
            raise ConfigError(exc.code) from exc
        state["in_flight"] = {
            "item_id": item_id,
            "phase": "claimed",
            "attempted": [],
            "claim_expires": claimed.get("expires_at"),
        }
        _save_state(home / "host_loop_state.json", state)
        _fire(hooks, "after_claim")
        return _resume(config, state, github, tests_runner, governor, now, hooks)
    return "idle"


def _resume(config, state, github, tests_runner, governor, now, hooks) -> str:
    home = config["home"]
    phase = state["in_flight"].get("phase")
    if phase == "receipt_appended":
        return _close_receipt(config, state, github, now)
    if phase == "claimed":
        if state["host_status"] == "BLOCKED" or _flag(home, "STOP"):
            return "blocked" if state["host_status"] == "BLOCKED" else "stop"
        if not _admitted(governor):
            return "idle"
        if _ensure_lease(config, state, github, now) != "held":
            return "idle"
        step = _run_providers(config, state, hooks, now)
        if step == "deferred":
            return "idle"
        if step != "ready":
            return step
    if state.get("in_flight") and state["in_flight"].get("phase") == "provider_exited":
        return _receipt(config, state, github, tests_runner, now, hooks)
    return "idle"


def _ensure_lease(config, state, github, now) -> str:
    """Confirm this host still holds the item. Renew once if the lease is short."""
    listed = _queue_view(github)
    if listed is None:
        return "unknown"
    paths, done = listed
    moment = _moment(now)
    flight = state["in_flight"]
    queue = _queue(config)
    try:
        view = claim(
            queue, flight["item_id"], config["holder"], config["lease_ttl_s"],
            host=config["host"], now=moment, done_prs=done, open_pr_files=paths,
        )
    except WorkQueueError as exc:
        if exc.code in CLAIM_SKIP:
            state["in_flight"] = None
            _save_state(config["home"] / "host_loop_state.json", state)
            return "lost"
        raise ConfigError(exc.code) from exc
    expires = view.get("expires_at")
    if _remaining(expires, moment) > config["timeout_s"]:
        return "held"
    if flight.get("renewed_expires") == expires:
        return "held"
    try:
        view = renew(
            queue, flight["item_id"], config["holder"], config["lease_ttl_s"], now=moment,
        )
    except WorkQueueError as exc:
        raise ConfigError(exc.code) from exc
    flight["renewed_expires"] = view.get("expires_at")
    _save_state(config["home"] / "host_loop_state.json", state)
    return "held"


def _run_providers(config, state, hooks, now) -> str:
    home = config["home"]
    flight = state["in_flight"]
    moment = _moment(now)
    item = _find_item(config, flight["item_id"], moment)
    if item is None:
        return _finish_providers(config, state, hooks, "failed", "none", "SPEC_MISSING")
    try:
        prompt = render_prompt(item, config["holder"])
    except Exception as exc:
        raise ConfigError("prompt") from exc
    if not isinstance(prompt, str) or not prompt.strip() or prompt.startswith("-"):
        return _finish_providers(config, state, hooks, "failed", "none", "BAD_PROMPT")
    workdir = _workdir(home, flight["item_id"])
    workdir.mkdir(parents=True, exist_ok=True)
    while True:
        _promote_strikes(state)
        name = next((item_name for item_name in _eligible(config, state) if item_name not in flight["attempted"]), None)
        if name is None:
            return _finish_providers(
                config, state, hooks, "failed",
                flight.get("last_provider") or "none",
                flight.get("last_reason") or "NO_PROVIDER",
            )
        outcome = _one_provider(config, prompt, name, workdir)
        if outcome["kind"] == "deferred":
            _save_state(home / "host_loop_state.json", state)
            return "deferred"
        flight["attempted"].append(name)
        flight["last_provider"] = name
        if outcome["kind"] == "unavailable":
            _mark_unavailable(state, name)
            _save_state(home / "host_loop_state.json", state)
            continue
        if outcome["kind"] == "blocked":
            return _finish_providers(config, state, hooks, "blocked", name, "PROVIDER_APPROVAL_REFUSED")
        if outcome["kind"] == "clean":
            return _finish_providers(config, state, hooks, "clean", name, "")
        flight["last_reason"] = outcome["reason"]
        _strike(state, name)
        _save_state(home / "host_loop_state.json", state)


def _one_provider(config, prompt, name, workdir) -> dict:
    params = build_provider_params(name, prompt, config["timeout_s"])
    try:
        result = provider_exec.run(params, workdir, config={"binaries": config["binaries"]})
    except Exception:
        return {"kind": "failed", "reason": "PROVIDER_CRASH"}
    reason = result.reason_code or ""
    if reason in IMMEDIATE_UNAVAILABLE:
        return {"kind": "unavailable", "reason": reason}
    if reason == "PROVIDER_APPROVAL_REFUSED" or result.outcome == "BLOCKED":
        return {"kind": "blocked", "reason": "PROVIDER_APPROVAL_REFUSED"}
    if result.outcome == "deferred" or reason in DEFERRED_REASONS:
        return {"kind": "deferred", "reason": reason or "DEFERRED"}
    refused = _output_refused(result.output)
    if result.outcome == "success" and result.exit_code == 0 and not refused and not result.truncated:
        return {"kind": "clean", "reason": ""}
    if refused:
        return {"kind": "failed", "reason": "REFUSED_OUTPUT"}
    if result.truncated:
        return {"kind": "failed", "reason": "OUTPUT_TOO_LARGE"}
    return {"kind": "failed", "reason": reason or "PROVIDER_FAILED"}


def _finish_providers(config, state, hooks, kind, provider, reason) -> str:
    flight = state["in_flight"]
    flight["result"] = {"kind": kind, "provider": provider, "reason": reason}
    flight["phase"] = "provider_exited"
    _save_state(config["home"] / "host_loop_state.json", state)
    _fire(hooks, "after_provider_exit")
    return "ready"


def _receipt(config, state, github, tests_runner, now, hooks) -> str:
    home = config["home"]
    flight = state["in_flight"]
    if "decision" not in flight:
        flight["decision"] = _decide(config, state, github, tests_runner, now)
        _save_state(home / "host_loop_state.json", state)
    if not _release_receipt(config, state, github, now):
        return "idle"
    decision = flight["decision"]
    if not flight.get("counted"):
        if decision["receipt"] == "FAILED":
            state["consecutive_all_failed"] = int(state.get("consecutive_all_failed") or 0) + 1
        elif decision["receipt"] == "ACCEPTED":
            state["consecutive_all_failed"] = 0
            provider = decision.get("provider") or ""
            if provider and provider != "none":
                state["provider_failures"][provider] = 0
        flight["counted"] = True
    flight["phase"] = "receipt_appended"
    _save_state(home / "host_loop_state.json", state)
    _fire(hooks, "after_receipt")
    return _close_receipt(config, state, github, now)


def _close_receipt(config, state, github, now) -> str:
    if not _release_receipt(config, state, github, now):
        return "idle"
    state["in_flight"] = None
    if int(state.get("consecutive_all_failed") or 0) >= STRIKE_LIMIT:
        _mark_blocked(state, config["home"])
        return "blocked"
    _save_state(config["home"] / "host_loop_state.json", state)
    return "progressed"


def _decide(config, state, github, tests_runner, now) -> dict:
    flight = state["in_flight"]
    result = flight.get("result") or {}
    provider = result.get("provider") or "none"
    kind = result.get("kind")
    item = _find_item(config, flight["item_id"], _moment(now)) or {}
    base = {
        "provider": provider,
        "pr": None,
        "head": None,
        "test_evidence": "not_run",
        "blocker": None,
    }
    if kind == "blocked":
        decision = {**base, "receipt": "BLOCKED", "blocker": "PROVIDER_APPROVAL_REFUSED"}
    elif kind != "clean":
        decision = {**base, "receipt": "FAILED", "blocker": result.get("reason") or "PROVIDER_FAILED"}
    else:
        decision = _verify_clean(config, state, github, tests_runner, item, provider)
    decision["result"] = _pack(decision)
    return decision


def _verify_clean(config, state, github, tests_runner, item, provider) -> dict:
    acceptance = item.get("acceptance") if isinstance(item.get("acceptance"), list) else []
    base = {"provider": provider, "pr": None, "head": None, "blocker": None}
    evidence = "not_run"
    if "tests" in acceptance:
        code = _run_tests(
            tests_runner, config.get("tests_command"), _workdir(config["home"], item.get("id", "item")),
        )
        if code is None:
            _strike(state, provider)
            return {**base, "receipt": "FAILED", "test_evidence": "tests_missing", "blocker": "TESTS_MISSING"}
        evidence = f"tests_exit={code}"
        if code != 0:
            _strike(state, provider)
            return {**base, "receipt": "FAILED", "test_evidence": evidence, "blocker": "TESTS_FAILED"}
    url, sha = None, None
    if "draft PR" in acceptance:
        url, sha, err = _verify_remote(github, item.get("branch"))
        if err:
            _strike(state, provider)
            return {
                **base, "receipt": "FAILED", "test_evidence": evidence, "blocker": err, "pr": url, "head": sha,
            }
    return {
        "receipt": "ACCEPTED",
        "provider": provider,
        "pr": url,
        "head": sha,
        "test_evidence": evidence,
        "blocker": None,
    }


def _release_receipt(config, state, github, now) -> bool:
    flight = state.get("in_flight") or {}
    decision = flight.get("decision")
    if not isinstance(decision, dict) or not decision.get("result"):
        return False
    moment = _moment(now)
    queue = _queue(config)
    try:
        released = release(
            queue, flight["item_id"], config["holder"], decision["result"], now=moment,
        )
    except WorkQueueError as exc:
        if exc.code != "NOT_HOLDER":
            raise ConfigError(exc.code) from exc
        if _ensure_lease(config, state, github, now) != "held":
            return False
        try:
            released = release(
                queue, flight["item_id"], config["holder"], decision["result"], now=moment,
            )
        except WorkQueueError as again:
            raise ConfigError(again.code) from again
    if released.get("result") != decision["result"]:
        return False
    _append_receipt_log(config["home"] / "run" / "host_loop_receipts.jsonl", flight, decision)
    return True


def _verify_remote(github, branch):
    try:
        exists = bool(github.branch_exists(branch))
    except Exception:
        return None, None, "BRANCH_MISSING"
    if not exists:
        return None, None, "BRANCH_MISSING"
    try:
        draft = github.draft_pr(branch)
    except Exception:
        return None, None, "PR_MISSING"
    if not isinstance(draft, tuple) or len(draft) != 2:
        return None, None, "PR_MISSING"
    url, sha = draft
    if not isinstance(url, str) or not url or not isinstance(sha, str) or not sha:
        return None, None, "PR_MISSING"
    if any(ch in url or ch in sha for ch in "\r\n"):
        return None, None, "PR_MISSING"
    return url, sha, None


def _run_tests(tests_runner, command, workdir):
    if not isinstance(command, list) or not command:
        return None
    try:
        code = tests_runner(list(command), workdir)
    except Exception:
        return 1
    if isinstance(code, bool) or not isinstance(code, int):
        return 1
    return code


def _default_tests(argv, workdir):
    try:
        completed = subprocess.run(
            argv,
            cwd=str(workdir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DEFAULT_TIMEOUT_S,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return 124
    except OSError:
        return 127
    return int(completed.returncode)


def _output_refused(output: bytes) -> bool:
    text = output.decode("utf-8", errors="replace").lower()
    return any(marker in text for marker in REFUSAL_MARKERS)


def _pack(decision: dict) -> str:
    text = " ".join([
        str(decision.get("receipt") or "FAILED"),
        "provider=" + str(decision.get("provider") or "none"),
        "pr=" + str(decision.get("pr") or "-"),
        "head=" + str(decision.get("head") or "-"),
        "tests=" + str(decision.get("test_evidence") or "not_run"),
        "blocker=" + str(decision.get("blocker") or "-"),
    ])
    text = "".join(ch for ch in text if ch not in "\r\n")
    return text[:200] if text.strip() else "FAILED"


def _eligible(config, state) -> list:
    blocked = set(state["unavailable"]) | set(config["unavailable"])
    names = []
    for name in config["providers"]:
        if name in blocked:
            continue
        if int(state["provider_failures"].get(name) or 0) >= STRIKE_LIMIT:
            continue
        names.append(name)
    return names


def _promote_strikes(state) -> None:
    for name, count in list(state["provider_failures"].items()):
        if int(count) >= STRIKE_LIMIT:
            _mark_unavailable(state, name)


def _strike(state, provider: str) -> None:
    if not provider or provider == "none":
        return
    count = int(state["provider_failures"].get(provider) or 0) + 1
    state["provider_failures"][provider] = count
    if count >= STRIKE_LIMIT:
        _mark_unavailable(state, provider)


def _mark_unavailable(state, provider: str) -> None:
    if provider and provider not in state["unavailable"]:
        state["unavailable"].append(provider)


def _mark_blocked(state, home: Path) -> None:
    state["host_status"] = "BLOCKED"
    state["in_flight"] = None
    _save_state(home / "host_loop_state.json", state)


def _admitted(governor) -> bool:
    target = governor
    if target is None:
        try:
            from scripts.resource_governor import governor as target
        except Exception:
            return False
    try:
        pressure = target.measure_pressure()
    except Exception:
        return False
    return isinstance(pressure, str) and pressure in ADMIT_PRESSURE


def _fire(hooks, name: str) -> None:
    fn = hooks.get(name) if isinstance(hooks, dict) else None
    if fn is not None:
        fn()


def _queue_view(github):
    """Open-PR paths and done PR numbers. ``None`` means the view is unknown."""
    if github is None or not hasattr(github, "open_pr_paths"):
        return None
    try:
        paths = github.open_pr_paths()
    except Exception:
        return None
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        return None
    done = []
    if hasattr(github, "done_prs"):
        try:
            done = github.done_prs()
        except Exception:
            return None
        if not isinstance(done, list) or not all(isinstance(item, str) for item in done):
            return None
    return list(paths), list(done)


def _find_item(config, item_id, moment):
    try:
        rows = _queue(config).items(now=moment)
    except WorkQueueError as exc:
        raise ConfigError(exc.code) from exc
    for row in rows:
        if row.get("id") == item_id:
            return row
    return None


def _remaining(expires, moment) -> float:
    if not isinstance(expires, str):
        return 0
    try:
        parsed = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return (parsed - moment).total_seconds()


def _load_config(path) -> dict:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError("config") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config")
    holder = raw.get("holder", raw.get("agent_id"))
    host = raw.get("host", raw.get("host_id"))
    if not _token(holder) or not _token(host):
        raise ConfigError("authority")
    home = raw.get("home")
    if not isinstance(home, str) or not home:
        raise ConfigError("home")
    home_path = Path(home)
    try:
        home_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigError("home") from exc
    providers = raw.get("providers", list(DEFAULT_PROVIDERS))
    if (
        not isinstance(providers, list) or not providers
        or not all(isinstance(item, str) and item for item in providers)
    ):
        raise ConfigError("providers")
    binaries = raw.get("binaries", {})
    if not isinstance(binaries, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in binaries.items()
    ):
        raise ConfigError("binaries")
    unavailable = raw.get("unavailable", [])
    if not isinstance(unavailable, list) or not all(isinstance(item, str) for item in unavailable):
        raise ConfigError("unavailable")
    timeout_s = raw.get("timeout_s", DEFAULT_TIMEOUT_S)
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
        raise ConfigError("timeout")
    timeout_s = float(timeout_s)
    if not (0 < timeout_s <= MAX_TIMEOUT_S):
        raise ConfigError("timeout")
    lease = raw.get("lease_ttl_s", DEFAULT_LEASE_S)
    if isinstance(lease, bool) or not isinstance(lease, int) or not 1 <= lease <= 7 * 24 * 3600:
        raise ConfigError("lease")
    items = raw.get("items_dir")
    ledger = raw.get("ledger")
    items_dir = Path(items) if isinstance(items, str) and items else DEFAULT_ITEMS
    ledger_path = Path(ledger) if isinstance(ledger, str) and ledger else home_path / "work_queue_ledger.jsonl"
    command = raw.get("tests_command")
    if command is not None and (
        not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command)
    ):
        raise ConfigError("tests_command")
    return {
        "holder": holder,
        "host": host,
        "home": home_path,
        "providers": list(providers),
        "binaries": dict(binaries),
        "unavailable": list(unavailable),
        "timeout_s": timeout_s,
        "lease_ttl_s": lease,
        "items_dir": items_dir,
        "ledger": ledger_path,
        "schema": DEFAULT_SCHEMA,
        "tests_command": list(command) if command else None,
    }


def _token(value) -> bool:
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None and len(value) <= 64


def _fresh_state() -> dict:
    return {
        "host_status": "READY",
        "consecutive_all_failed": 0,
        "provider_failures": {},
        "unavailable": [],
        "skipped": [],
        "in_flight": None,
    }


def _load_state(path: Path) -> dict:
    if not path.exists():
        return _fresh_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError("state") from exc
    if not isinstance(raw, dict):
        raise ConfigError("state")
    state = _fresh_state()
    status = raw.get("host_status", "READY")
    if status not in ("READY", "BLOCKED"):
        raise ConfigError("state")
    state["host_status"] = status
    count = raw.get("consecutive_all_failed", 0)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ConfigError("state")
    state["consecutive_all_failed"] = count
    failures = raw.get("provider_failures", {})
    unavailable = raw.get("unavailable", [])
    skipped = raw.get("skipped", [])
    if not isinstance(failures, dict) or not isinstance(unavailable, list) or not isinstance(skipped, list):
        raise ConfigError("state")
    state["provider_failures"] = {
        key: int(value)
        for key, value in failures.items()
        if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
    }
    state["unavailable"] = [item for item in unavailable if isinstance(item, str)]
    state["skipped"] = [item for item in skipped if isinstance(item, str)]
    flight = raw.get("in_flight")
    if flight is not None and not isinstance(flight, dict):
        raise ConfigError("state")
    state["in_flight"] = flight
    return state


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _queue(config) -> WorkQueue:
    return WorkQueue(config["items_dir"], config["ledger"], config["schema"])


def _append_receipt_log(path: Path, flight: dict, decision: dict) -> None:
    result = decision.get("result")
    if _log_has(path, flight.get("item_id"), result):
        return
    record = {
        "blocker": decision.get("blocker"),
        "head": decision.get("head"),
        "item_id": flight.get("item_id"),
        "pr": decision.get("pr"),
        "provider": decision.get("provider"),
        "receipt": decision.get("receipt"),
        "result": result,
        "test_evidence": decision.get("test_evidence"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _log_has(path: Path, item_id, result) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("item_id") == item_id and row.get("result") == result:
            return True
    return False


def _moment(now) -> datetime:
    current = now() if callable(now) else now
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ConfigError("clock")
    return current.astimezone(timezone.utc)


def _flag(home: Path, name: str) -> bool:
    return (home / name).exists()


def _workdir(home: Path, item_id: str) -> Path:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(item_id))[:80]
    return home / "work" / (cleaned or "item")


if __name__ == "__main__":
    raise SystemExit(main())
