"""Surface budget: WORK != WINDOW.

One host-local supervisor decides, before any Courier-controlled window,
terminal or session is opened, whether the work can reuse an existing owned
surface, is a duplicate of work already running, should wait in a queue, can
run headless, or may really open a new visible surface. Repeating the same
continuation prompt 100 times wakes the existing campaign once; it never
opens 100 windows.

Order of preference (product law):
  1. reuse a healthy owned idle surface      -> REUSE
  2. join work that is already running        -> COALESCED
  3. headless/background execution            -> HEADLESS (when allowed and the
     budget or host pressure says conserve)
  4. open a new visible surface               -> OPEN (below the soft limit; between soft
     and hard only for work that genuinely needs a window)
  5. wait behind the current workers          -> QUEUED (at the hard limit or under
     severe host pressure: SURFACE_BUDGET_EXHAUSTED)

Closing is ownership-safe: a surface is only closed when Courier owns it, its
(pid, create_time) identity still matches, no work is active, a durable
checkpoint exists and nothing unsaved would be lost. Never by process name.
"""
import dataclasses
import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

STARTING, WORKING, IDLE_READY = "STARTING", "WORKING", "IDLE_READY"
WAITING_FOR_USER, WAITING_FOR_OS = "WAITING_FOR_USER", "WAITING_FOR_OS"
TERMINAL_HOST_FAILED, SURFACE_CORRUPTED = "TERMINAL_HOST_FAILED", "SURFACE_CORRUPTED"
COMPLETED, PARKED = "COMPLETED", "PARKED"
BUSY = {STARTING, WORKING, WAITING_FOR_USER, WAITING_FOR_OS}
REUSABLE = {IDLE_READY, PARKED}
DEAD = {TERMINAL_HOST_FAILED, SURFACE_CORRUPTED, COMPLETED}

NORMAL, CONSERVE, NO_NEW_VISIBLE = "NORMAL", "CONSERVE_SURFACES", "NO_NEW_VISIBLE_SURFACES"
SURFACE_BUDGET_EXHAUSTED = "SURFACE_BUDGET_EXHAUSTED"


@dataclass
class Surface:
    surface_id: str
    provider: str
    host: str
    os: str
    owner: str
    workkey: str
    visible: bool
    state: str = STARTING
    pid: int = 0
    create_time: float = 0.0
    parent_pid: int = 0
    window_id: str = ""
    created_at: float = 0.0
    last_activity: float = 0.0
    checkpoint: str = ""          # durable checkpoint reference; required before closing
    unsaved: bool = False         # true while the surface holds work not yet persisted


@dataclass(frozen=True)
class Budget:
    soft: int = 3                 # visible Courier surfaces before conserving
    hard: int = 5                 # visible Courier surfaces never exceeded
    ram_conserve_pct: float = 80.0
    ram_stop_pct: float = 90.0


@dataclass(frozen=True)
class Decision:
    action: str                   # REUSE | COALESCED | HEADLESS | QUEUED | OPEN
    surface_id: str = ""
    reason: str = ""
    intent: str = ""
    coalesced: int = 0


def intent_key(provider, workkey, prompt, kind="task"):
    """Same provider + workkey + prompt (whitespace/case-insensitive) + kind = same intent."""
    norm = re.sub(r"\s+", " ", prompt or "").strip().lower()
    return hashlib.sha256(f"{kind}|{provider}|{workkey}|{norm}".encode()).hexdigest()[:20]


def pressure_level(budget, visible_count, ram_used_pct=None):
    """Admission/backpressure level. Unknown RAM (None) is not guessed; counts still apply."""
    if visible_count >= budget.hard or (ram_used_pct is not None and ram_used_pct >= budget.ram_stop_pct):
        return NO_NEW_VISIBLE
    if visible_count >= budget.soft or (ram_used_pct is not None and ram_used_pct >= budget.ram_conserve_pct):
        return CONSERVE
    return NORMAL


def _default_identity(surface):
    if not surface.pid:
        return False
    from courier_runtime.ownership import OwnedProcess, is_same_process
    return is_same_process(OwnedProcess(surface.pid, surface.create_time, surface.workkey, surface.owner, 0.0))


