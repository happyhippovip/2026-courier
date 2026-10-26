"""CI watcher v2: follow the GitHub runs of ONE commit SHA with few, bounded queries.

Stand-alone. It does not change or replace scripts/github_worker_adapter.py: it is a
single-invocation helper (no loop outside one call, no scheduler, no second engine, no
model call). Only `gh run list --commit <sha>` is used for status; `gh workflow run` is
used only when the caller passes a dispatch workflow.

Guarantees (proved by tests/automation/test_ci_watcher_v2.py with a gh stub):
* queries are scoped to one SHA (`--commit SHA --limit 20`), runs of other SHAs are ignored;
* bounded exponential backoff: base, factor, max interval, max attempts are configurable,
  clock and sleep are injectable (deterministic);
* progress (attempt counter, next poll time, runs, terminal result) lives in one small state
  file written atomically (tmp + fsync + os.replace); a restart resumes it and never polls
  before `next_poll_at`; a terminal result costs zero further gh calls;
* idempotency key `<workkey>@<sha>`: the dispatch callable runs at most once per key, ever.
  A crash between the DISPATCHING marker and the dispatch result is never "healed" by a
  second dispatch (the run is adopted if it shows up, otherwise DISPATCH_UNCONFIRMED);
* one process per key at a time (flock, released by the OS when a process dies, so a
  SIGKILL does not leave a stale lock).

CLI (watch only unless --dispatch-workflow is given):
    python -m tools.automation.ci_watcher_v2 --workkey WK --sha <40 hex> --state-dir DIR
        [--window 60] [--base 5] [--factor 2] [--max-interval 60] [--max-attempts 64]
        [--dispatch-workflow FILE --ref BRANCH] [--repo owner/name]
Exit codes: 0 all runs success · 1 runs finished but not all success · 10 still waiting
(window over; run again) · 11 attempts exhausted · 12 dispatch unconfirmed · 13 locked by
another process · 14 state file unreadable · 2 usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

try:  # POSIX; on Windows the lock is skipped (the state file still guards idempotency)
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LIST_LIMIT = 20
FIELDS = "databaseId,status,conclusion,displayTitle,headSha,workflowName,url"

WATCHING, COMPLETED, EXHAUSTED, DISPATCHING, UNCONFIRMED = (
    "WATCHING", "COMPLETED", "EXHAUSTED", "DISPATCHING", "DISPATCH_UNCONFIRMED")
WAITING, LOCKED, STATE_UNREADABLE = "WAITING", "LOCKED", "STATE_UNREADABLE"
EXIT_CODES = {"SUCCESS": 0, "FINISHED_NOT_SUCCESS": 1, WAITING: 10, EXHAUSTED: 11, UNCONFIRMED: 12,
              LOCKED: 13, STATE_UNREADABLE: 14}


class GhQueryError(RuntimeError):
    """Transient problem with one status query (non-zero exit, rate limit, malformed JSON)."""

    def __init__(self, message: str, rate_limited: bool = False):
        super().__init__(message)
        self.rate_limited = rate_limited


@dataclass(frozen=True)
class Backoff:
    base: float = 5.0
    factor: float = 2.0
    max_interval: float = 60.0
    max_attempts: int = 64  # 0 = unbounded
    window: float = 60.0  # seconds one invocation may wait; 0 = until terminal/exhausted
    dispatch_grace: float = 300.0

    def delay(self, attempt: int) -> float:
        """Delay before poll number `attempt` (1-based; poll 1 is immediate)."""
        if attempt <= 1:
            return 0.0
        return min(self.max_interval, self.base * (max(self.factor, 1.0) ** (attempt - 2)))


def idempotency_key(workkey: str, sha: str) -> str:
    return f"{workkey}@{sha}"


def _stem(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def state_path(state_dir: Path, key: str) -> Path:
    return Path(state_dir) / f".ci-watch-{_stem(key)}.json"  # dotfile: never matched by dispatch-*.json globs


def default_run_cmd(command: list[str]) -> tuple[int, str, str]:
    done = subprocess.run(command, capture_output=True, text=True, timeout=120)
    return done.returncode, done.stdout, done.stderr


def write_state(path: Path, state: dict) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, sort_keys=True, indent=1)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def read_state(path: Path) -> Optional[dict]:
    """None when there is no state file; ValueError when it exists but is unusable."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        state = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"state file is not valid JSON: {exc}") from exc
    if not isinstance(state, dict) or not isinstance(state.get("attempts", 0), int) or isinstance(state.get("attempts"), bool):
        raise ValueError("state file has an unexpected shape")
    return state


