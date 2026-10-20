"""Provider continuity (Kirby): the user is not the Continue button.

One durable, host-local supervisor that keeps a campaign moving across
provider turns, blocked items, stalls and context saturation:

  TURN_ENDED != CAMPAIGN_COMPLETED   a provider going idle after one task is a
                                     boundary; Kirby reconciles and wakes the
                                     same session for the next workkey
  BLOCKED_WORKKEY != BLOCKED_SESSION a blocked workkey is parked; the session
                                     continues with another executable one
  PROMPT != NEW TASK                 per session at most ONE pending wake;
                                     duplicate wakes are coalesced
  ONE WRITER PER WORKKEY             claims carry a fencing token; a stale
                                     owner (rotated/recovered) is rejected
  ROTATION / RECOVERY                checkpoint -> release -> exactly ONE
                                     successor in the same slot -> resume
                                     from the checkpoint, never from zero
  WATCHDOG                           event-driven first; a 30-60 s health tick
                                     is the fallback; a structured Critical
                                     Snapshot every ~15 min is evidence only

Pure logic: process identity, termination and session start are injected,
so the same contract runs on Mac, Windows and in tests. Termination is only
ever by proven ownership (courier_runtime.ownership), never by name.
"""
import dataclasses
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# workkey states
OPEN, CLAIMED, DONE, BLOCKED, FAILED_FINAL = "OPEN", "CLAIMED", "DONE", "BLOCKED", "FAILED_FINAL"
# session states
WORKING, IDLE, WAKE_PENDING, WAITING_FOR_USER = "WORKING", "IDLE", "WAKE_PENDING", "WAITING_FOR_USER"
RECOVERING, RETIRED = "RECOVERING", "RETIRED"
LIVE = {WORKING, IDLE, WAKE_PENDING, WAITING_FOR_USER, RECOVERING}

# Explicit provider failure signals that mean "this session's context/backlog is
# saturated". No fixed prompt-count limit is assumed.
SATURATION_SIGNALS = ("hard_threshold_failed", "compaction cannot replace external history",
                      "turn-submit backlog full", "context window exceeded", "context_length_exceeded")

# activity class -> (heartbeat grace s, useful-progress window s). Quiet != hung.
ACTIVITY = {
    "interactive": (90, 900),
    "build": (180, 3600),
    "long_quiet": (600, 4 * 3600),
}
SNAPSHOT_EVERY_S = 15 * 60
HEALTH_TICK_S = 45


@dataclass
class Workkey:
    key: str
    state: str = OPEN
    owner: str = ""                # session_id of the single writer
    token: int = 0                 # fencing token, bumps on every claim
    checkpoint: str = ""
    blocked_reason: str = ""
    priority: int = 100
    depends_on: list = dataclasses.field(default_factory=list)
    effect_class: str = "idempotent"
    result_id: str = ""


@dataclass
class Session:
    slot: str
    session_id: str
    provider: str
    host: str
    state: str = IDLE
    pid: int = 0
    create_time: float = 0.0
    workkey: str = ""
    token: int = 0
    generation: int = 1
    activity: str = "interactive"
    last_heartbeat: float = 0.0
    last_progress: float = 0.0
    accepting: bool = True
    successor: str = ""
    recovering_since: float = 0.0
    delivered_workkey: str = ""
    delivery_enforced: bool = False
    lease_until: float = 0.0


def saturation_signal(provider_text="", context_used_pct=None, threshold_pct=90.0):
    """Rotation trigger: real context telemetry if available, else explicit failure text."""
    if context_used_pct is not None and context_used_pct >= threshold_pct:
        return f"context pressure {context_used_pct:.0f}%"
    low = (provider_text or "").lower()
    return next((s for s in SATURATION_SIGNALS if s in low), None)


