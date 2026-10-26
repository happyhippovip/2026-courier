"""CI watcher v2: follow the GitHub runs of ONE commit SHA with few, bounded queries.

Stand-alone. It does not change or replace scripts/github_worker_adapter.py: it is a
single-invocation helper (no loop outside one call, no scheduler, no second engine, no
model call). Only `gh run list --commit <sha>` is used for status; `gh workflow run` is
used only when the caller passes a dispatch workflow. It is an OBSERVER: its exit code reports
what GitHub showed; it is not a merge gate and decides nothing about merging.

Guarantees (proved by tests/automation/test_ci_watcher_v2*.py with a gh stub and real processes):
* queries are scoped to one SHA (`--commit SHA --limit 20`), runs of other SHAs are ignored;
* bounded exponential backoff: base, factor, max interval, max attempts are configurable,
  clock and sleep are injectable (deterministic);
* progress (attempt counter, next poll time, runs, terminal result) lives in one small state
  file written atomically (tmp + fsync + os.replace); a restart resumes it and never polls
  before `next_poll_at`; a terminal result costs zero further gh calls;
* idempotency key `<workkey>@<sha>`: the dispatch callable runs at most once per key, ever.
  A crash between the DISPATCHING marker and the dispatch result is never "healed" by a
  second dispatch (the run is adopted if it shows up, otherwise DISPATCH_UNCONFIRMED).
  Every dispatch failure whose acceptance cannot be excluded (timeout, HTTP 5xx, network, any
  unrecognised gh error) is AMBIGUOUS and keeps the marker. Only a failure that provably never
  reached GitHub (gh could not start, HTTP 4xx other than 408, gh usage/auth errors) frees the key;
* one process per key at a time: flock where available (released by the OS when a process dies, so
  a SIGKILL leaves no stale lock); where there is no fcntl (Windows) an O_EXCL lock file with a
  heartbeat, taken over only after `stale_after` seconds without heartbeat.

What counts as "finished" (the one rule, CW-2):
* DISPATCHED BY THIS KEY: only runs with `createdAt >= dispatched_at - 5s` (clock-skew allowance) and
  `event == workflow_dispatch` (when gh reports the event) belong to the dispatch. A finished run from
  before the dispatch never counts. SUCCESS/FINISHED_NOT_SUCCESS only once at least one such run is
  seen and all of them are completed. If none appears within `dispatch_grace` seconds the result is
  DISPATCH_UNCONFIRMED.
* OBSERVER MODE (no dispatch by this key): all runs of the SHA count, and completion needs a
  stability window of two consecutive polls that list the same, completely finished set of runs
  (so a workflow that registers a moment after the first one finished cannot yield a false SUCCESS).
  It cannot know a workflow that has not been created yet at both polls: UNKNOWN beyond that.

CLI (watch only unless --dispatch-workflow is given):
    python -m tools.automation.ci_watcher_v2 --workkey WK --sha <40 hex> --state-dir DIR
        [--window 60] [--base 5] [--factor 2] [--max-interval 60] [--max-attempts 64]
        [--dispatch-workflow FILE --ref BRANCH] [--repo owner/name] [--reset-state]
Exit codes: 0 all runs success - 1 runs finished but not all success - 2 usage (also: --base and
--max-interval must be >= 1, --factor >= 1) - 10 still waiting (window over; run again) - 11 attempts
exhausted - 12 dispatch unconfirmed - 13 locked by another process - 14 state file unreadable -
15 dispatch ambiguous (may have reached GitHub; NOT repeated; check GitHub, then run again to watch) -
16 dispatch failed cleanly (nothing was dispatched, the key is free) - 17 I/O error on the state/lock
file - 18 --reset-state refused (state is not COMPLETED/EXHAUSTED). Every outcome prints one JSON line.

--reset-state: for a state that is COMPLETED or EXHAUSTED only (e.g. after a re-run of a failed CI):
clears status, attempts, runs and schedule, KEEPS the dispatch marker (a dispatch is never repeated for
the same workkey; use a new workkey for a new dispatch). A state in WATCHING, DISPATCHING or
DISPATCH_UNCONFIRMED is never reset by the tool: look at GitHub, then delete the dotfile by hand.
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
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

try:  # POSIX flock; without fcntl (Windows) _Lock falls back to an O_EXCL lock file
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LIST_LIMIT = 20
FIELDS = "databaseId,status,conclusion,displayTitle,headSha,workflowName,url,createdAt,event"
DISPATCH_SKEW = 5.0  # seconds a GitHub createdAt may precede our local dispatch clock

WATCHING, COMPLETED, EXHAUSTED, DISPATCHING, UNCONFIRMED = (
    "WATCHING", "COMPLETED", "EXHAUSTED", "DISPATCHING", "DISPATCH_UNCONFIRMED")
WAITING, LOCKED, STATE_UNREADABLE = "WAITING", "LOCKED", "STATE_UNREADABLE"
DISPATCH_AMBIGUOUS, DISPATCH_FAILED, IO_ERROR, RESET_REFUSED = "DISPATCH_AMBIGUOUS", "DISPATCH_FAILED", "IO_ERROR", "RESET_REFUSED"
EXIT_CODES = {"SUCCESS": 0, "FINISHED_NOT_SUCCESS": 1, WAITING: 10, EXHAUSTED: 11, UNCONFIRMED: 12,
              LOCKED: 13, STATE_UNREADABLE: 14, DISPATCH_AMBIGUOUS: 15, DISPATCH_FAILED: 16, IO_ERROR: 17,
              RESET_REFUSED: 18, "RESET": 0, "NO_STATE": 0}
MIN_INTERVAL = 1.0  # CLI lower bound for --base and --max-interval (CW-4)


class GhQueryError(RuntimeError):
    """Transient problem with one status query (non-zero exit, rate limit, malformed JSON)."""

    def __init__(self, message: str, rate_limited: bool = False):
        super().__init__(message)
        self.rate_limited = rate_limited


class AmbiguousDispatch(RuntimeError):
    """The dispatch command may or may not have reached GitHub (e.g. it timed out).
    The DISPATCHING marker is kept, so the key is never dispatched a second time."""


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
    """Atomic: the target is only ever replaced by a complete, fsynced temp file; a failure leaves the old
    file intact and removes the temp file. On Windows os.replace can briefly fail with PermissionError
    (a scanner holds the target): retried a few times."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
    for field in ("next_poll_at", "dispatched_at"):
        value = state.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value != value):
            raise ValueError(f"state file field {field} is not a number")
    if not isinstance(state.get("last_complete_ids"), (list, type(None))):
        raise ValueError("state file has an unexpected shape")
    if not isinstance(state.get("runs", []), list) or state.get("dispatch", "NONE") not in ("NONE", "DISPATCHING", "DISPATCHED") \
            or state.get("status", WATCHING) not in (WATCHING, COMPLETED, EXHAUSTED, UNCONFIRMED):
        raise ValueError("state file has an unexpected shape")
    return state


