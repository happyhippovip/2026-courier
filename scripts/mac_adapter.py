#!/usr/bin/env python3
"""Mac thin adapter over the accepted cannon core. No rewrite, no daemon.

Platform-specific surface only:
  - Mac default state dir (~/.courier/motor, overridable via
    COURIER_STATE_DIR or explicit argument)
  - JSON status snapshot for a browser UI to poll (no server bundled here)
  - CLI verbs mapping 1:1 to CannonMotor controls

Core (scripts/cannon_motor.py, scripts/work_queue.py) is imported read-only
and never modified by this adapter. stdlib only.
"""
import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.cannon_motor import CannonMotor  # noqa: E402

WORK_QUEUE = Path(__file__).resolve().parent / "work_queue.py"


def default_state_dir():
    override = os.environ.get("COURIER_STATE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".courier" / "motor"


class MacAdapter:
    def __init__(self, state_dir=None):
        self.state_dir = Path(state_dir or default_state_dir())
        self.motor = CannonMotor(self.state_dir)

    # ---- controls (pass-through, same semantics as core) ----
    def start(self, mode=None, limit=None, cooldown=5.0):
        return self._rebind(self.motor.start(mode=mode, limit=limit,
                                             cooldown=cooldown))

    def pause(self):
        return self._rebind(self.motor.request_pause())

    def resume(self):
        return self._rebind(self.motor.request_resume())

    def stop(self):
        return self._rebind(self.motor.request_stop())

    def step(self):
        return self._rebind(self.motor.run_step())

    def run(self, max_steps=1000):
        reports = self.motor.run(max_steps)
        return self._rebind({"reports": len(reports)})

    def dauerlauf(self, art="begrenzt", limit=None, cooldown=5.0,
                  max_cycles=None, idle_sleep=5.0, local_fake=False):
        """Overnight entry: art begrenzt (FINITE) or unendlich (INFINITE).
        Bounded supervisor; returns when terminal or cycles exhausted."""
        return self.supervise(max_cycles, idle_sleep,
                              start=(art, limit, cooldown, local_fake))

    def supervise(self, max_cycles=None, idle_sleep=5.0, start=None):
        # One existing motor supervisor per state directory, including CLI
        # retries. This is an instance lock, not another task/lease authority.
        lock = (self.state_dir / "supervisor.lock").open("a")
        try:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                lock.close()
                return {"started": False, "reason": "supervisor_active"}
            self.motor._load()
            if start is not None:
                art, limit, cooldown, local_fake = start
                mode = "INFINITE" if art == "unendlich" else "FINITE"
                started = self.motor.start(mode=mode, limit=limit,
                                           cooldown=cooldown,
                                           local_fake=local_fake)
                if not started.get("started"):
                    return self._rebind(started)
            return self._rebind(self.motor.supervise(max_cycles, idle_sleep))
        finally:
            if not lock.closed:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
                lock.close()

    def save_prompt(self, prompt_id, text, semantics="readonly"):
        return self._rebind(
            self.motor.save_prompt(prompt_id, text, semantics))

    def _rebind(self, out):
        self.motor = CannonMotor(self.state_dir)
        if isinstance(out, dict):
            out = dict(out)
            out["snapshot"] = self.status()
        return out

    # ---- browser-pollable truth (backend files stay authoritative) ----
    def status(self):
        snap = self.motor.queue_snapshot()
        counts = {}
        for info in snap["tasks"].values():
            counts[info.get("status")] = counts.get(info.get("status"), 0) + 1
        try:
            mtime = self.motor.motor_file.stat().st_mtime
        except OSError:
            mtime = None
        inv = self.motor.invariants()
        remaining = inv.get("REMAINING")
        return {"platform": platform.system().lower(),
                "state": self.motor.state,
                "error": self.motor.m.get("error"),
                "run_id": self.motor.m["run_id"],
                "current_task": self.motor.m["current_task"],
                "task_counts": counts,
                "needs_review": list(self.motor.m["needs_review"]),
                "waiting_for_work": self.motor.m.get("waiting_for_work", False),
                "invariants": inv,
                "motor_file_mtime": mtime,
                "state_dir": str(self.state_dir),
                "overnight": {
                    "dauerlauf_aktiv": self.motor.state in (
                        "RUNNING", "STOP_AFTER_CURRENT", "PAUSED"),
                    "modus": "NORMAL",
                    "gleichzeitig": 1,
                    "cooldown_s": self.motor.m.get("cooldown_seconds", 5.0),
                    "laufart": ("UNENDLICH"
                                if inv.get("RUN_MODE") == "INFINITE"
                                else "BEGRENZT"),
                    "gestartet": self.motor.m.get("started_count", 0),
                    "erledigt": self.motor.m.get("done_count", 0),
                    "verbleibend": ("∞" if remaining is None
                                    else remaining),
                    "aktuelle_aufgabe": self.motor.m.get("current_task"),
                    "letztes_ergebnis": self.motor.m.get("last_result"),
                    "wartet": counts.get("READY", 0) + counts.get("WAITING", 0),
                    "blockiert": counts.get("BLOCKED", 0),
                    "braucht_dich": (len(self.motor.m.get("needs_review", []))
                                     + counts.get("HUMAN_GATE", 0))}}

    # ---- deterministic seeding via work_queue CLI (reused, unmodified) ----
    def seed(self, n, package="mac-pk"):
        if type(n) is not int or not 1 <= n <= 100:
            raise ValueError("seed is a small explicit demo helper (1..100)")
        subprocess.check_output(
            [sys.executable, str(WORK_QUEUE), "--state-dir",
             str(self.state_dir), "init", package], text=True)
        for i in range(1, n + 1):
            subprocess.check_output(
                [sys.executable, str(WORK_QUEUE), "--state-dir",
                 str(self.state_dir), "add", json.dumps({
                     "task_id": f"t{i}", "package_id": package,
                     "description": f"mac task {i}",
                     "dependencies": [], "read_scopes": [],
                     "write_scopes": [f"mac-scope-{i}"],
                     "status": "READY", "priority": i})], text=True)
        return {"seeded": n, "package": package}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", default=None)
    ap.add_argument("verb", choices=["status", "start", "pause", "resume",
                                     "stop", "step", "run", "seed",
                                     "dauerlauf", "supervise", "save-prompt"])
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--art", default="begrenzt")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cooldown", type=float, default=5.0)
    ap.add_argument("--local-fake", action="store_true")
    ap.add_argument("--prompt-id", default=None)
    ap.add_argument("--semantics", default="readonly")
    ap.add_argument("--text", default="")
    args = ap.parse_args(argv)
    adapter = MacAdapter(args.state_dir)
    if args.verb == "seed":
        print(json.dumps(adapter.seed(args.n)))
    elif args.verb == "dauerlauf":
        print(json.dumps(adapter.dauerlauf(
            art=args.art, limit=args.limit, cooldown=args.cooldown,
            local_fake=args.local_fake),
            default=str))
    elif args.verb == "save-prompt":
        print(json.dumps(adapter.save_prompt(
            args.prompt_id, args.text, args.semantics)))
    elif args.verb == "start":
        print(json.dumps(adapter.start(cooldown=args.cooldown), default=str))
    else:
        print(json.dumps(getattr(adapter, args.verb)(), default=str))


if __name__ == "__main__":
    main()