def list_runs(sha: str, run_cmd: Callable, repo: Optional[str] = None) -> list[dict]:
    """One status query for exactly one commit. Runs whose headSha differs are dropped locally."""
    command = ["gh", "run", "list", "--commit", sha, "--limit", str(LIST_LIMIT), "--json", FIELDS]
    if repo:
        command += ["--repo", repo]
    code, out, err = run_cmd(command)
    if code != 0:
        text = (err or out or "").strip()[:300]
        low = text.lower()
        raise GhQueryError(f"gh run list failed ({code}): {text}",
                           rate_limited=("rate limit" in low or "http 429" in low or "secondary rate" in low))
    try:
        data = json.loads(out)
    except ValueError as exc:
        raise GhQueryError(f"gh run list returned malformed JSON: {exc}") from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise GhQueryError("gh run list returned an unexpected JSON shape")
    return [item for item in data if item.get("headSha") == sha]


def _summary(runs: list[dict]) -> list[dict]:
    keep = ("databaseId", "status", "conclusion", "workflowName", "displayTitle", "url")
    return sorted(({k: run.get(k) for k in keep} for run in runs), key=lambda r: str(r["databaseId"]))


def _result(status: str, state: dict, polls: int, key: str) -> dict:
    conclusion = state.get("conclusion")
    label = status
    if status == COMPLETED:
        label = "SUCCESS" if conclusion == "success" else "FINISHED_NOT_SUCCESS"
    return {"status": status, "outcome": label, "key": key, "sha": state.get("sha"), "workkey": state.get("workkey"),
            "attempts": state.get("attempts", 0), "polls_this_call": polls, "conclusion": conclusion,
            "runs": state.get("runs", []), "last_error": state.get("last_error"),
            "exit_code": EXIT_CODES[label]}


class _Lock:
    def __init__(self, path: Path):
        self.path, self.handle = path, None

    def acquire(self) -> bool:
        if fcntl is None:  # pragma: no cover
            return True
        self.handle = open(self.path, "a+")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            return False
        return True

    def release(self) -> None:
        if self.handle is not None:
            self.handle.close()  # closing drops the flock; the OS drops it too if the process dies
            self.handle = None