def list_runs(sha: str, run_cmd: Callable, repo: Optional[str] = None) -> list[dict]:
    """One status query for exactly one commit. Runs whose headSha differs are dropped locally."""
    command = ["gh", "run", "list", "--commit", sha, "--limit", str(LIST_LIMIT), "--json", FIELDS]
    if repo:
        command += ["--repo", repo]
    try:
        code, out, err = run_cmd(command)
    except (subprocess.TimeoutExpired, OSError) as exc:  # a read-only query: safe to count as a failed poll
        raise GhQueryError(f"gh run list could not run: {type(exc).__name__}: {str(exc)[:200]}") from exc
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
    """flock where available; otherwise an O_EXCL lock file with a heartbeat (CW-5)."""

    def __init__(self, path: Path, stale_after: float = 600.0):
        self.path, self.handle, self.stale_after = path, None, stale_after
        self.excl_path = path.with_name(path.name + ".x")
        self.excl_held = False

    def acquire(self) -> bool:
        if fcntl is None:
            return self._acquire_excl()
        self.handle = open(self.path, "a+")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            return False
        return True

    def _acquire_excl(self) -> bool:
        for _ in range(2):
            try:
                fd = os.open(self.excl_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.excl_path.stat().st_mtime
                except OSError:
                    continue  # vanished between the two calls: try to create it again
                if age < self.stale_after:
                    return False
                grave = self.excl_path.with_name(f"{self.excl_path.name}.stale.{os.getpid()}")
                try:  # the rename is atomic: of several processes that see a stale lock only one wins it
                    os.replace(self.excl_path, grave)
                    os.unlink(grave)
                except OSError:
                    return False
                continue
            with os.fdopen(fd, "w") as handle:
                handle.write(str(os.getpid()))
            self.excl_held = True
            return True
        return False

    def touch(self) -> None:
        """Heartbeat of the O_EXCL fallback (the flock needs none)."""
        if self.excl_held:
            try:
                os.utime(self.excl_path)
            except OSError:
                pass

    def release(self) -> None:
        if self.handle is not None:
            self.handle.close()  # closing drops the flock; the OS drops it too if the process dies
            self.handle = None
        if self.excl_held:
            self.excl_held = False
            try:
                os.unlink(self.excl_path)
            except OSError:
                pass


def _epoch(text) -> Optional[float]:
    if not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def select_runs(runs: list[dict], state: dict) -> tuple[list[dict], bool]:
    """The runs this watcher answers for, and whether they are "ours" (dispatched by this key)."""
    if state.get("dispatch") in ("DISPATCHING", "DISPATCHED") and state.get("dispatched_at") is not None:
        floor = state["dispatched_at"] - DISPATCH_SKEW
        ours = []
        for run in runs:
            created = _epoch(run.get("createdAt"))
            if created is None or created < floor:
                continue  # unknown or older than our dispatch: never ours
            if run.get("event") not in (None, "workflow_dispatch"):
                continue
            ours.append(run)
        return ours, True
    return runs, False


def reset_state(workkey: str, sha: str, state_dir) -> dict:
    """CW-3: allow watching again after a terminal COMPLETED/EXHAUSTED (see module docstring)."""
    if not SHA_RE.match(sha or "") or not workkey:
        raise ValueError("a workkey and a full 40-character lowercase hex sha are required")
    key = idempotency_key(workkey, sha)
    path = state_path(Path(state_dir), key)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _Lock(path.with_name(path.name[:-5] + ".lock"))
    if not lock.acquire():
        return _result(LOCKED, {"sha": sha, "workkey": workkey}, 0, key)
    try:
        try:
            state = read_state(path)
        except ValueError as exc:
            return _result(STATE_UNREADABLE, {"sha": sha, "workkey": workkey, "last_error": str(exc)}, 0, key)
        if state is None:
            return _result("NO_STATE", {"sha": sha, "workkey": workkey}, 0, key)
        if state.get("status") not in (COMPLETED, EXHAUSTED):
            return _result(RESET_REFUSED, dict(state, last_error=f"state is {state.get('status')}; only COMPLETED/EXHAUSTED "
                                                              "can be reset (check GitHub, then delete the dotfile by hand)"), 0, key)
        state.update({"status": WATCHING, "attempts": 0, "next_poll_at": None, "runs": [], "conclusion": None,
                      "last_error": None, "last_complete_ids": None})
        write_state(path, state)
        return _result("RESET", state, 0, key)
    finally:
        lock.release()


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
    lock = _Lock(path.with_name(path.name[:-5] + ".lock"), stale_after=max(600.0, 3 * backoff.max_interval + 300.0))
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
            except AmbiguousDispatch:  # may have been sent: keep the marker, report, never retry on our own
                raise
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
            if backoff.max_interval > 0:  # a clock that jumped back (or a bad state) must not park the watcher
                wait = min(wait, backoff.max_interval)
            if deadline is not None and now + wait > deadline:
                # The next poll lies beyond this call. If the schedule was made in this call, spend one
                # last poll exactly at the window edge (so a run that finishes inside the window is
                # seen); a schedule inherited from an earlier process is honoured without a call.
                if polls > 0 and not edge_used and deadline - now > 0:
                    wait, edge_used = deadline - now, True
                else:
                    return _result(WAITING, state, polls, key)
            lock.touch()
            if wait:
                sleep(wait)
            lock.touch()
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
                considered, ours = select_runs(runs, state)
                state["runs"] = _summary(considered)
                finished = bool(considered) and all(run.get("status") == "completed" for run in considered)
                ids = sorted(str(run.get("databaseId")) for run in considered)
                if finished and (ours or state.get("last_complete_ids") == ids):
                    state["status"] = COMPLETED  # ours: the expected run is seen and finished; observer: 2 identical complete polls
                    ok = all(run.get("conclusion") == "success" for run in considered)
                    state["conclusion"] = "success" if ok else "not_success"
                    state["next_poll_at"] = None
                    state["last_complete_ids"] = ids
                    write_state(path, state)
                    return _result(COMPLETED, state, polls, key)
                state["last_complete_ids"] = ids if finished else None  # first complete look: confirm once more
                if (not considered and state.get("dispatch") in ("DISPATCHING", "DISPATCHED")
                        and state.get("dispatched_at") is not None and now - state["dispatched_at"] > backoff.dispatch_grace):
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


_HTTP = re.compile(r"HTTP (\d{3})")
_NEVER_SENT = ("unknown flag", "required flag", "unknown command", "accepts ", "gh auth login", "authentication token",
               "to get started with github cli", "not logged in")


def _rejected_before_acceptance(code: int, text: str) -> bool:
    """True only for gh failures that prove GitHub did not accept the dispatch: an HTTP 4xx answer (a 408 timeout
    excluded) or a gh usage/authentication error raised before any request. Everything else (5xx, network, empty
    or unknown text) may have been accepted and is ambiguous (CW-6)."""
    match = _HTTP.search(text)
    if match:
        status = int(match.group(1))
        return 400 <= status < 500 and status != 408
    low = text.lower()
    return any(marker in low for marker in _NEVER_SENT)


def gh_dispatch(workflow: str, ref: str, repo: Optional[str] = None, run_cmd: Callable = default_run_cmd) -> Callable[[], None]:
    def _dispatch() -> None:
        command = ["gh", "workflow", "run", workflow, "--ref", ref]
        if repo:
            command += ["--repo", repo]
        try:
            code, out, err = run_cmd(command)
        except subprocess.TimeoutExpired as exc:  # outcome unknown: GitHub may have accepted the request
            raise AmbiguousDispatch(f"gh workflow run timed out after {exc.timeout}s; dispatch state unknown") from exc
        except OSError as exc:  # gh could not even be started: nothing was sent
            raise RuntimeError(f"gh could not be started: {exc}") from exc
        if code != 0:
            text = (err or out or "").strip()[:300]
            if _rejected_before_acceptance(code, text):
                raise RuntimeError(f"gh workflow run rejected ({code}): {text}")
            raise AmbiguousDispatch(f"gh workflow run failed ({code}) without proof that GitHub refused it: {text}")
    return _dispatch


def _failure(status: str, workkey: str, sha: str, message: str) -> dict:
    return {"status": status, "outcome": status, "key": idempotency_key(workkey, sha), "sha": sha, "workkey": workkey,
            "error": message[:300], "exit_code": EXIT_CODES[status]}


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
    parser.add_argument("--reset-state", action="store_true",
                        help="allow watching again after COMPLETED/EXHAUSTED (keeps the dispatch marker); no gh call")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if bool(args.dispatch_workflow) != bool(args.ref):
        print("--dispatch-workflow and --ref belong together", file=sys.stderr)
        return 2
    if args.window < 0 or args.factor < 1 or args.max_attempts < 0 or args.base < MIN_INTERVAL or args.max_interval < MIN_INTERVAL:
        print(f"--base and --max-interval must be >= {MIN_INTERVAL:g}, --window and --max-attempts >= 0, --factor >= 1", file=sys.stderr)
        return 2
    backoff = Backoff(base=args.base, factor=args.factor, max_interval=args.max_interval,
                      max_attempts=args.max_attempts, window=args.window)
    dispatch = gh_dispatch(args.dispatch_workflow, args.ref, args.repo) if args.dispatch_workflow else None
    try:
        if args.reset_state:
            result = reset_state(args.workkey, args.sha, args.state_dir)
        else:
            result = watch(args.workkey, args.sha, args.state_dir, backoff=backoff, dispatch=dispatch, repo=args.repo)
    except ValueError as exc:
        print(f"CI_WATCHER_ERROR {exc}", file=sys.stderr)
        return 2
    except AmbiguousDispatch as exc:  # the marker stays: a second call watches, it never dispatches again
        result = _failure(DISPATCH_AMBIGUOUS, args.workkey, args.sha, str(exc))
    except OSError as exc:  # state dir, state file or lock file not usable
        result = _failure(IO_ERROR, args.workkey, args.sha, f"{type(exc).__name__}: {exc}")
    except RuntimeError as exc:  # clean dispatch failure: nothing was dispatched, the key is free again
        result = _failure(DISPATCH_FAILED, args.workkey, args.sha, str(exc))
    print(json.dumps(result, sort_keys=True))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