class Kirby:
    def __init__(self, path, host, max_slots=12, identity=lambda s: True, terminate=lambda s: {"result": "NONE"},
                 start_session=None, clock=time.time, verifier=None, dispatcher=None, lease_seconds=0.0):
        self.path, self.host, self.max_slots = Path(path), host, max_slots
        self.identity, self.terminate, self.clock = identity, terminate, clock
        self.start_session = start_session or (lambda slot, gen: (f"{slot}-g{gen}", 0, 0.0))
        self.verifier = verifier
        self.dispatcher = dispatcher
        self.lease_seconds = float(lease_seconds or 0.0)
        self._load()

    # ---- persistence --------------------------------------------------------
    def _load(self):
        d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.workkeys = {k: Workkey(**v) for k, v in d.get("workkeys", {}).items()}
        self.sessions = {k: Session(**v) for k, v in d.get("sessions", {}).items()}
        self.counters = d.get("counters", {"coalesced": 0, "manual_continue": 0, "auto_wakes": 0,
                                           "rotations": 0, "recoveries": 0, "completions": 0})
        self.last_snapshot = d.get("last_snapshot", 0.0)
        max_tok = max([0] + [w.token for w in self.workkeys.values()] + [s.token for s in self.sessions.values()])
        self.token_seq = max(int(d.get("token_seq", 0)), max_tok)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        d = {"workkeys": {k: dataclasses.asdict(v) for k, v in self.workkeys.items()},
             "sessions": {k: dataclasses.asdict(v) for k, v in self.sessions.items()},
             "counters": self.counters, "last_snapshot": self.last_snapshot,
             "token_seq": getattr(self, "token_seq", 0)}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".kirby.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f, sort_keys=True)
        os.replace(tmp, self.path)

    def _log(self, name, record):
        with open(self.path.parent / name, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    # ---- campaign + slots ---------------------------------------------------
    def add_workkeys(self, keys, priority=100, depends_on=None, effect_class="idempotent"):
        deps = list(depends_on or [])
        for k in keys:
            if isinstance(k, dict):
                key = k["key"]
                self.workkeys.setdefault(
                    key,
                    Workkey(
                        key,
                        priority=k.get("priority", priority),
                        depends_on=list(k.get("depends_on", deps)),
                        effect_class=k.get("effect_class", effect_class),
                    ),
                )
            else:
                self.workkeys.setdefault(
                    k,
                    Workkey(k, priority=priority, depends_on=list(deps), effect_class=effect_class),
                )
        self._save()

    def open_slot(self, slot, provider, activity="interactive"):
        """A logical session slot. Slots are distinct; the pool never exceeds max_slots."""
        if slot in self.sessions and self.sessions[slot].state in LIVE:
            return self.sessions[slot]
        if len([s for s in self.sessions.values() if s.state in LIVE]) >= self.max_slots:
            raise RuntimeError(f"pool full ({self.max_slots} slots)")
        # Generations are monotonic per slot: a reopened/archived slot must never
        # reuse a retired session_id, or owner-equality checks could misattribute
        # a stale owner to the new physical session.
        gen = self.sessions[slot].generation + 1 if slot in self.sessions else 1
        sid, pid, ct = self.start_session(slot, gen)
        now = self.clock()
        self.sessions[slot] = Session(slot, sid, provider, self.host, IDLE, pid, ct, generation=gen,
                                      activity=activity, last_heartbeat=now, last_progress=now)
        self._save()
        return self.sessions[slot]

    def reconnect_slot(self, slot, provider=None, activity=None):
        """Reopen a retired/disconnected slot or wake an idle reconnected slot."""
        existing = self.sessions.get(slot)
        prov = provider or (existing.provider if existing else "antigravity")
        act = activity or (existing.activity if existing else "interactive")
        if existing is not None and existing.state in LIVE and not self.identity(existing):
            if existing.workkey:
                self.recover(slot, "worker reconnected after disconnect")
                return self.sessions[slot]
            existing.state = RETIRED
            self._save()
        s = self.open_slot(slot, prov, activity=act)
        if self.has_ready_work() or (s.workkey and self.workkeys[s.workkey].owner == s.session_id):
            self.wake(slot)
        return self.sessions[slot]

    def _is_ready(self, w):
        if w.state != OPEN:
            return False
        return all(self.workkeys.get(dep) is not None and self.workkeys[dep].state == DONE for dep in w.depends_on)

    def ready_workkeys(self):
        ready = [w for w in self.workkeys.values() if self._is_ready(w)]
        ready.sort(key=lambda w: (w.priority, w.key))
        return ready

    def has_ready_work(self):
        return bool(self.ready_workkeys())

    def _next_workkey(self):
        ready = self.ready_workkeys()
        return ready[0] if ready else None

    def _claim(self, s, w):
        self.token_seq = getattr(self, "token_seq", 0) + 1
        w.state, w.owner, w.token = CLAIMED, s.session_id, self.token_seq
        s.workkey, s.token = w.key, w.token
        s.delivered_workkey = ""

    # ---- event-driven continuation -----------------------------------------
    def wake(self, slot, manual=False):
        """Any continuation intent (provider idle, human 'continue', timer, repeated prompt).
        At most one pending wake per session; everything else is coalesced."""
        s = self.sessions[slot]
        if manual:
            self.counters["manual_continue"] += 1
        if s.state == RETIRED:
            s = self.open_slot(slot, s.provider, activity=s.activity)
        if s.state in (WAKE_PENDING, WORKING, RECOVERING) or not s.accepting:
            self.counters["coalesced"] += 1
            self._save()
            return "COALESCED"
        if s.workkey and self.workkeys[s.workkey].owner == s.session_id:
            s.state = WAKE_PENDING                              # resume own claimed work
        else:
            w = self._next_workkey()
            if w is None:
                has_blocked = any(x.state == BLOCKED for x in self.workkeys.values())
                has_unready_open = any(x.state == OPEN and not self._is_ready(x) for x in self.workkeys.values())
                s.state = WAITING_FOR_USER if (has_blocked or has_unready_open) else IDLE
                self._save()
                return s.state
            self._claim(s, w)
            s.state = WAKE_PENDING
        self.counters["auto_wakes"] += 0 if manual else 1
        self._save()
        return WAKE_PENDING

    def deliver(self, slot):
        """The single pending wake is sent to the provider (one turn). Returns the workkey."""
        s = self.sessions[slot]
        if s.state != WAKE_PENDING:
            return None
        now = self.clock()
        s.state, s.last_heartbeat, s.last_progress = WORKING, now, now
        s.delivered_workkey = s.workkey
        s.delivery_enforced = True
        if self.lease_seconds > 0:
            s.lease_until = now + self.lease_seconds
        self._save()
        return s.workkey

    def on_turn_end(self, slot, outcome, token, checkpoint="", reason="", workkey=None, result_id=""):
        """Provider returned idle. outcome: DONE | BLOCKED | STILL_OPEN | FAILED_FINAL.
        The stale-token check is the duplicate-writer guard."""
        s = self.sessions[slot]
        if workkey:
            target = self.workkeys.get(workkey)
            if target is not None and target.state == DONE:
                return "DUPLICATE_IGNORED"
            if s.workkey != workkey:
                return "REJECTED_STALE_WRITER"
        if result_id and any(x.result_id == result_id and x.state == DONE for x in self.workkeys.values()):
            return "DUPLICATE_IGNORED"
        w = self.workkeys.get(s.workkey)
        if w is None or w.owner != s.session_id or w.token != token:
            return "REJECTED_STALE_WRITER"
        if s.delivery_enforced and s.delivered_workkey != s.workkey:
            return "DUPLICATE_IGNORED"
        w.checkpoint = checkpoint or w.checkpoint
        if outcome == "DONE":
            if self.verifier is not None and not self.verifier(w.key, w.checkpoint, s):
                w.state, w.owner, w.blocked_reason = BLOCKED, "", reason or "verification_failed"
                s.workkey, s.delivered_workkey, s.lease_until = "", "", 0.0
                s.state = IDLE
                self._save()
                return self.wake(slot)
            w.state, w.owner = DONE, ""
            if result_id:
                w.result_id = result_id
            s.workkey, s.delivered_workkey, s.lease_until = "", "", 0.0
            self.counters["completions"] += 1
            self._log("receipts.jsonl", {"workkey": w.key, "outcome": DONE, "session": s.session_id,
                                         "checkpoint": w.checkpoint, "at": self.clock()})
        elif outcome == "BLOCKED":
            w.state, w.owner, w.blocked_reason = BLOCKED, "", reason
            s.workkey, s.delivered_workkey, s.lease_until = "", "", 0.0
        elif outcome == "FAILED_FINAL":
            w.state, w.owner = FAILED_FINAL, ""
            s.workkey, s.delivered_workkey, s.lease_until = "", "", 0.0
        s.state = IDLE
        self._save()
        return self.wake(slot)                                  # TURN_ENDED != CAMPAIGN_COMPLETED

    def heartbeat(self, slot, progress=False, checkpoint=None):
        s = self.sessions[slot]
        now = self.clock()
        s.last_heartbeat = now
        if progress:
            s.last_progress = now
        if self.lease_seconds > 0 and s.state == WORKING:
            s.lease_until = now + self.lease_seconds
        if checkpoint is not None and s.workkey:
            self.workkeys[s.workkey].checkpoint = checkpoint
        self._save()

    # ---- watchdog -----------------------------------------------------------
    def health(self, slot):
        """Multi-signal classification. One weak signal = investigate; several = recover."""
        s = self.sessions[slot]
        if s.state != WORKING:
            return "OK", []
        hb_grace, progress_window = ACTIVITY.get(s.activity, ACTIVITY["interactive"])
        now = self.clock()
        signals = []
        if s.lease_until > 0 and now >= s.lease_until:
            signals.append("lease_expired")
        if now - s.last_heartbeat > hb_grace:
            signals.append("heartbeat_missed")
        if now - s.last_progress > progress_window:
            signals.append("no_useful_progress")
        if s.pid and not self.identity(s):
            signals.append("executor_gone")
        if not signals:
            return "OK", []
        if len(signals) == 1 and signals not in (["executor_gone"], ["lease_expired"]):
            return "INVESTIGATE", signals
        return "RECOVER", signals

    def tick(self):
        """Fallback watchdog (~every 30-60 s) + Critical Snapshot cadence (~15 min)."""
        actions = {}
        for slot in list(self.sessions):
            verdict, signals = self.health(slot)
            if verdict == "RECOVER":
                actions[slot] = self.recover(slot, "stall: " + ",".join(signals))
            elif verdict == "INVESTIGATE":
                actions[slot] = {"slot": slot, "action": "INVESTIGATE", "signals": signals}
        if self.clock() - self.last_snapshot >= SNAPSHOT_EVERY_S:
            self.critical_snapshot()
        return actions

    def critical_snapshot(self, sha=""):
        """Structured evidence. It is never read back as runtime truth."""
        snap = {"at": self.clock(), "host": self.host, "sha": sha, "evidence_only": True, "sessions": [
            {"slot": s.slot, "provider": s.provider, "session_id": s.session_id, "pid": s.pid,
             "create_time": s.create_time, "state": s.state, "workkey": s.workkey,
             "checkpoint": self.workkeys[s.workkey].checkpoint if s.workkey in self.workkeys else "",
             "last_progress": s.last_progress, "writer_token": s.token} for s in self.sessions.values()]}
        self.last_snapshot = snap["at"]
        self._log("snapshots.jsonl", snap)
        self._save()
        return snap

    # ---- rotation / recovery: exactly one successor -------------------------
    def _replace(self, slot, kind, reason, checkpoint=None):
        old = self.sessions[slot]
        if old.state == RETIRED or old.successor:
            return {"slot": slot, "action": "ALREADY_REPLACED", "successor": old.successor}
        old.accepting = False
        w = self.workkeys.get(old.workkey)
        if w is not None and checkpoint is not None:
            w.checkpoint = checkpoint
        cleanup = "NOT_OWNED_OR_GONE"
        if old.pid and self.identity(old):
            cleanup = self.terminate(old).get("result", "?")      # proven-owned tree only
        gen = old.generation + 1
        sid, pid, ct = self.start_session(slot, gen)
        now = self.clock()
        new = Session(slot, sid, old.provider, self.host, IDLE, pid, ct, generation=gen, activity=old.activity,
                      last_heartbeat=now, last_progress=now, recovering_since=0.0)
        quarantined = False
        if w is not None and w.owner == old.session_id:
            if kind == "RECOVER" and w.effect_class == "non_idempotent":
                self.token_seq = getattr(self, "token_seq", 0) + 1
                w.state, w.owner, w.token = BLOCKED, "", self.token_seq
                w.blocked_reason = f"unknown external effect ({reason})"
                quarantined = True
            else:
                self._claim(new, w)                              # same workkey, new fencing token
                new.state = WAKE_PENDING                         # resumes from w.checkpoint
        old.state, old.successor = RETIRED, sid
        self.sessions[slot] = new
        if quarantined:
            self.wake(slot)
        self._log("retired.jsonl", dataclasses.asdict(old))
        self.counters["rotations" if kind == "ROTATE" else "recoveries"] += 1
        receipt = {"incident": f"{kind}-{slot}-g{gen}", "slot": slot, "kind": kind, "reason": reason,
                   "old_session": old.session_id, "new_session": sid, "workkey": new.workkey,
                   "quarantined_workkey": w.key if quarantined else "",
                   "checkpoint": w.checkpoint if w else "", "cleanup": cleanup,
                   "foreign_process_touched": False, "duplicate_execution": False, "at": now}
        self._log("recovery_receipts.jsonl", receipt)
        self._save()
        return receipt

    def rotate(self, slot, reason, checkpoint=None):
        return self._replace(slot, "ROTATE", reason, checkpoint)

    def recover(self, slot, reason):
        return self._replace(slot, "RECOVER", reason)

    def on_provider_output(self, slot, text="", context_used_pct=None, checkpoint=None):
        """Feed provider status lines/telemetry; rotates exactly once on saturation."""
        sig = saturation_signal(text, context_used_pct)
        return self.rotate(slot, sig, checkpoint) if sig else None

    # ---- restart + user view ------------------------------------------------
    def reconcile_after_restart(self):
        """Every live session becomes exactly one of RESUMED / RECOVERED / ARCHIVED_STALE."""
        result = {}
        for slot, s in list(self.sessions.items()):
            if s.state not in LIVE:
                continue
            if not s.pid or self.identity(s):
                result[slot] = "RESUMED"
            elif s.workkey:
                self.recover(slot, "executor lost across restart")
                result[slot] = "RECOVERED"
            else:
                s.state = RETIRED
                result[slot] = "ARCHIVED_STALE"
        self._save()
        return result

    def user_state(self):
        """What an ordinary user sees: WORKING / RECOVERING / NEEDS YOU / DONE."""
        live = [s for s in self.sessions.values() if s.state in LIVE]
        if all(w.state in (DONE, FAILED_FINAL) for w in self.workkeys.values()) and self.workkeys:
            return "DONE"
        if any(s.state in (WORKING, WAKE_PENDING) for s in live):
            return "WORKING"
        if any(w.state == BLOCKED for w in self.workkeys.values()) and not any(
                w.state == OPEN for w in self.workkeys.values()):
            return "NEEDS YOU"
        return "WORKING" if live else "NEEDS YOU"


def concurrency_advice(windows):
    """Power-pool experiment: windows = [{"slots", "completions_per_h", "errors", "ram_pct"}].
    Recommend the smallest slot count with the best verified throughput; scale down
    when more slots stop helping or the host is under pressure."""
    healthy = [w for w in windows if w.get("ram_pct", 0) < 85 and w.get("errors", 0) <= 2]
    if not healthy:
        smallest = min(windows, key=lambda w: w["slots"])
        return {"slots": max(1, smallest["slots"] // 2), "why": "resource pressure or errors: scale down"}
    best = max(healthy, key=lambda w: (w["completions_per_h"], -w["slots"]))
    return {"slots": best["slots"], "why": f"best verified throughput {best['completions_per_h']}/h"}
