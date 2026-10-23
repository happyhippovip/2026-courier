"""Continuation admission. No prompt is sent and no provider is called."""
import json
from pathlib import Path

import pytest

from scripts.continuation_gate import (
    ABSOLUTE_LIMIT_SECONDS,
    MAX_FOLLOWUPS,
    complete,
    evaluate,
    fingerprint,
)

NOW = 1_800_000_000
HEAD = "808273daca7f"
SENDER = "cursor-windows"


def _open(root, workkey="CWQ", sha=HEAD, sender=SENDER, now=NOW, **extra):
    body = dict(
        head=HEAD,
        workkey=workkey,
        sha=sha,
        sender=sender,
        now=now,
        cost_eur=0,
        cost_class="local",
        quota_remaining=1,
    )
    body.update(extra)
    return evaluate(root, **body)


def test_completed_fingerprint_is_not_continued(tmp_path):
    mark = fingerprint(HEAD, "CWQ-103", HEAD)
    assert _open(tmp_path, "CWQ-103")["outcome"] == "admit"
    assert complete(
        tmp_path, sender=SENDER, now=NOW, head=HEAD, workkey="CWQ-103", sha=HEAD, proof="journal:1"
    )["outcome"] == "unchanged"
    again = _open(tmp_path, "CWQ-103")
    assert again["outcome"] == "unchanged"
    assert again["executions"] == 0
    assert again["fingerprint"] == mark


def test_two_overlapping_senders_admit_one(tmp_path):
    import threading

    results = []
    barrier = threading.Barrier(2)

    def run():
        barrier.wait()
        results.append(_open(tmp_path, "CWQ-104"))

    first = threading.Thread(target=run)
    second = threading.Thread(target=run)
    first.start()
    second.start()
    first.join()
    second.join()
    outcomes = sorted(item["outcome"] for item in results)
    assert outcomes == ["admit", "duplicate"]
    assert sum(item["executions"] for item in results) == 1


def test_same_workkey_and_sha_runs_once(tmp_path):
    first = _open(tmp_path, "CWQ-105", sha="same")
    second = _open(tmp_path, "CWQ-105", sha="same", now=NOW + 1)
    assert first["outcome"] == "admit" and first["executions"] == 1
    assert second["outcome"] == "duplicate" and second["executions"] == 0


def test_new_workkey_or_new_sha_is_admitted_once(tmp_path):
    assert _open(tmp_path, "CWQ-106", sha="one")["outcome"] == "admit"
    assert _open(tmp_path, "CWQ-106", sha="two", now=NOW + 1)["outcome"] == "admit"
    assert _open(tmp_path, "CWQ-107", sha="two", now=NOW + 2)["outcome"] == "admit"
    assert _open(tmp_path, "CWQ-106", sha="two", now=NOW + 3)["outcome"] == "duplicate"


def test_unchanged_state_starts_no_job(tmp_path):
    assert _open(tmp_path, "CWQ-107")["outcome"] == "admit"
    complete(tmp_path, sender=SENDER, now=NOW, head=HEAD, workkey="CWQ-107", sha=HEAD, proof="done")
    assert _open(tmp_path, "CWQ-107", now=NOW + 1)["executions"] == 0


def test_aborted_session_is_not_replayed_without_proof(tmp_path):
    aborted = _open(tmp_path, "CWQ-108", session="aborted", proof=None)
    assert aborted["outcome"] == "aborted_no_replay"
    assert aborted["executions"] == 0
    replay = _open(tmp_path, "CWQ-108", now=NOW + 1)
    assert replay["outcome"] == "aborted_no_replay"
    assert replay["executions"] == 0


def test_stale_lease_and_second_sender_are_rejected(tmp_path):
    assert _open(tmp_path, "CWQ-109", ttl=10)["outcome"] == "admit"
    other = _open(tmp_path, "CWQ-109", sender="other-window", now=NOW + 1, sha="other")
    assert other["outcome"] == "duplicate_sender"
    assert other["executions"] == 0
    stale = _open(tmp_path, "CWQ-110", sender="other-window", now=NOW + 10, sha="fresh")
    assert stale["outcome"] == "stale_lease"
    assert (tmp_path / "sender.lock").is_file()


def test_checkpoint_survives_a_new_reader(tmp_path):
    assert _open(tmp_path, "CWQ-110")["outcome"] == "admit"
    saved = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert saved["schema"] == 1
    assert saved["head"] == HEAD
    assert saved["followups"] == 1
    assert saved["pending"] == [fingerprint(HEAD, "CWQ-110", HEAD)]
    assert saved["started_at"] == NOW
    reloaded = _open(tmp_path, "CWQ-110", now=NOW + 1)
    assert reloaded["outcome"] == "duplicate"
    assert reloaded["executions"] == 0


