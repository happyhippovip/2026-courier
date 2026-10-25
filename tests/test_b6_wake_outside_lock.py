"""GOAL-06: a wake callback must run after the campaign lock is released."""
import fcntl
import hashlib
import json
import os
from pathlib import Path

from courier_core.controller import Controller
from courier_core.verification import Verdict
from courier_runtime.continuity import CLAIMED, DONE, Kirby
from courier_runtime.host_loop import emit_signal, run_once
from courier_runtime.ledger_engine import LedgerEngine, task_id_for


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_verifier(task, result, home: Path) -> Verdict:
    arts = result.payload.get("artifacts") or []
    if not arts:
        return Verdict(False, "no artifacts")
    for art in arts:
        path = home / art["path"]
        if not path.exists() or _sha256(path.read_bytes()) != art["sha256"]:
            return Verdict(False, f"mismatch on {art['path']}")
    return Verdict(True, "verified artifact bytes")


def test_b6_wake_outside_lock(tmp_path: Path) -> None:
    """on_wake_ready runs after run_once releases the campaign lock."""
    ctrl = Controller(tmp_path / "home", verifier=lambda _: _artifact_verifier).boot()
    try:
        campaign_path = tmp_path / "campaign" / "kirby.json"
        engine = LedgerEngine(ctrl, campaign_path, "host-a")
        engine.add_workkeys(["WK-B6"])
        engine.open_slot("S1", "local")
        signal_path = tmp_path / "campaign" / "signals.log"
        emit_signal(signal_path, "IDLE")
        state = {"offset": 0, "last_tick": 0.0, "notified": {}}
        callback_calls = []

        def on_wake(slot: str, workkey: str, token: int) -> None:
            fd = os.open(engine.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
            callback_calls.append((slot, workkey, token))

        kirby = Kirby(campaign_path, "host-a")
        run_once(kirby, "S1", signal_path, state, on_wake_ready=on_wake, engine=engine)
        assert len(callback_calls) == 1
        assert callback_calls[0][0] == "S1"
        assert callback_calls[0][1] == "WK-B6"
    finally:
        ctrl.stop()


def test_b6_host_loop_finish_turn_canary_abc_zero_human_relay(tmp_path: Path) -> None:
    """A→B→C reaches DONE only through LedgerEngine.finish_turn."""
    home = tmp_path / "home"
    ctrl = Controller(home, verifier=lambda _: _artifact_verifier).boot()
    try:
        campaign_path = tmp_path / "campaign" / "kirby.json"
        engine = LedgerEngine(ctrl, campaign_path, "host-a")
        engine.add_workkeys(["WK-A", "WK-B", "WK-C"])
        engine.open_slot("S1", "local")
        signal_path = tmp_path / "campaign" / "signals.log"
        state = {"offset": 0, "last_tick": 0.0, "notified": {}}
        kirby = Kirby(campaign_path, "host-a")
        emit_signal(signal_path, "IDLE")
        woken = []
        run_once(kirby, "S1", signal_path, state, on_wake_ready=lambda s, w, t: woken.append((s, w, t)), engine=engine)
        assert [item[1] for item in woken] == ["WK-A"]

        for index, workkey in enumerate(["WK-A", "WK-B", "WK-C"], start=1):
            slot, current, token = woken[-1]
            assert current == workkey
            emit_signal(signal_path, f"TURN_ENDED outcome=DONE checkpoint=premature-{workkey}")
            results, _, _ = run_once(kirby, "S1", signal_path, state, engine=engine)
            assert results == ["NOT_PROVEN"]
            assert json.loads(campaign_path.read_text())["workkeys"][workkey]["state"] == CLAIMED

            task_id = engine.submit(
                workkey,
                {
                    "adapter": "synthetic",
                    "params": {"estimated_cost_eur": 0.0, "step": workkey},
                    "effect_class": "idempotent",
                    "max_attempts": 1,
                    "lease_ttl_s": 30,
                },
                slot=slot,
                token=token,
            )
            assert task_id == task_id_for(workkey)
            claimed = ctrl.claim({"worker_id": "w-canary"})
            ctrl.start({"dispatch_id": claimed["dispatch_id"], "worker_id": "w-canary"})
            art_bytes = f"artifact-{workkey}-{index}".encode("utf-8")
            art_name = f"{workkey}.bin"
            (home / art_name).write_bytes(art_bytes)
            ctrl.result({
                "dispatch_id": claimed["dispatch_id"],
                "result_id": f"res-{workkey}",
                "outcome": "success",
                "artifacts": [{"path": art_name, "sha256": _sha256(art_bytes)}],
            })
            ctrl.drain()
            emit_signal(signal_path, f"TURN_ENDED outcome=DONE checkpoint=done-{workkey}")
            run_once(
                kirby, "S1", signal_path, state,
                on_wake_ready=lambda s, w, t: woken.append((s, w, t)),
                engine=engine,
            )

        final_campaign = json.loads(campaign_path.read_text())
        for workkey in ("WK-A", "WK-B", "WK-C"):
            assert final_campaign["workkeys"][workkey]["state"] == DONE
            assert ":RESULT_ACCEPTED" in final_campaign["workkeys"][workkey]["checkpoint"]
        assert final_campaign["counters"]["manual_continue"] == 0
        assert final_campaign["counters"]["completions"] == 3
    finally:
        ctrl.stop()
