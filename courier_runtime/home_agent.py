"""Courier Home Agent: lets Courier (also from the cloud) do work on the
owner's own computer - safely, always reachable, never an open door.

Transport = a mailbox folder inside a private git repository that the
computer already pulls. The computer only ever connects OUTWARD (git pull /
push); no port is opened, nothing listens.

  mailbox/<host>/inbox/<job_id>.json    written by Courier (cloud or another device)
  mailbox/<host>/outbox/<job_id>.json   written by the home agent: result + receipt

Safety laws (content cannot grant authority):
- A job names an ACTION from a fixed catalog. There is no "run this command".
- What the computer may do is decided by GRANTS stored LOCALLY on that
  computer (COURIER_HOME), never by anything in the repository. A job in the
  repo can ask; only the owner's local grants can allow.
- Every job runs at most once (job id is the idempotency key); the outcome is
  written as a receipt, also for refusals.
- Process control goes through the surface supervisor (owned, by identity).
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

# action -> (access level, what it does). Read actions are safe by default;
# anything that changes the machine needs an explicit local grant.
CATALOG = {
    "host_health": ("read", "measure RAM/CPU/disk/autostart and explain (scripts/host_health.py)"),
    "surface_status": ("read", "how many Courier windows/workers/queued items"),
    "reclaim_idle_surfaces": ("control", "close Courier's own finished windows (owned + checkpointed only)"),
    "git_pull_repo": ("write", "update one allowlisted local repository"),
}
ACCESS_ORDER = {"read": 0, "write": 1, "control": 2}


@dataclass(frozen=True)
class LocalGrants:
    """Lives on the computer (COURIER_HOME/home_grants.json), edited only by the owner."""
    max_access: str = "read"                       # read | write | control
    allowed_actions: frozenset = frozenset({"host_health", "surface_status"})
    allowed_repos: frozenset = frozenset()         # absolute paths for git_pull_repo
    paused: bool = False                           # one switch: stop everything

    @classmethod
    def load(cls, path):
        p = Path(path)
        if not p.exists():
            return cls()                           # missing file = read-only defaults
        d = json.loads(p.read_text(encoding="utf-8"))
        return cls(d.get("max_access", "read"), frozenset(d.get("allowed_actions", [])),
                   frozenset(d.get("allowed_repos", [])), bool(d.get("paused", False)))


def why_refused(job, grants):
    """None if the job may run on this computer, else the reason (shown to the user)."""
    action = job.get("action")
    if grants.paused:
        return "home agent is paused by the owner"
    if action not in CATALOG:
        return f"unknown action {action!r}: only catalog actions exist, never free commands"
    if "argv" in job or "command" in job or "script" in job:
        return "jobs may not carry commands"
    if action not in grants.allowed_actions:
        return f"action {action!r} is not granted on this computer"
    if ACCESS_ORDER[CATALOG[action][0]] > ACCESS_ORDER[grants.max_access]:
        return f"action needs {CATALOG[action][0]} access, this computer allows {grants.max_access}"
    if action == "git_pull_repo" and job.get("params", {}).get("repo") not in grants.allowed_repos:
        return "repository is not on this computer's allowlist"
    return None


class HomeAgent:
    def __init__(self, mailbox_root, host, grants, handlers, clock=time.time):
        self.inbox = Path(mailbox_root) / host / "inbox"
        self.outbox = Path(mailbox_root) / host / "outbox"
        self.host, self.grants, self.handlers, self.clock = host, grants, handlers, clock

    def run_once(self):
        """Process every new job once. Returns the receipts written in this pass."""
        self.outbox.mkdir(parents=True, exist_ok=True)
        receipts = []
        for path in sorted(self.inbox.glob("*.json")) if self.inbox.exists() else []:
            job_id = path.stem
            out = self.outbox / f"{job_id}.json"
            if out.exists():
                continue                                   # already done: never twice
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                receipt = {"job_id": job_id, "status": "REFUSED", "reason": "unreadable job"}
            else:
                reason = why_refused(job, self.grants)
                if reason:
                    receipt = {"job_id": job_id, "action": job.get("action"), "status": "REFUSED", "reason": reason}
                else:
                    try:
                        result = self.handlers[job["action"]](job.get("params", {}))
                        receipt = {"job_id": job_id, "action": job["action"], "status": "DONE", "result": result}
                    except Exception as exc:               # the failure is reported, not hidden
                        receipt = {"job_id": job_id, "action": job["action"], "status": "FAILED",
                                   "reason": f"{type(exc).__name__}: {exc}"[:300]}
            receipt.update(host=self.host, finished_at=self.clock())
            out.write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
            receipts.append(receipt)
        return receipts


def default_handlers(surface_supervisor=None):
    """Real implementations; each one is the catalog action and nothing more."""
    def host_health(_params):
        from scripts.host_health import diagnose, snapshot
        s = snapshot()
        return {"findings": diagnose(s), "ram_used_pct": s["ram_used_pct"], "uptime_min": s["uptime_min"],
                "top": s["groups"][:8], "startup": [i["name"] for i in s["startup"]]}

    def surface_status(_params):
        return surface_supervisor.status() if surface_supervisor else {"note": "no surface registry on this host"}

    def reclaim_idle(_params):
        from courier_runtime.surfaces import adapter_for
        import sys
        return surface_supervisor.reclaim_idle(adapter_for(sys.platform).close) if surface_supervisor else []

    def git_pull_repo(params):
        import subprocess
        out = subprocess.run(["git", "-C", params["repo"], "pull", "--ff-only"], capture_output=True, text=True,
                             timeout=120)
        return {"returncode": out.returncode, "output": (out.stdout + out.stderr)[-800:]}

    return {"host_health": host_health, "surface_status": surface_status,
            "reclaim_idle_surfaces": reclaim_idle, "git_pull_repo": git_pull_repo}


def submit(mailbox_root, host, job_id, action, params=None):
    """Courier side (cloud or any device): put one job into a computer's inbox."""
    inbox = Path(mailbox_root) / host / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"{job_id}.json"
    if not path.exists():                                  # same job id twice = one job
        path.write_text(json.dumps({"action": action, "params": params or {}}, indent=1), encoding="utf-8")
    return path