def test_missing_cost_is_not_stored_as_zero(tmp_path):
    blocked = evaluate(
        tmp_path,
        head=HEAD,
        workkey="CWQ-115",
        sha=HEAD,
        sender=SENDER,
        now=NOW,
        cost_eur=None,
        cost_class=None,
        quota_remaining=1,
    )
    assert blocked["outcome"] == "unknown_cost"
    assert blocked["executions"] == 0
    assert not (tmp_path / "checkpoint.json").exists()
    for cost_eur, cost_class in ((0, "unknown"), ("0.0", "local"), (False, "local"), (float("nan"), "local")):
        result = evaluate(
            tmp_path,
            head=HEAD,
            workkey="CWQ-115",
            sha=HEAD,
            sender=SENDER,
            now=NOW,
            cost_eur=cost_eur,
            cost_class=cost_class,
            quota_remaining=1,
        )
        assert result["outcome"] == "unknown_cost"


def test_quota_end_pauses_without_a_job(tmp_path):
    exhausted = _open(tmp_path, "CWQ-116", quota_remaining=0)
    unknown = _open(tmp_path, "CWQ-116", quota_remaining=None, sha="other")
    assert exhausted["outcome"] == "quota_pause" and exhausted["reason"] == "QUOTA_EXHAUSTED"
    assert unknown["outcome"] == "quota_pause" and unknown["reason"] == "QUOTA_UNKNOWN"
    assert exhausted["executions"] == 0
    assert not (tmp_path / "checkpoint.json").exists()


def test_restart_does_not_execute_a_pending_fingerprint_again(tmp_path):
    home = tmp_path / "host-a"
    other = tmp_path / "host-b"
    assert _open(home, "CWQ-117")["executions"] == 1
    assert _open(home, "CWQ-117", now=NOW + 1)["executions"] == 0
    assert _open(other, "CWQ-117")["executions"] == 1


def test_kill_switch_and_absolute_limit_stop_admission(tmp_path):
    assert _open(tmp_path, "CWQ-113", ttl=ABSOLUTE_LIMIT_SECONDS + 1)["outcome"] == "admit"
    limited = _open(
        tmp_path,
        "CWQ-113B",
        sha="next",
        now=NOW + ABSOLUTE_LIMIT_SECONDS,
        ttl=ABSOLUTE_LIMIT_SECONDS + 1,
    )
    assert limited["outcome"] == "limit" and limited["executions"] == 0
    fresh = tmp_path / "killed"
    (fresh / "KILL").parent.mkdir()
    (fresh / "KILL").write_text("stop", encoding="utf-8")
    assert _open(fresh, "CWQ-113")["outcome"] == "killed"


def test_followup_cap_is_five(tmp_path):
    for index in range(MAX_FOLLOWUPS):
        result = _open(tmp_path, f"CWQ-{index}", sha=f"sha-{index}", now=NOW + index)
        assert result["outcome"] == "admit"
    blocked = _open(tmp_path, "CWQ-extra", sha="extra", now=NOW + MAX_FOLLOWUPS)
    assert blocked["outcome"] == "limit"


def test_returning_to_a_head_does_not_replay_pending_work(tmp_path):
    assert _open(tmp_path, "CWQ-117B", sha="a")["outcome"] == "admit"
    assert _open(tmp_path, "CWQ-117C", sha="b", head="new-head", now=NOW + 1)["outcome"] == "admit"
    replay = _open(tmp_path, "CWQ-117B", sha="a", now=NOW + 2)
    assert replay["outcome"] == "duplicate"
    assert replay["executions"] == 0


def test_empty_proof_does_not_complete(tmp_path):
    assert _open(tmp_path, "CWQ-108B")["outcome"] == "admit"
    refused = complete(
        tmp_path, sender=SENDER, now=NOW, head=HEAD, workkey="CWQ-108B", sha=HEAD, proof="  "
    )
    assert refused["outcome"] == "blocked"
    assert _open(tmp_path, "CWQ-108B", now=NOW + 1)["outcome"] == "duplicate"


def test_symlink_checkpoint_is_not_followed(tmp_path):
    gate = tmp_path / "gate"
    gate.mkdir()
    real = tmp_path / "outside.json"
    real.write_text("{}", encoding="utf-8")
    link = gate / "checkpoint.json"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlink not permitted")
    result = _open(gate, "CWQ-110")
    assert result["outcome"] == "blocked"
    assert real.read_text(encoding="utf-8") == "{}"
