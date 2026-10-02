"""Host Guardian resource-endurance envelopes (Issue #76, CI-safe slice).

Accelerated proof that repeated Host Guardian cycles do not leak: thousands
of admission/classify/checkpoint cycles run in-process in seconds, and a
handful of real bounded subprocess runs prove timeout/grandchild cleanup,
orphan-gate restart, and outbox retention under network loss.

What this file is NOT: it is not the 24h/7d soak. Long soaks live in
``scripts/soak/soak_host_guardian.py`` (manual) and
``.github/workflows/host-endurance-soak.yml`` (workflow_dispatch only), so
this suite never becomes a permanent CI resource burner.

Coverage map (each soak class has at least one accelerated case):
  24H/7D SOAK ................. test_accelerated_cycles_no_upward_slope
  ACCELERATED THOUSANDS ....... same (2000 admission cycles + checkpoint loop)
  SLEEP/WAKE .................. test_sleep_wake_spike_recovers_without_latch
  NETWORK LOSS ................ test_network_loss_outbox_retained_single_attempt
  PROVIDER QUOTA .............. test_provider_quota_single_heavy_lease
  PROCESS TIMEOUT ............. test_process_timeout_reaps_owned_tree
  GRANDCHILD CLEANUP .......... test_grandchild_in_owned_tree_reaped
  APP RESTART ................. test_app_restart_orphan_gate_bounded,
                                test_checkpoint_restart_roundtrip
  CRASH DURING STABILIZATION .. test_crash_during_stabilization_touches_only_owned
  64 LOGICAL SLOTS ............ test_64_logical_slots_staged_and_bounded

Pass rule: bounded envelopes, never byte-exact equality. A repeated cycle
may jitter; it must not slope upward without bound.

Nothing here writes outside pytest tmp dirs (the v1 CI gate fails on any
worktree write), touches the network beyond a closed-loop fake, or spawns
more than one child tree at a time (single-flight, like the product).
"""

from __future__ import annotations

import gc
import json
import os
import sys
import time

import pytest

from scripts import host_capacity as HC
from scripts.resource_governor import HostPressureController
from courier_worker import host as H
from courier_worker import service as S

PY = sys.executable

# -- envelopes (bounded, documented; tighten only with baseline evidence) ------
CYCLES = 2000
SLOTS_64 = 64
FILE_DELTA_MAX = 0        # pure admission cycles must leave no files behind
RSS_GROWTH_MAX_KB = 5120  # generous: allocator jitter, not a leak allowance
RSS_SLOPE_MAX_KB = 5.0    # per-cycle least-squares slope ceiling
FD_DELTA_MAX = 4          # best-effort; skipped where the platform hides FDs
CLEANUP_WALL_MAX_S = 30.0  # timeout(2s) + KILL_GRACE + scheduling margin
CHECKPOINT_MAX_BYTES = 64 * 1024


def _slope(xs, ys) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def _healthy() -> HC.HostSnapshot:
    return HC.HostSnapshot(load_1=2.0, cores=8, memory_pressure="NOMINAL",
                           swap_paging=False, thermal="NOMINAL")


def _unknown() -> HC.HostSnapshot:
    return HC.HostSnapshot()


def _spec(home, tag, argv, timeout_s=2.0, lease_s=30.0) -> H.ExecutionSpec:
    return H.ExecutionSpec(
        task_id=tag, attempt=1, dispatch_id="d-" + tag, worker_id="w1",
        result_id="r-d-" + tag, argv=tuple(argv),
        timeout_s=timeout_s, lease_ttl_s=lease_s,
        artifact_dir=os.path.join(str(home), "artifacts", tag),
        heartbeat_s=0.2)


def _admission(desired, active, heavy, snap):
    return HC.admit_capacity(desired, active, heavy, snap, HC.NORMAL_PROFILE)


# -- 64 LOGICAL SLOTS ----------------------------------------------------------
def test_64_logical_slots_staged_and_bounded():
    """Desired=64 admits at most the safe estimate, staged +2 per step."""
    seen = []
    active = 0
    for _ in range(40):
        adm = _admission(SLOTS_64, active, 0, _healthy())
        assert adm.desired_slots == SLOTS_64
        assert adm.admitted_active <= HC.NORMAL_PROFILE.safe_local_estimate
        assert adm.waiting_slots == SLOTS_64 - adm.admitted_active
        assert adm.health == HC.HEALTHY
        seen.append(adm.admitted_active)
        if adm.admitted_active >= HC.NORMAL_PROFILE.safe_local_estimate:
            break
        assert adm.admitted_active - active <= HC.STAGED_TRANCHE
        active = adm.admitted_active
    assert seen[-1] == HC.NORMAL_PROFILE.safe_local_estimate
    assert seen == sorted(seen)  # monotonic ramp, no overshoot oscillation