def watch(workkey: str, sha: str, state_dir, *, backoff: Backoff = Backoff(),
          dispatch: Optional[Callable[[], None]] = None, repo: Optional[str] = None,
          run_cmd: Callable = default_run_cmd, clock: Callable[[], float] = time.time,
          sleep: Callable[[float], None] = time.sleep) -> dict:
    """Follow the runs of `sha` for at most `backoff.window` seconds. Safe to call again at any time."""
    if not SHA_RE.match(sha or ""):
        raise ValueError("sha must be a full 40-character lowercase hex commit id")
    if not workkey:
        raise ValueError("workkey is required")
    key = idempotency_key(workkey, sha)
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_path(state_dir, key)
    lock = _Lock(path.with_name(path.name[:-5] + ".lock"))
    if not lock.acquire():
        return _result(LOCKED, {"sha": sha, "workkey": workkey}, 0, key)
    try:
        try:
            state = read_state(path)
        except ValueError as exc:  # never guess: a damaged state could hide a dispatch
            return _result(STATE_UNREADABLE, {"sha": sha, "workkey": workkey, "last_error": str(exc)}, 0, key)
        if state is None:
            state = {"key": key, "sha": sha, "workkey": workkey, "status": WATCHING, "attempts": 0,
                     "next_poll_at": None, "runs": [], "conclusion": None, "last_error": None,
                     "dispatch": "NONE", "dispatched_at": None}
        if state.get("key") not in (None, key) or state.get("sha") not in (None, sha):
            return _result(STATE_UNREADABLE, {"sha": sha, "workkey": workkey,
                                              "last_error": "state file belongs to another key"}, 0, key)
        if state.get("status") in (COMPLETED, EXHAUSTED, UNCONFIRMED):
            return _result(state["status"], state, 0, key)  # terminal: zero gh calls

        if dispatch is not None and state.get("dispatch", "NONE") == "NONE":
            state["dispatch"], state["dispatched_at"] = "DISPATCHING", clock()  # intent first
            write_state(path, state)
            try:
                dispatch()
            except Exception:  # clean failure: nothing was dispatched, the key stays free
                state["dispatch"], state["dispatched_at"] = "NONE", None
                write_state(path, state)
                raise
            state["dispatch"] = "DISPATCHED"
            write_state(path, state)
        started = clock()
        deadline = started + backoff.window if backoff.window > 0 else None
        polls, edge_used = 0, False
        while True:
            attempts = state.get("attempts", 0)
            if backoff.max_attempts and attempts >= backoff.max_attempts:
                state["status"] = EXHAUSTED
                write_state(path, state)
                return _result(EXHAUSTED, state, polls, key)
            due = state.get("next_poll_at")
            now = clock()
            wait = max(0.0, (due - now) if due is not None else 0.0)
            if deadline is not None and now + wait > deadline:
                # The next poll lies beyond this call. If the schedule was made in this call, spend one
                # last poll exactly at the window edge (so a run that finishes inside the window is
                # seen); a schedule inherited from an earlier process is honoured without a call.
                if polls > 0 and not edge_used and deadline - now > 0:
                    wait, edge_used = deadline - now, True
                else:
                    return _result(WAITING, state, polls, key)
            if wait:
                sleep(wait)
            polls += 1
            state["attempts"] = attempts + 1
            error = None
            try:
                runs = list_runs(sha, run_cmd, repo)
            except GhQueryError as exc:
                error, runs = exc, []
            now = clock()
            if error is not None:
                state["last_error"] = str(error)[:200]
            else:
                state["last_error"] = None
                state["runs"] = _summary(runs)
                if runs and all(run.get("status") == "completed" for run in runs):
                    state["status"] = COMPLETED
                    ok = all(run.get("conclusion") == "success" for run in runs)
                    state["conclusion"] = "success" if ok else "not_success"
                    state["next_poll_at"] = None
                    write_state(path, state)
                    return _result(COMPLETED, state, polls, key)
                if (not runs and state.get("dispatch") == "DISPATCHING" and state.get("dispatched_at") is not None
                        and now - state["dispatched_at"] > backoff.dispatch_grace):
                    state["status"] = UNCONFIRMED  # never dispatch again on our own
                    write_state(path, state)
                    return _result(UNCONFIRMED, state, polls, key)
            delay = backoff.delay(state["attempts"] + 1)
            if error is not None and getattr(error, "rate_limited", False):
                delay = max(delay, backoff.max_interval)
            state["next_poll_at"] = now + delay
            write_state(path, state)
    finally:
        lock.release()


def gh_dispatch(workflow: str, ref: str, repo: Optional[str] = None, run_cmd: Callable = default_run_cmd) -> Callable[[], None]:
    def _dispatch() -> None:
        command = ["gh", "workflow", "run", workflow, "--ref", ref]
        if repo:
            command += ["--repo", repo]
        code, out, err = run_cmd(command)
        if code != 0:
            raise RuntimeError(f"gh workflow run failed ({code}): {(err or out).strip()[:300]}")
    return _dispatch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.automation.ci_watcher_v2", description="Follow the CI runs of one commit SHA.")
    parser.add_argument("--workkey", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--repo")
    parser.add_argument("--window", type=float, default=60.0)
    parser.add_argument("--base", type=float, default=5.0)
    parser.add_argument("--factor", type=float, default=2.0)
    parser.add_argument("--max-interval", type=float, default=60.0)
    parser.add_argument("--max-attempts", type=int, default=64)
    parser.add_argument("--dispatch-workflow")
    parser.add_argument("--ref")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if bool(args.dispatch_workflow) != bool(args.ref):
        print("--dispatch-workflow and --ref belong together", file=sys.stderr)
        return 2
    backoff = Backoff(base=args.base, factor=args.factor, max_interval=args.max_interval,
                      max_attempts=args.max_attempts, window=args.window)
    dispatch = gh_dispatch(args.dispatch_workflow, args.ref, args.repo) if args.dispatch_workflow else None
    try:
        result = watch(args.workkey, args.sha, args.state_dir, backoff=backoff, dispatch=dispatch, repo=args.repo)
    except ValueError as exc:
        print(f"CI_WATCHER_ERROR {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
