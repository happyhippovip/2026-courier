"""Local provider hub: one queue, known Google (agy) and Muse slots, one job per slot.

Jobs are submitted in one place and dispatched to exactly one free, healthy slot of the
requested provider.  Overlapping write scopes never run at the same time.  Every state
change is appended to runtime/events.jsonl without prompts or credentials.

The hub never passes --dangerously-skip-permissions or --yolo and refuses the expensive
reasoning levels (xhigh/max/ultra).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psutil

from scripts.windows_muse_wall.slot_state import atomic_write, process_matches, read_json

HERE = Path(__file__).resolve().parent
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
AGY_EXE = LOCALAPPDATA / "agy" / "bin" / "agy.EXE"
MUSE_DIR = LOCALAPPDATA / "Programs" / "muse"

ALLOWED_EFFORTS = ("low", "medium", "high")
JOB_STATES = ("QUEUED", "RUNNING", "DONE", "FAILED")
HEALTH_STATES = ("READY", "AUTH_REQUIRED", "BROKEN", "EXPIRED", "QUOTA", "UNKNOWN")
PING_WORD = "HUBPONG"

_SECRET = re.compile(
    r"(ya29\.[\w.-]+|AIza[\w-]{20,}|1//[\w-]{20,}|sk-[\w-]{16,}"
    r"|(?i:bearer)\s+\S+"
    r"|(?i:token|api[_-]?key|secret|password|csrf[_-]?token)[\"']?\s*[:=]\s*\S+)"
)


def redact(text, limit=300):
    text = _SECRET.sub("<redacted>", text or "")
    return text[:limit]


def muse_binary():
    version = (MUSE_DIR / ".muse-version").read_text(encoding="utf-8").strip()
    return MUSE_DIR / f"muse-bin-{version}.exe"


def scope_key(path):
    return os.path.normcase(os.path.abspath(path)).rstrip("\\/") + os.sep


def scopes_overlap(first, second):
    if not first or not second:
        return False
    a, b = scope_key(first), scope_key(second)
    return a.startswith(b) or b.startswith(a)


def classify(exit_code, output, error, timed_out=False):
    blob = f"{output}\n{error}".lower()
    if timed_out:
        return "UNKNOWN"
    if exit_code == 0 and PING_WORD.lower() in output.lower():
        return "READY"
    if "expired" in blob:
        return "EXPIRED"
    if "resource_exhausted" in blob or " 429" in blob or "quota" in blob:
        return "QUOTA"
    if any(word in blob for word in ("login", "log in", "unauthenticated", "not authenticated", " 401", "sign in")):
        return "AUTH_REQUIRED"
    return "BROKEN"


class ProviderHub:
    def __init__(self, root=None, config=None, launcher=None):
        self.root = Path(root) if root else HERE / "runtime"
        self.config = config or read_json(HERE / "slots.json")
        self.jobs_dir = self.root / "jobs"
        self.slots_dir = self.root / "slots"
        self.events_path = self.root / "events.jsonl"
        self.launcher = launcher or subprocess.Popen
        self.children = {}
        for directory in (self.jobs_dir, self.slots_dir):
            directory.mkdir(parents=True, exist_ok=True)

    # ---- records -------------------------------------------------------------------
    @property
    def slots(self):
        return {slot["slot_id"]: slot for slot in self.config["slots"]}

    def event(self, job, state, result="", error=""):
        record = {
            "ts": time.time(),
            "provider": job.get("provider"),
            "slot": job.get("slot_id"),
            "account": job.get("account"),
            "job": job.get("job_id"),
            "start": job.get("started_at"),
            "state": state,
            "result": redact(result),
            "error": redact(error),
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def job_path(self, job_id):
        return self.jobs_dir / f"{job_id}.json"

    def jobs(self):
        found = [read_json(path) for path in sorted(self.jobs_dir.glob("*.json"))]
        return sorted(found, key=lambda job: job["created_at"])

    def save_job(self, job):
        job["updated_at"] = time.time()
        atomic_write(self.job_path(job["job_id"]), job)

    def health(self, slot_id):
        path = self.slots_dir / f"{slot_id}.health.json"
        return read_json(path) if path.exists() else {"state": "UNKNOWN"}

    # ---- submit --------------------------------------------------------------------
    def submit(self, provider, prompt, workdir=None, write_scope=None, effort=None, timeout_s=900):
        if provider not in {slot["provider"] for slot in self.config["slots"]}:
            raise ValueError(f"no slots for provider: {provider}")
        effort = effort or self.config.get("default_effort", "medium")
        if effort not in ALLOWED_EFFORTS:
            raise ValueError(f"effort {effort!r} not allowed; use one of {ALLOWED_EFFORTS}")
        job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        job = {
            "job_id": job_id,
            "provider": provider,
            "prompt": prompt,
            "workdir": str(Path(write_scope or workdir or self.root / "work" / job_id).resolve()),
            "write_scope": str(Path(write_scope).resolve()) if write_scope else None,
            "effort": effort,
            "timeout_s": int(timeout_s),
            "state": "QUEUED",
            "slot_id": None,
            "account": None,
            "process": None,
            "created_at": time.time(),
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "error": None,
        }
        self.save_job(job)
        self.event(job, "QUEUED")
        return job

    # ---- command lines -------------------------------------------------------------
    def command(self, slot, job):
        prompt, effort = job["prompt"], job["effort"]
        if slot["provider"] == "google":
            argv = [str(AGY_EXE), "-p", prompt, "--effort", effort,
                    "--print-timeout", f"{job['timeout_s']}s"]
            argv += ["--mode", "accept-edits"] if job["write_scope"] else ["--mode", "plan"]
            return argv
        if slot["provider"] == "muse":
            return [str(muse_binary()), "exec", "--reasoning-effort", effort,
                    "--workspace", job["workdir"], prompt]
        raise ValueError(f"unknown provider: {slot['provider']}")

    def environment(self, slot):
        env = dict(os.environ)
        if slot.get("profile_home"):
            env["USERPROFILE"] = slot["profile_home"]
            env["HOME"] = slot["profile_home"]
        return env

    # ---- dispatch ------------------------------------------------------------------
    def busy_slots(self, jobs):
        return {job["slot_id"] for job in jobs if job["state"] == "RUNNING"}

    def free_slot(self, provider, jobs):
        busy = self.busy_slots(jobs)
        for slot_id, slot in self.slots.items():
            if slot["provider"] != provider or slot_id in busy:
                continue
            if self.health(slot_id).get("state") in ("READY", "UNKNOWN"):
                return slot
        return None

    def start(self, job, slot):
        Path(job["workdir"]).mkdir(parents=True, exist_ok=True)
        out = open(self.jobs_dir / f"{job['job_id']}.out", "wb")
        err = open(self.jobs_dir / f"{job['job_id']}.err", "wb")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        child = self.launcher(self.command(slot, job), cwd=job["workdir"], env=self.environment(slot),
                              stdin=subprocess.DEVNULL, stdout=out, stderr=err, creationflags=flags)
        out.close()
        err.close()
        try:
            create_time = psutil.Process(child.pid).create_time()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            create_time = None
        job.update(state="RUNNING", slot_id=slot["slot_id"], account=slot.get("account"),
                   started_at=time.time(), process={"pid": child.pid, "create_time": create_time})
        self.children[job["job_id"]] = child
        self.save_job(job)
        self.event(job, "RUNNING")

    def finish(self, job, exit_code, error=None):
        output = (self.jobs_dir / f"{job['job_id']}.out").read_text(encoding="utf-8", errors="replace")
        job.update(state="DONE" if exit_code == 0 and not error else "FAILED",
                   exit_code=exit_code, error=error, finished_at=time.time())
        self.children.pop(job["job_id"], None)
        self.save_job(job)
        self.event(job, job["state"], result=output, error=error or "")

    def kill_tree(self, job):
        if not process_matches(job.get("process")):
            return
        root = psutil.Process(job["process"]["pid"])
        for proc in root.children(recursive=True) + [root]:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass

    def reconcile(self, jobs):
        now = time.time()
        for job in jobs:
            if job["state"] != "RUNNING":
                continue
            child = self.children.get(job["job_id"])
            if child is not None and child.poll() is not None:
                self.finish(job, child.returncode)
            elif now - job["started_at"] > job["timeout_s"] + 60:
                self.kill_tree(job)
                self.finish(job, None, error="timeout")
            elif child is None and not process_matches(job.get("process")):
                self.finish(job, None, error="orphaned: hub restarted, exit code unknown; output kept")

    def tick(self):
        jobs = self.jobs()
        self.reconcile(jobs)
        jobs = self.jobs()
        for job in jobs:
            if job["state"] != "QUEUED":
                continue
            running = [other for other in jobs if other["state"] == "RUNNING"]
            if any(scopes_overlap(job["write_scope"], other["write_scope"]) for other in running):
                continue
            slot = self.free_slot(job["provider"], jobs)
            if slot is None:
                continue
            self.start(job, slot)
            jobs = self.jobs()

    def idle(self):
        return all(job["state"] in ("DONE", "FAILED") for job in self.jobs())

    def run(self, until_idle=False, max_seconds=None):
        with DispatcherLock(self.root / "hub.lock"):
            began = time.time()
            while True:
                self.tick()
                if until_idle and self.idle():
                    return
                if max_seconds and time.time() - began > max_seconds:
                    return
                time.sleep(self.config.get("poll_seconds", 3))

    # ---- health --------------------------------------------------------------------
    def check(self, slot_id, timeout_s=150):
        slot = self.slots[slot_id]
        if slot_id in self.busy_slots(self.jobs()):
            return {"state": "BUSY"}
        workdir = self.root / "health" / slot_id
        workdir.mkdir(parents=True, exist_ok=True)
        probe = {"prompt": f"Antworte nur mit dem Wort {PING_WORD}.", "effort": "low",
                 "timeout_s": timeout_s, "write_scope": None, "workdir": str(workdir)}
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        began, timed_out = time.time(), False
        try:
            done = subprocess.run(self.command(slot, probe), cwd=workdir, env=self.environment(slot),
                                  stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout_s + 20,
                                  creationflags=flags)
            code, out, err = done.returncode, done.stdout.decode(errors="replace"), done.stderr.decode(errors="replace")
        except subprocess.TimeoutExpired:
            code, out, err, timed_out = None, "", "timeout", True
        except OSError as exc:
            code, out, err = None, "", str(exc)
        state = classify(code, out, err, timed_out)
        record = {"slot_id": slot_id, "provider": slot["provider"], "account": slot.get("account"),
                  "state": state, "checked_at": time.time(), "seconds": round(time.time() - began, 1),
                  "detail": "" if state == "READY" else redact(err or out, 200)}
        atomic_write(self.slots_dir / f"{slot_id}.health.json", record)
        return record


class DispatcherLock:
    """Exactly one dispatcher; a lock left by a dead dispatcher is reclaimed."""

    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        if self.path.exists():
            try:
                holder = read_json(self.path)
            except Exception:
                holder = None
            if holder and process_matches(holder):
                raise RuntimeError(f"dispatcher already running: pid {holder['pid']}")
        me = psutil.Process()
        atomic_write(self.path, {"pid": me.pid, "create_time": me.create_time()})
        return self

    def __exit__(self, *_):
        self.path.unlink(missing_ok=True)


def ensure_dispatcher(hub):
    """Start a background dispatcher unless a live one already holds the lock."""
    lock = hub.root / "hub.lock"
    if lock.exists():
        try:
            if process_matches(read_json(lock)):
                return False
        except Exception:
            pass
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
             | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    subprocess.Popen([str(pythonw if pythonw.exists() else python), "-m", "scripts.provider_hub.hub",
                      "run", "--until-idle"], cwd=str(HERE.parent.parent), creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def ask(hub):
    def read(label):
        return input(label).replace("﻿", "").strip()

    provider = read("Provider [google/muse] (Enter = google): ").lower() or "google"
    prompt = read("Auftrag: ")
    scope = read("Ordner, in dem geschrieben werden darf (Enter = nur antworten): ").strip('"')
    if provider not in ("google", "muse"):
        print(f"Unbekannter Provider: {provider!r}. Bitte google oder muse.")
        return 1
    if not prompt:
        print("Kein Auftrag eingegeben.")
        return 1
    job = hub.submit(provider, prompt, write_scope=scope or None)
    ensure_dispatcher(hub)
    print(f"Job {job['job_id']} eingereiht. Warte auf Ergebnis ...")
    while True:
        time.sleep(3)
        current = read_json(hub.job_path(job["job_id"]))
        if current["state"] in ("DONE", "FAILED"):
            break
    output = (hub.jobs_dir / f"{job['job_id']}.out").read_text(encoding="utf-8", errors="replace")
    print(f"\n[{current['state']}] slot={current['slot_id']}\n{output}")
    if current["error"]:
        print(f"Fehler: {current['error']}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--provider", required=True, choices=["google", "muse"])
    submit.add_argument("--prompt", required=True)
    submit.add_argument("--write-scope")
    submit.add_argument("--workdir")
    submit.add_argument("--effort", choices=ALLOWED_EFFORTS)
    submit.add_argument("--timeout", type=int, default=900)
    run = sub.add_parser("run")
    run.add_argument("--until-idle", action="store_true")
    run.add_argument("--max-seconds", type=int)
    health = sub.add_parser("health")
    health.add_argument("slots", nargs="*")
    sub.add_parser("status")
    sub.add_parser("ask")
    args = parser.parse_args(argv)
    hub = ProviderHub()
    if args.cmd == "ask":
        return ask(hub)
    if args.cmd == "submit":
        job = hub.submit(args.provider, args.prompt, args.workdir, args.write_scope, args.effort, args.timeout)
        ensure_dispatcher(hub)
        print(job["job_id"])
    elif args.cmd == "run":
        hub.run(until_idle=args.until_idle, max_seconds=args.max_seconds)
    elif args.cmd == "health":
        for slot_id in args.slots or list(hub.slots):
            print(json.dumps(hub.check(slot_id), sort_keys=True))
    elif args.cmd == "status":
        for slot_id, slot in hub.slots.items():
            print(f"SLOT {slot_id:10} {slot['provider']:7} health={hub.health(slot_id).get('state')}")
        for job in hub.jobs():
            print(f"JOB  {job['job_id']} {job['provider']:7} {job['state']:8} slot={job['slot_id']} "
                  f"exit={job['exit_code']} error={job['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