class SurfaceSupervisor:
    def __init__(self, path, host, os_name, owner="courier", budget=Budget(), identity=_default_identity,
                 clock=time.time):
        self.path, self.host, self.os, self.owner = Path(path), host, os_name, owner
        self.budget, self.identity, self.clock = budget, identity, clock
        self._load()

    # ---- persistence -------------------------------------------------------
    def _load(self):
        data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.surfaces = {k: Surface(**v) for k, v in data.get("surfaces", {}).items()}
        self.intents = data.get("intents", {})       # key -> {"surface_id"|"queued": ..., "count": n}
        self.queue = data.get("queue", [])           # [{"intent", "provider", "workkey", "visible"}]
        self.coalesced_total = data.get("coalesced_total", 0)
        self._seq = data.get("seq", 0)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"surfaces": {k: dataclasses.asdict(v) for k, v in self.surfaces.items()},
                "intents": self.intents, "queue": self.queue, "coalesced_total": self.coalesced_total,
                "seq": self._seq}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".surfaces.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True)
        os.replace(tmp, self.path)

    # ---- counts ------------------------------------------------------------
    def _visible_live(self):
        return [s for s in self.surfaces.values() if s.visible and s.state not in DEAD]

    def level(self, ram_used_pct=None):
        return pressure_level(self.budget, len(self._visible_live()), ram_used_pct)

    # ---- admission ---------------------------------------------------------
    def admit(self, provider, workkey, prompt, kind="task", needs_visible=True, allow_headless=True,
              ram_used_pct=None):
        key = intent_key(provider, workkey, prompt, kind)
        known = self.intents.get(key)
        if known and (known.get("queued") or self._alive(known.get("surface_id"))):
            known["count"] = known.get("count", 1) + 1
            self.coalesced_total += 1
            self._save()
            return Decision("COALESCED", known.get("surface_id", ""), "same intent already running or queued",
                            key, known["count"] - 1)
        running = next((s for s in self.surfaces.values() if s.workkey == workkey and s.state in BUSY), None)
        if running:
            self.intents[key] = {"surface_id": running.surface_id, "count": 1}
            self.coalesced_total += 1
            self._save()
            return Decision("COALESCED", running.surface_id, "workkey already running", key, 0)
        idle = next((s for s in self.surfaces.values() if s.provider == provider and s.owner == self.owner
                     and s.state in REUSABLE and s.visible == needs_visible and self.identity(s)), None)
        if idle:
            idle.state, idle.workkey, idle.last_activity = WORKING, workkey, self.clock()
            self.intents[key] = {"surface_id": idle.surface_id, "count": 1}
            self._save()
            return Decision("REUSE", idle.surface_id, "healthy owned idle surface", key)
        level = self.level(ram_used_pct)
        if not needs_visible or (level != NORMAL and allow_headless):
            sid = self._register(provider, workkey, visible=False)
            self.intents[key] = {"surface_id": sid, "count": 1}
            self._save()
            return Decision("HEADLESS", sid, "no window needed" if not needs_visible else level, key)
        if level == NO_NEW_VISIBLE:
            self.queue.append({"intent": key, "provider": provider, "workkey": workkey, "visible": True})
            self.intents[key] = {"queued": True, "count": 1}
            self._save()
            return Decision("QUEUED", "", SURFACE_BUDGET_EXHAUSTED, key)
        # NORMAL, or CONSERVE for work that genuinely needs a window (headless not allowed)
        sid = self._register(provider, workkey, visible=True)
        self.intents[key] = {"surface_id": sid, "count": 1}
        self._save()
        return Decision("OPEN", sid, "below budget" if level == NORMAL else "window required; below hard limit", key)

    def _register(self, provider, workkey, visible):
        self._seq += 1
        sid = f"{self.host}-s{self._seq}"
        now = self.clock()
        self.surfaces[sid] = Surface(sid, provider, self.host, self.os, self.owner, workkey, visible,
                                     created_at=now, last_activity=now)
        return sid

    def _alive(self, sid):
        s = self.surfaces.get(sid or "")
        return bool(s) and s.state not in DEAD

    # ---- lifecycle ---------------------------------------------------------
    def attach(self, surface_id, pid, create_time, parent_pid=0, window_id=""):
        s = self.surfaces[surface_id]
        s.pid, s.create_time, s.parent_pid, s.window_id, s.state = pid, create_time, parent_pid, window_id, WORKING
        self._save()

    def set_state(self, surface_id, state, checkpoint=None, unsaved=None):
        s = self.surfaces[surface_id]
        s.state, s.last_activity = state, self.clock()
        if checkpoint is not None:
            s.checkpoint = checkpoint
        if unsaved is not None:
            s.unsaved = unsaved
        self._save()

    def finish(self, surface_id, checkpoint):
        """Work done and checkpointed: the surface becomes IDLE_READY and the next
        queued intent for this provider is handed to it (no new window)."""
        s = self.surfaces[surface_id]
        s.state, s.checkpoint, s.unsaved, s.last_activity = IDLE_READY, checkpoint, False, self.clock()
        for key, meta in list(self.intents.items()):
            if meta.get("surface_id") == surface_id:
                del self.intents[key]
        nxt = next((q for q in self.queue if q["provider"] == s.provider and q["visible"] == s.visible), None)
        if nxt:
            self.queue.remove(nxt)
            s.state, s.workkey = WORKING, nxt["workkey"]
            self.intents[nxt["intent"]] = {"surface_id": surface_id, "count": 1}
            self._save()
            return Decision("REUSE", surface_id, "queued work moved into the freed surface", nxt["intent"])
        self._save()
        return None

    # ---- ownership-safe cleanup -------------------------------------------
    def why_not_closable(self, surface_id):
        s = self.surfaces[surface_id]
        reasons = []
        if s.owner != self.owner:
            reasons.append("not owned by Courier")
        if not self.identity(s):
            reasons.append("pid/start-time identity does not match")
        if s.state in BUSY:
            reasons.append(f"active work ({s.state})")
        if not s.checkpoint:
            reasons.append("no durable checkpoint")
        if s.unsaved:
            reasons.append("unsaved work")
        return reasons

    def reclaim(self, surface_id, closer):
        """Close one surface through `closer(surface)` only if every safety check passes."""
        reasons = self.why_not_closable(surface_id)
        if reasons:
            return {"surface_id": surface_id, "closed": False, "reasons": reasons}
        result = closer(self.surfaces[surface_id])
        self.surfaces[surface_id].state = COMPLETED
        self._save()
        return {"surface_id": surface_id, "closed": True, "closer": result}

    def reclaim_idle(self, closer):
        """Collapse completed/idle owned surfaces; anything unsafe stays (PARK, never kill)."""
        return [self.reclaim(sid, closer) for sid, s in list(self.surfaces.items())
                if s.state in REUSABLE and s.visible]

    # ---- restart -----------------------------------------------------------
    def reconcile(self):
        """After a Courier restart: classify every persisted surface against reality.
        Nothing is respawned; queued intents stay queued."""
        result = {}
        for sid, s in self.surfaces.items():
            if s.state in DEAD:
                result[sid] = "COMPLETED"
            elif s.owner != self.owner:
                result[sid] = "ORPHANED"
            elif not self.identity(s):
                s.state = TERMINAL_HOST_FAILED
                result[sid] = "STALE"
            elif s.state in REUSABLE:
                result[sid] = "REUSABLE"
            else:
                result[sid] = "STILL_ALIVE"
        for key, meta in list(self.intents.items()):
            if meta.get("surface_id") and not self._alive(meta["surface_id"]):
                del self.intents[key]          # its surface is gone: the next request may run it again
        self._save()
        return result

    def status(self, ram_used_pct=None):
        live = [s for s in self.surfaces.values() if s.state not in DEAD]
        return {"workers": len(live), "visible_windows": len([s for s in live if s.visible]),
                "queued": len(self.queue), "surface_mode": self.level(ram_used_pct),
                "duplicate_requests_coalesced": self.coalesced_total}


# ---- platform adapters: same logical contract, different OS mechanics --------
class PlatformAdapter:
    """Closes exactly one owned surface by identity. Never by name."""
    name = "generic"
    mechanism = "pid+create_time via courier_runtime.ownership.terminate_owned"

    def close(self, surface):
        from courier_runtime.ownership import OwnedProcess, terminate_owned
        return terminate_owned(OwnedProcess(surface.pid, surface.create_time, surface.workkey, surface.owner, 0.0))


class MacAdapter(PlatformAdapter):
    name = "darwin"
    mechanism = "pid+create_time (owned process tree); Terminal/Electron windows closed only via their owned process"


class WindowsAdapter(PlatformAdapter):
    name = "win32"
    mechanism = "pid+create_time (owned process tree); Job Object grouping planned; never by image name"


def adapter_for(platform_name):
    return {"darwin": MacAdapter, "win32": WindowsAdapter}.get(platform_name, PlatformAdapter)()