def _git(repo, *args, timeout=120):
    import subprocess
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout)


def _single_instance(lock_path):
    """One home agent per computer. A stale lock (process gone or pid reused) is taken over."""
    import os
    from courier_runtime.ownership import OwnedProcess, is_same_process
    lock = Path(lock_path)
    if lock.exists():
        try:
            old = OwnedProcess(**json.loads(lock.read_text(encoding="utf-8")))
            if is_same_process(old):
                return False
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    lock.parent.mkdir(parents=True, exist_ok=True)
    me = OwnedProcess.capture(os.getpid(), "home-agent", "courier")
    lock.write_text(json.dumps(me.__dict__), encoding="utf-8")
    return True


def main(argv=None):
    """python -m courier_runtime.home_agent --repo <private mailbox repo> --host <name>
       [--home <COURIER_HOME>] [--every 120] [--once]"""
    import argparse
    import os
    p = argparse.ArgumentParser(prog="courier_runtime.home_agent")
    p.add_argument("--repo", required=True, help="local clone of the private repo holding mailbox/")
    p.add_argument("--host", required=True)
    p.add_argument("--home", default=os.environ.get("COURIER_HOME", str(Path.home() / ".courier")))
    p.add_argument("--every", type=int, default=120, help="seconds between checks (min 30)")
    p.add_argument("--once", action="store_true")
    a = p.parse_args(argv)
    home = Path(a.home)
    if not _single_instance(home / "home_agent.lock"):
        print("home agent already running on this computer")
        return 0
    from courier_runtime.surfaces import SurfaceSupervisor
    import sys
    sup = SurfaceSupervisor(home / "surfaces.json", a.host, sys.platform)
    while True:
        grants = LocalGrants.load(home / "home_grants.json")         # re-read: the owner can change it anytime
        _git(a.repo, "pull", "--ff-only", "-q")
        receipts = HomeAgent(Path(a.repo) / "mailbox", a.host, grants, default_handlers(sup)).run_once()
        for r in receipts:
            print(f"{r['job_id']}: {r['status']} {r.get('reason', '')}")
        if receipts:
            _git(a.repo, "add", f"mailbox/{a.host}/outbox")
            _git(a.repo, "commit", "-q", "-m", f"home-agent {a.host}: {len(receipts)} receipt(s)")
            _git(a.repo, "push", "-q")
        if a.once:
            return 0
        time.sleep(max(30, a.every))


if __name__ == "__main__":
    import sys
    sys.exit(main())