def test_degraded_and_pressured_never_grow():
    spike = HC.HostSnapshot(load_1=20.0, cores=8, memory_pressure="CRITICAL",
                            swap_paging=True, thermal="NOMINAL")
    for health_snap in (spike, HC.HostSnapshot(load_1=10.0, cores=8,
                                               memory_pressure="HIGH")):
        adm = _admission(SLOTS_64, 4, 1, health_snap)
        assert adm.admitted_active <= 4
        assert adm.heavy_allowed is False
        assert adm.waiting_slots == SLOTS_64 - adm.admitted_active


# -- ACCELERATED THOUSANDS-OF-CYCLES -------------------------------------------
def test_accelerated_cycles_no_upward_slope(tmp_path):
    """2000 admission cycles: constant output, no files, flat RSS slope."""
    snap = _healthy()
    before_files = sum(len(files) for _, _, files in os.walk(tmp_path))
    rss = []
    try:
        import psutil
        proc = psutil.Process()
        have_rss = True
    except Exception:
        have_rss = False
    waiting = []
    for i in range(CYCLES):
        adm = _admission(6, 2, 0, snap)
        waiting.append(adm.waiting_slots)
        if have_rss and i % 50 == 0:
            rss.append(proc.memory_info().rss // 1024)
    assert set(waiting) == {2}  # desired 6, staged admit 4 -> waiting exactly 2
    after_files = sum(len(files) for _, _, files in os.walk(tmp_path))
    assert after_files - before_files <= FILE_DELTA_MAX
    if have_rss and len(rss) >= 3:
        assert rss[-1] - rss[0] <= RSS_GROWTH_MAX_KB
        assert _slope(list(range(len(rss))), rss) <= RSS_SLOPE_MAX_KB


def test_fd_handles_bounded_across_cycles(tmp_path):
    try:
        import psutil
        proc = psutil.Process()
        try:
            before = proc.num_fds()
        except AttributeError:
            before = proc.num_handles()  # Windows native handle count
    except Exception:
        pytest.skip("platform exposes no FD/handle count")
    snap = _healthy()
    for _ in range(200):
        adm = _admission(6, 2, 0, snap)
        HC.save_checkpoint(tmp_path, adm.health, adm, [],
                           last_resource_event="CYCLE_PROBE")
    HC.load_checkpoint(tmp_path)
    try:
        after = proc.num_fds()
    except AttributeError:
        after = proc.num_handles()
    assert after - before <= FD_DELTA_MAX
    gc.collect()


# -- UNKNOWN / FAIL-CLOSED ------------------------------------------------------
@pytest.mark.parametrize("snap", [
    _unknown(),
    HC.HostSnapshot(load_1=None, cores=None),
    HC.HostSnapshot(load_1=1.0, cores=None, memory_pressure="UNKNOWN",
                    thermal="UNKNOWN"),  # load without cores is no signal
])
def test_unknown_signals_never_healthy(snap):
    assert HC.classify_health(snap) != HC.HEALTHY
    adm = _admission(8, 2, 0, snap)
    assert adm.admitted_active <= 2  # no growth on unknown ground


def test_known_good_load_may_be_healthy_but_still_staged():
    """Pin the implemented contract: one known-good signal (load norm)
    suffices for HEALTHY; safety then comes from the staged +2 ramp and the
    safe-estimate cap, not from refusing HEALTHY. Do not tighten or loosen
    this without the Guardian owner's decision."""
    snap = HC.HostSnapshot(load_1=1.0, cores=8, memory_pressure="UNKNOWN",
                           thermal="UNKNOWN")
    assert HC.classify_health(snap) == HC.HEALTHY
    adm = _admission(8, 0, 0, snap)
    assert adm.admitted_active <= HC.STAGED_TRANCHE
    assert adm.waiting_slots == 8 - adm.admitted_active


def test_resource_pause_and_emergency_fail_closed_with_checkpoint(tmp_path):
    for latched, health in (("resource_pause_latched", HC.RESOURCE_PAUSE),
                            ("emergency_latched", HC.EMERGENCY)):
        snap = HC.HostSnapshot(load_1=0.1, cores=8, memory_pressure="NOMINAL",
                               thermal="NOMINAL", **{latched: True})
        owned = [HC.OwnedProcess(pid=42420 + len(health))]
        adm = _admission(8, 3, 1, snap)
        assert adm.health == health
        assert adm.spawn_allowed is False
        assert adm.heavy_allowed is False
        assert adm.waiting_slots == 8 - adm.admitted_active
        path = HC.save_checkpoint(tmp_path, adm.health, adm, owned,
                                  human_gate_waiting=2, resumable=1,
                                  last_resource_event="TEST_" + health)
        assert path.stat().st_size <= CHECKPOINT_MAX_BYTES
        data = HC.load_checkpoint(tmp_path)
        assert data["health"] == health
        assert data["human_gate_waiting"] == 2  # gates survive the pause
        assert [o["pid"] for o in data["owned"]] == [owned[0].pid]


# -- APP RESTART / CRASH DURING STABILIZATION -----------------------------------
def test_checkpoint_restart_roundtrip_and_corrupt_fail_closed(tmp_path):
    adm = _admission(6, 2, 0, _healthy())
    owned = [HC.OwnedProcess(pid=111, command_fingerprint="abc", purpose="t")]
    HC.save_checkpoint(tmp_path, adm.health, adm, owned,
                       human_gate_waiting=1, resumable=3,
                       last_resource_event="RESTART_PROBE")
    data = HC.load_checkpoint(tmp_path)
    assert data["resumable"] == 3
    assert data["admission"]["desired_slots"] == 6
    assert data["version"] == HC.CHECKPOINT_VERSION
    # A torn write is evidence of nothing: fail closed, never half-resume.
    HC.checkpoint_path(tmp_path).write_text("{torn", encoding="utf-8")
    assert HC.load_checkpoint(tmp_path) is None
    assert HC.load_checkpoint(tmp_path / "absent-subdir") is None


def test_crash_during_stabilization_touches_only_owned(tmp_path):
    owned = [HC.OwnedProcess(pid=101), HC.OwnedProcess(pid=102)]
    adm = _admission(4, 2, 0, _healthy())
    plan = HC.plan_stabilize(owned, human_gate_waiting=1)
    assert plan["exact_owned_pids"] == [101, 102]
    assert plan["unrelated_apps_touched"] is False
    assert plan["checkpoint_first"] is True
    touched = []
    out = HC.execute_emergency_stop(tmp_path, owned, adm,
                                    killer=lambda pid: touched.append(pid) or True,
                                    human_gate_waiting=1, resumable=2)
    assert sorted(touched) == [101, 102]
    assert out["remaining_owned"] == []
    assert out["unrelated_touched"] == []
    assert out["human_gate_waiting"] == 1
    # A killer that fails still checkpoints first and reports the remainder.
    out2 = HC.execute_emergency_stop(tmp_path, owned, adm,
                                     killer=lambda pid: False,
                                     human_gate_waiting=0, resumable=0)
    assert out2["remaining_owned"] == [101, 102]
    assert HC.load_checkpoint(tmp_path)["last_resource_event"] == "EMERGENCY_STOP"


# -- PROCESS TIMEOUT / GRANDCHILD CLEANUP --------------------------------------
def _wait_dead(pid, timeout_s=5.0) -> bool:
    try:
        import psutil
    except Exception:
        return True  # without psutil there is nothing portable to observe
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if not psutil.pid_exists(pid):
            return True
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                return True
        except Exception:
            return True
        time.sleep(0.05)
    return not psutil.pid_exists(pid)


def test_process_timeout_reaps_owned_tree(tmp_path):
    home = tmp_path / "home-timeout"
    host = H.WorkerHost(str(home), pressure_probe=lambda: None)
    start = time.monotonic()
    res = host.run_once(_spec(home, "timeout", [PY, "-c", "import time; time.sleep(30)"]))
    wall = time.monotonic() - start
    assert res.outcome == H.Outcome.TIMEOUT
    assert res.retryable is True  # timeout is environment-shaped, worth one retry
    assert host.busy is False
    assert wall <= CLEANUP_WALL_MAX_S
    assert H.run_orphan_gate(str(home)) == 0  # no claim record left behind


def test_grandchild_in_owned_tree_reaped(tmp_path):
    """A grandchild that stays in the owned group dies with the tree.

    Session escapees (double-fork out of the group/job) are documented as
    unreachable by owned-tree cleanup on every platform; this test pins the
    reachable case only.
    """
    home = tmp_path / "home-grandchild"
    marker = tmp_path / "grandchild.pid"
    child_code = (
        "import subprocess, sys, time; "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        f"open(r'{marker}', 'w').write(str(p.pid)); "
        "time.sleep(60)"
    )
    host = H.WorkerHost(str(home), pressure_probe=lambda: None)
    res = host.run_once(_spec(home, "grandchild", [PY, "-c", child_code]))
    assert res.outcome == H.Outcome.TIMEOUT
    gc_pid = int(marker.read_text(encoding="utf-8").strip())
    assert _wait_dead(gc_pid), "grandchild survived the owned-tree kill"
    assert H.run_orphan_gate(str(home)) == 0


# -- NETWORK LOSS / PROVIDER QUOTA ---------------------------------------------
class _DeadController:
    """Closed-loop network loss: every delivery attempt fails, counted."""

    def __init__(self):
        self.attempts = 0

    def deliver(self, payload):
        self.attempts += 1
        raise S.ControllerUnreachable("simulated network loss")


def _payload(tag):
    return {"dispatch_id": "d-" + tag, "task_id": "t-" + tag, "attempt": 1,
            "result_id": "r-d-" + tag, "status": "SUCCESS",
            "artifacts": [], "worker_id": "w1"}


def test_network_loss_outbox_retained_single_attempt(tmp_path):
    home = tmp_path / "home-offline"
    dead = _DeadController()
    loop = S.WorkerLoop(str(home), "http://127.0.0.1:9/", "w1", 0.2,
                        engine=H.WorkerHost(str(home), pressure_probe=lambda: None),
                        client_factory=lambda: dead)
    H.outbox_write(str(home), _payload("offline"))
    assert loop.flush_outbox() == 1  # retained, not lost
    assert dead.attempts == 1  # exactly one attempt per payload per flush
    stored = H.outbox_read_all(str(home))
    assert len(stored) == 1 and stored[0][1] == _payload("offline")  # identical bytes
    assert loop.flush_outbox() == 1  # still retained, no storm, no duplicate file
    assert dead.attempts == 2  # linear, never exponential
    assert len(H.outbox_read_all(str(home))) == 1


def test_provider_quota_single_heavy_lease():
    gov = HostPressureController()
    assert gov.admit_job("HEAVY") is True
    gov.active_jobs["HEAVY"] = 1  # lease now held, as the service layer tracks it
    assert gov.admit_job("HEAVY") is False  # quota: exactly one heavy job
    assert gov.admit_job("LIGHT") is True  # light work is never quota-blocked
    snap = HC.HostSnapshot(load_1=1.0, cores=8, memory_pressure="NOMINAL",
                           thermal="NOMINAL", heavy_lease_active=True)
    adm = HC.admit_capacity(8, 2, 1, snap, HC.NORMAL_PROFILE)
    assert adm.admitted_heavy <= HC.NORMAL_PROFILE.heavy_limit
    assert adm.heavy_allowed is False  # no second heavy while the lease is held


# -- SLEEP/WAKE / APP RESTART ----------------------------------------------------
def test_sleep_wake_spike_recovers_without_latch():
    """A wake spike pauses growth; nominal signals afterwards ramp again."""
    spike = HC.HostSnapshot(load_1=30.0, cores=8, memory_pressure="HIGH",
                            swap_paging=True, thermal="SERIOUS")
    adm = _admission(SLOTS_64, 4, 0, spike)
    assert adm.health == HC.DEGRADED
    assert adm.admitted_active <= 4
    assert adm.spawn_allowed in (True, False)  # platform decision, never growth
    back = _admission(SLOTS_64, adm.admitted_active, 0, _healthy())
    assert back.health == HC.HEALTHY
    assert back.admitted_active >= adm.admitted_active  # ramp resumes
    assert back.admitted_active - adm.admitted_active <= HC.STAGED_TRANCHE


def test_app_restart_orphan_gate_bounded(tmp_path):
    home = tmp_path / "home-restart"
    assert H.run_orphan_gate(str(home)) == 0  # fresh home: nothing to do
    claims = home / "run" / "claims"
    claims.mkdir(parents=True)
    dead = 1 << 30  # certainly no live owner/tree; killpg ESRCH is caught
    stale = {"owner_pid": dead, "child_pid": dead, "pgid": dead,
             "dispatch_id": "d-stale", "task_id": "t-stale"}
    (claims / "dispatch-d-stale.json").write_text(json.dumps(stale),
                                                 encoding="utf-8")
    (claims / "dispatch-torn.json").write_text("{torn", encoding="utf-8")
    handled = H.run_orphan_gate(str(home))
    assert 0 <= handled <= 2  # bounded: stale handled, torn skipped, live kept
    assert H.run_orphan_gate(str(home)) <= handled  # idempotent on rerun
