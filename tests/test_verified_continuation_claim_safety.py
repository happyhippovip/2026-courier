"""VC-1: an expired or unreadable claim is not proof that its unit stopped, so it is never taken over silently.

Before: ``claim`` unlinked any expired or unparsable claim file and claimed the workkey, and
any process using the same owner string (the default ``google-antigravity``) could "renew" a
live lease held by another process. Both run the unit twice.
"""
import json
import os
import time

import pytest

from scripts.verified_continuation import VerifiedContinuation


@pytest.fixture
def engine(tmp_path):
    (tmp_path / "repo").mkdir()
    return VerifiedContinuation(root_dir=tmp_path / "repo", ledger_dir=tmp_path / "ledger")


def _plant(engine, workkey, owner, pid, age_s, ttl_s=60):
    path = engine.claims_dir / f"{workkey}.claim"
    path.write_text(json.dumps({"workkey": workkey, "owner": owner, "pid": pid,
                                "created_at_ts": time.time() - age_s, "ttl_s": ttl_s}))
    return path


def test_an_expired_claim_of_another_owner_is_not_taken_over(engine):
    path = _plant(engine, "WK1", "worker-a", 999999, age_s=3600)
    before = path.read_bytes()
    assert engine.claim("WK1", owner="worker-b") is False
    assert path.read_bytes() == before


def test_an_expired_claim_of_the_same_owner_in_another_process_is_not_taken_over(engine):
    path = _plant(engine, "WK1", "google-antigravity", os.getpid() + 1, age_s=3600)
    assert engine.claim("WK1") is False
    assert json.loads(path.read_text())["pid"] == os.getpid() + 1


def test_a_live_lease_of_another_process_with_the_same_owner_is_not_renewed(engine):
    path = _plant(engine, "WK1", "google-antigravity", os.getpid() + 1, age_s=1)
    assert engine.claim("WK1") is False
    assert json.loads(path.read_text())["pid"] == os.getpid() + 1


@pytest.mark.parametrize("content", ["{not json", "[]", '{"owner": "x"}', ""])
def test_an_unreadable_claim_is_not_taken_over(engine, content):
    path = engine.claims_dir / "WK1.claim"
    path.write_text(content)
    assert engine.claim("WK1", owner="worker-b") is False
    assert path.read_text() == content


def test_the_holding_process_may_still_renew(engine):
    assert engine.claim("WK1", owner="worker-a") is True
    assert engine.claim("WK1", owner="worker-a") is True


@pytest.mark.parametrize("actor,reason", [("", "x"), ("dennis", ""), (None, "x"), ("dennis", "  ")])
def test_reclaim_needs_an_actor_and_a_reason(engine, actor, reason):
    _plant(engine, "WK1", "worker-a", 999999, age_s=3600)
    with pytest.raises(ValueError):
        engine.reclaim("WK1", actor, reason)


def test_reclaim_refuses_a_live_lease(engine):
    _plant(engine, "WK1", "worker-a", 999999, age_s=1)
    with pytest.raises(ValueError, match="live"):
        engine.reclaim("WK1", "dennis", "too early")


def test_reclaim_moves_the_expired_claim_aside_with_a_record(engine):
    _plant(engine, "WK1", "worker-a", 999999, age_s=3600)
    record = engine.reclaim("WK1", "dennis", "worker-a is gone")
    assert record["actor"] == "dennis" and record["reason"] == "worker-a is gone"
    assert record["previous"]["owner"] == "worker-a"
    assert not (engine.claims_dir / "WK1.claim").exists()
    kept = list(engine.claims_dir.glob("WK1.claim.reclaimed-*"))
    assert len(kept) == 1 and json.loads(kept[0].read_text())["previous"]["owner"] == "worker-a"
    assert engine.claim("WK1", owner="worker-b") is True


def test_reclaim_also_frees_an_unreadable_claim(engine):
    (engine.claims_dir / "WK1.claim").write_text("{not json")
    record = engine.reclaim("WK1", "dennis", "corrupt file after crash")
    assert record["previous"] is None
    assert engine.claim("WK1", owner="worker-b") is True


def test_reclaim_refuses_a_workkey_with_a_verified_result(engine):
    _plant(engine, "WK1", "worker-a", 999999, age_s=3600)
    (engine.results_dir / "WK1.result").write_text("{}")
    with pytest.raises(ValueError, match="verified result"):
        engine.reclaim("WK1", "dennis", "looks stuck")


# Review v8c
def test_a_restarted_process_with_a_reused_pid_cannot_renew_a_dead_claim(engine):
    path = _plant(engine, "WK1", "google-antigravity", os.getpid(), age_s=1)   # same pid, other process life
    assert engine.claim("WK1") is False
    assert json.loads(path.read_text()).get("holder_nonce") is None


def test_the_holding_process_renews_by_its_nonce(engine):
    assert engine.claim("WK1", owner="worker-a") is True
    first = engine.is_claimed("WK1")["holder_nonce"]
    assert engine.claim("WK1", owner="worker-a") is True
    assert engine.is_claimed("WK1")["holder_nonce"] == first


def test_reclaim_refuses_a_workkey_with_a_durable_checkpoint(engine):
    _plant(engine, "WK1", "worker-a", 999999, age_s=3600)
    engine.checkpoint("WK1", {"status": "PASS"})              # crashed after its checkpoint, before release
    with pytest.raises(ValueError, match="done"):
        engine.reclaim("WK1", "dennis", "looks stuck")


def test_reclaim_and_the_expired_message_from_the_command_line(tmp_path, capsys):
    from scripts.verified_continuation import main
    ledger = tmp_path / "ledger"
    engine = VerifiedContinuation(root_dir=tmp_path, ledger_dir=ledger)
    _plant(engine, "WK1", "worker-a", 999999, age_s=3600)
    assert main(["--workkey", "WK1", "--ledger-dir", str(ledger)]) == 1
    assert "expired" in capsys.readouterr().out
    assert main(["--reclaim", "WK1", "--actor", "dennis", "--ledger-dir", str(ledger)]) == 2   # no reason
    assert main(["--reclaim", "WK1", "--actor", "dennis", "--reason", "worker-a gone",
                 "--ledger-dir", str(ledger)]) == 0
    assert engine.is_claimed("WK1") is None
