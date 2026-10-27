"""RAID-OFFIZIER V1: Event → Decision. Cases A–F. No network, no ledger, no model."""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.automation import raid_officer as officer

REPO_ROOT = Path(__file__).resolve().parents[2]
WK = "WK-RAID-OFFIZIER-V1"
LIMITS = {
    "AUTONOMOUS_SPEND_LIMIT_EUR": 0,
    "HEAVY_JOB_LIMIT": 1,
    "SINGLE_WRITER": "YES",
    "SINGLE_WRITER_ACCOUNT": "Acc1",
    "UNKNOWN_COST": "BLOCK",
}
VALID_LEASE = {"valid": True, "owner": "Acc1", "workkey": WK, "ref": "lease:WK"}
SKIP = {
    "kind": "SKIP",
    "id": "skip-cp09",
    "marker": "CP_09",
    "detail": "SKIP because CP_09",
    "ref": "events.jsonl:1",
}
BLOCKED = {
    "kind": "BLOCKED",
    "id": "evt-cp11",
    "blocker": "CP_11",
    "detail": "CP_11 not reached; planned run did not happen",
    "ref": "events.jsonl:4",
}


def status(**over):
    base = {
        "workkey": WK,
        "gate": "ROT",
        "owner": "Acc1",
        "actor": "Acc1",
        "requested_action": "write",
        "event": dict(SKIP),
        "lease": {"valid": False, "owner": "Acc1", "workkey": WK, "ref": "lease:WK"},
        "journal": {"status": "idle", "ref": "journal:head"},
    }
    base.update(over)
    return base


def assert_quiet(decision):
    assert decision["limits"] == LIMITS
    assert decision["spend_eur"] == 0
    assert decision["start_paid_agent"] is False
    assert decision["spawn_agent"] is False
    assert decision["model_call"] is False
    assert decision["stop_bypass"] is False
    assert decision["heavy_job_started"] is False
    assert decision["repeat"] is False
    assert decision["next_action"] not in {"MERGE", "FORCE_PUSH", "STOP_BYPASS", "READY_FOR_REVIEW"}
    assert isinstance(decision["evidence_refs"], list) and decision["evidence_refs"]
    assert decision["format"] == officer.FORMAT


def test_a_gate_rot_blocks_write_and_diagnoses():
    decision = officer.decide(status(watchdog={"status": "ROT", "ref": "DPS_STATUS.json"}))
    assert decision["case"] == "A"
    assert decision["next_action"] == "DIAGNOSE"
    assert decision["write_allowed"] is False
    assert decision["ledger_write_allowed"] is False
    assert decision["owner"] == "Acc1"
    assert decision["gate"] == "ROT"
    assert "CP_09" in decision["reason"]
    assert "events.jsonl:1" in decision["evidence_refs"]
    assert "skip:CP_09" in decision["evidence_refs"]
    assert decision["coalesced"] is False
    assert_quiet(decision)


def test_b_gate_stays_rot_coalesces_without_a_repeat_loop():
    first = officer.decide(status())
    assert first["next_action"] == "DIAGNOSE" and first["case"] == "A"
    priors = [first]
    for _ in range(5):
        nxt = officer.decide(status(prior_decisions=priors))
        assert nxt["case"] == "B"
        assert nxt["next_action"] == "HOLD"
        assert nxt["coalesced"] is True
        assert nxt["write_allowed"] is False
        assert nxt["fingerprint"] == first["fingerprint"]
        assert nxt["idempotency_key"] == first["idempotency_key"]
        assert_quiet(nxt)
        priors.append(nxt)
    assert sum(item["next_action"] == "DIAGNOSE" for item in priors) == 1


def test_b_a_new_blocker_is_diagnosed_once_then_coalesces():
    first = officer.decide(status())
    moved = officer.decide(status(event=dict(BLOCKED), prior_decisions=[first]))
    assert moved["next_action"] == "DIAGNOSE"
    assert moved["fingerprint"] != first["fingerprint"]
    again = officer.decide(status(event=dict(BLOCKED), prior_decisions=[first, moved]))
    assert again["next_action"] == "HOLD" and again["case"] == "B" and again["coalesced"] is True


def test_c_green_releases_writer_only_with_valid_lease():
    released = officer.decide(status(gate="GREEN", lease=dict(VALID_LEASE), watchdog={"status": "GREEN", "ref": "DPS_STATUS.json"}))
    assert released["case"] == "C"
    assert released["next_action"] == "RELEASE_WRITER"
    assert released["write_allowed"] is True
    assert released["ledger_write_allowed"] is True
    assert released["lease_valid"] is True
    assert released["owner"] == "Acc1"
    assert_quiet(released)

    for bad in (False, None, "true", 1, "yes", 0):
        held = officer.decide(status(gate="GREEN", lease={"valid": bad, "owner": "Acc1", "workkey": WK}))
        assert held["next_action"] == "WAIT_LEASE"
        assert held["case"] == "C"
        assert held["next_action"] != "RELEASE_WRITER"
        assert held["write_allowed"] is False
        assert held["ledger_write_allowed"] is False
        assert held["lease_valid"] is False
        assert_quiet(held)


def test_c_rot_then_green_releases_only_after_the_lease_is_valid():
    diagnosed = officer.decide(status())
    still = officer.decide(status(gate="GREEN", lease={"valid": False, "owner": "Acc1", "workkey": WK}, prior_decisions=[diagnosed]))
    assert still["next_action"] == "WAIT_LEASE"
    assert still["fingerprint"] != diagnosed["fingerprint"]
    released = officer.decide(status(gate="GREEN", lease=dict(VALID_LEASE), prior_decisions=[diagnosed, still]))
    assert released["next_action"] == "RELEASE_WRITER"
    assert released["write_allowed"] is True


def test_c_conflicting_watchdog_stays_rot():
    decision = officer.decide(status(gate="GREEN", lease=dict(VALID_LEASE), watchdog={"status": "ROT", "ref": "DPS_STATUS.json"}))
    assert decision["gate"] == "ROT"
    assert decision["next_action"] == "DIAGNOSE"
    assert decision["write_allowed"] is False
    assert "disagree" in decision["reason"]


def test_d_only_the_rightful_owner_may_write():
    owner = officer.decide(status(gate="GREEN", actor="Acc1", owner="Acc1", lease=dict(VALID_LEASE), requested_action="write"))
    ninja = officer.decide(status(
        gate="GREEN", actor="Acc2", owner="Acc1", requested_action="write",
        lease={"valid": True, "owner": "Acc2", "workkey": WK, "ref": "lease:ninja"},
    ))
    assert owner["next_action"] == "RELEASE_WRITER" and owner["write_allowed"] is True
    assert ninja["case"] == "D"
    assert ninja["next_action"] == "DENY_NINJA"
    assert ninja["write_allowed"] is False
    assert ninja["ledger_write_allowed"] is False
    assert ninja["owner"] == "Acc1"
    assert ninja["actor"] == "Acc2"
    assert ninja["workkey"] == owner["workkey"]
    assert "anti-ninja" in ninja["reason"]
    assert_quiet(ninja)


def test_d_write_is_refused_when_no_owner_is_recorded():
    decision = officer.decide(status(gate="GREEN", owner="", actor="Acc2", lease=dict(VALID_LEASE)))
    assert decision["next_action"] == "DENY_NINJA"
    assert decision["write_allowed"] is False


@pytest.mark.parametrize("cost", [
    {},
    {"cost_eur": None},
    {"cost_eur": "unknown"},
    {"cost_eur": ""},
    {"cost_known": False, "cost_eur": 0},
    {"cost_eur": True},
    {"cost_eur": "5"},
    {"cost_eur": float("nan")},
    {"cost_eur": float("inf")},
    {"cost_eur": -1},
])
def test_e_unknown_cost_blocks_paid_agent(cost):
    decision = officer.decide(status(
        gate="GREEN", lease=dict(VALID_LEASE), requested_action="start_paid_agent", heavy_jobs_running=0, **cost,
    ))
    assert decision["case"] == "E"
    assert decision["next_action"] == "BLOCK_UNKNOWN_COST"
    assert decision["next_action"] != "RELEASE_WRITER"
    assert decision["start_paid_agent"] is False
    assert decision["write_allowed"] is False
    assert decision["spend_eur"] == 0
    assert "UNKNOWN_COST=BLOCK" in decision["reason"]
    assert_quiet(decision)


def test_e_known_spend_does_not_start_an_agent():
    positive = officer.decide(status(
        gate="GREEN", lease=dict(VALID_LEASE), requested_action="start_paid_agent", cost_eur=2, cost_known=True,
    ))
    zero = officer.decide(status(
        gate="GREEN", lease=dict(VALID_LEASE), requested_action="model_call", cost_eur=0, cost_known=True,
    ))
    assert positive["next_action"] == "BLOCK_SPEND" and positive["spend_eur"] == 0 and positive["start_paid_agent"] is False
    assert zero["next_action"] == "BLOCK_PAID_AGENT" and zero["start_paid_agent"] is False and zero["spend_eur"] == 0
    assert_quiet(positive)
    assert_quiet(zero)


def test_f_no_progress_escalates_once_with_the_blocker():
    stalled = status(progress=False, event=dict(BLOCKED))
    diagnosed = officer.decide(stalled)
    assert diagnosed["next_action"] == "DIAGNOSE"  # read-only diagnose before any escalation
    escalated = officer.decide(status(progress=False, event=dict(BLOCKED), prior_decisions=[diagnosed]))
    assert escalated["case"] == "F"
    assert escalated["next_action"] == "ESCALATE"
    assert escalated["owner"] == "Ultra"
    assert escalated["escalate_to"] == "Ultra"
    assert escalated["escalation_count"] == 1
    assert escalated["blocker"] == "CP_11"
    assert "CP_11" in escalated["reason"]
    assert "events.jsonl:4" in escalated["evidence_refs"]
    assert escalated["write_allowed"] is False
    assert_quiet(escalated)

    priors = [diagnosed, escalated]
    for _ in range(4):
        held = officer.decide(status(progress=False, event=dict(BLOCKED), prior_decisions=priors))
        assert held["next_action"] == "HOLD"
        assert held["case"] == "F"
        assert held["coalesced"] is True
        assert held["escalation_count"] == 1
        assert held["escalate_to"] is None
        assert_quiet(held)
        priors.append(held)
    assert sum(item["next_action"] == "ESCALATE" for item in priors) == 1


def test_f_diagnosis_done_is_the_escalation_trigger_and_it_fires_once():
    triggered = officer.decide(status(progress=False, diagnosis_done=True, event=dict(BLOCKED)))
    assert triggered["next_action"] == "ESCALATE" and triggered["escalation_count"] == 1
    assert "CP_11" in triggered["reason"]
    held = officer.decide(status(progress=False, diagnosis_done=True, escalated=True, event=dict(BLOCKED)))
    assert held["next_action"] == "HOLD" and held["escalation_count"] == 1 and held["coalesced"] is True


def test_stop_on_a_green_gate_does_not_release_the_writer():
    decision = officer.decide(status(gate="GREEN", stop=True, lease=dict(VALID_LEASE), event={"kind": "STOP", "ref": "watchdog:STOP", "marker": "MUSE_STOP"}))
    assert decision["next_action"] != "RELEASE_WRITER"
    assert decision["write_allowed"] is False
    assert decision["stop_bypass"] is False
    assert decision["case"] == "STOP"
    again = officer.decide(status(
        gate="GREEN", stop=True, lease=dict(VALID_LEASE), prior_decisions=[decision],
        event={"kind": "STOP", "ref": "watchdog:STOP", "marker": "MUSE_STOP"},
    ))
    assert again["next_action"] == "HOLD" and again["coalesced"] is True and again["write_allowed"] is False


@pytest.mark.parametrize("requested", ["merge", "force_push", "force-push", "ready_for_review", "stop_bypass"])
def test_merge_force_push_and_stop_bypass_are_refused(requested):
    decision = officer.decide(status(gate="GREEN", lease=dict(VALID_LEASE), requested_action=requested))
    assert decision["next_action"] == "BLOCK_BANNED"
    assert decision["write_allowed"] is False
    assert decision["ledger_write_allowed"] is False
    assert_quiet(decision)


def test_heavy_job_limit_blocks_a_second_job_and_never_starts_one():
    blocked = officer.decide(status(requested_action="heavy_job", cost_eur=0, cost_known=True, heavy_jobs_running=1))
    idle = officer.decide(status(requested_action="heavy_job", cost_eur=0, cost_known=True, heavy_jobs_running=0))
    unreadable = officer.decide(status(requested_action="heavy_job", cost_eur=0, cost_known=True, heavy_jobs_running=True))
    assert blocked["next_action"] == "BLOCK_HEAVY" and "already running" in blocked["reason"]
    assert idle["next_action"] == "BLOCK_HEAVY" and idle["heavy_job_started"] is False
    assert unreadable["next_action"] == "BLOCK_HEAVY"
    assert_quiet(blocked)
    assert_quiet(idle)


def test_non_acc1_owner_is_not_the_ledger_writer():
    decision = officer.decide(status(
        gate="GREEN", owner="Acc2", actor="Acc2", requested_action="write",
        lease={"valid": True, "owner": "Acc1", "workkey": WK},
    ))
    assert decision["next_action"] == "BLOCK_SINGLE_WRITER"
    assert decision["write_allowed"] is False
    assert decision["ledger_write_allowed"] is False


def test_lease_for_another_workkey_does_not_release():
    decision = officer.decide(status(
        gate="GREEN",
        lease={"valid": True, "owner": "Acc1", "workkey": "WK-OTHER", "ref": "lease:other"},
    ))
    assert decision["next_action"] == "WAIT_LEASE"
    assert decision["write_allowed"] is False


def test_gruen_is_green_and_a_skip_marker_supplies_the_event():
    decision = officer.decide({
        "workkey": WK,
        "gate": "GRÜN",
        "owner": "Acc1",
        "actor": "Acc1",
        "requested_action": "write",
        "skip_marker": {"present": True, "marker": "CP_09", "ref": "SKIP_CP_09"},
        "lease": dict(VALID_LEASE),
    })
    assert decision["gate"] == "GREEN"
    assert decision["next_action"] == "RELEASE_WRITER"
    assert "skip:CP_09" in decision["evidence_refs"]


def test_event_line_and_lease_invalid_event_block_release():
    line = json.dumps({"kind": "LEASE_INVALID", "ref": "events.jsonl:2", "marker": "lease"})
    decision = officer.decide(status(gate="GREEN", event_line=line, event=None, lease=dict(VALID_LEASE)))
    assert decision["lease_valid"] is False
    assert decision["next_action"] != "RELEASE_WRITER"


def test_decide_is_deterministic_and_does_not_mutate_or_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = status()
    before = json.dumps(raw, sort_keys=True)
    first = json.dumps(officer.decide(raw), sort_keys=True)
    second = json.dumps(officer.decide(raw), sort_keys=True)
    assert first == second
    assert json.dumps(raw, sort_keys=True) == before
    assert list(tmp_path.iterdir()) == []


def test_load_status_reads_watchdog_event_skip_lease_and_journal(tmp_path):
    (tmp_path / "DPS_STATUS.json").write_text(json.dumps({"status": "ROT", "ref": "DPS_STATUS.json"}), encoding="utf-8")
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"kind": "HEARTBEAT", "id": "old", "ref": "events.jsonl:0"}) + "\n"
        + json.dumps({"kind": "SKIP", "id": "skip-cp09", "marker": "CP_09", "ref": "events.jsonl:1"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "SKIP_CP_09").write_text("CP_09\n", encoding="utf-8")
    (tmp_path / "lease.json").write_text(
        json.dumps({"valid": False, "owner": "Acc1", "workkey": WK, "ref": "lease.json"}), encoding="utf-8")
    (tmp_path / "journal.json").write_text(json.dumps({"status": "idle", "ref": "journal.json"}), encoding="utf-8")
    (tmp_path / "status.json").write_text(json.dumps({
        "workkey": WK,
        "owner": "Acc1",
        "actor": "Acc1",
        "requested_action": "write",
        "watchdog_file": "DPS_STATUS.json",
        "events_jsonl": "events.jsonl",
        "skip_marker_file": "SKIP_CP_09",
        "lease_file": "lease.json",
        "journal_file": "journal.json",
    }), encoding="utf-8")
    loaded = officer.load_status(tmp_path / "status.json")
    decision = officer.decide(loaded)
    assert decision["next_action"] == "DIAGNOSE"
    assert decision["write_allowed"] is False
    assert "events.jsonl:1" in decision["evidence_refs"]
    assert "skip:CP_09" in decision["evidence_refs"]
    assert set(decision["inputs"]) >= {"watchdog", "event", "skip_marker", "lease", "journal"}
    assert list(tmp_path.glob("*.tmp")) == []


def test_missing_skip_marker_file_is_not_a_skip(tmp_path):
    (tmp_path / "status.json").write_text(json.dumps({
        "workkey": WK, "gate": "ROT", "owner": "Acc1", "actor": "Acc1", "requested_action": "write",
        "skip_marker_file": "SKIP_ABSENT",
        "lease": {"valid": False, "owner": "Acc1", "workkey": WK},
    }), encoding="utf-8")
    loaded = officer.load_status(tmp_path / "status.json")
    assert loaded["skip_marker"]["present"] is False
    assert officer.decide(loaded)["next_action"] == "DIAGNOSE"


def _cli(tmp_path, *args):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "tools.automation.raid_officer", *args],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=30,
    )


def test_cli_from_status_prints_one_decision_json(tmp_path):
    path = tmp_path / "status.json"
    path.write_text(json.dumps(status()), encoding="utf-8")
    done = _cli(tmp_path, "--from-status", str(path))
    assert done.returncode == 0, done.stderr
    assert "Traceback" not in done.stderr
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    decision = json.loads(lines[0])
    assert decision["case"] == "A" and decision["next_action"] == "DIAGNOSE" and decision["exit_code"] == 0
    assert_quiet(decision)


def test_cli_usage_and_bad_status_exit_codes(tmp_path):
    usage = _cli(tmp_path)
    assert usage.returncode == 2 and usage.stdout == ""

    missing = _cli(tmp_path, "--from-status", str(tmp_path / "missing.json"))
    assert missing.returncode == 3 and missing.stdout == "" and "RAID_OFFICER_ERROR" in missing.stderr

    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    invalid = _cli(tmp_path, "--from-status", str(bad))
    assert invalid.returncode == 4 and invalid.stdout == "" and "RAID_OFFICER_ERROR" in invalid.stderr

    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    assert _cli(tmp_path, "--from-status", str(array)).returncode == 4


def test_decisions_out_is_opt_in(tmp_path):
    path = tmp_path / "status.json"
    path.write_text(json.dumps(status()), encoding="utf-8")
    fixture = tmp_path / "decisions.jsonl"
    quiet = _cli(tmp_path, "--from-status", str(path))
    assert quiet.returncode == 0 and not fixture.exists()
    saved = _cli(tmp_path, "--from-status", str(path), "--decisions-out", str(fixture))
    assert saved.returncode == 0
    line = json.loads(fixture.read_text(encoding="utf-8"))
    assert line == json.loads(saved.stdout)
    assert line["next_action"] == "DIAGNOSE"


def test_module_imports_nothing_outside_the_stdlib_decision_path():
    source = (REPO_ROOT / "tools" / "automation" / "raid_officer.py").read_text(encoding="utf-8")
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".")[0])
    assert modules == {"__future__", "argparse", "hashlib", "json", "math", "os", "pathlib", "sys"}
    assert "courier_runtime" not in source
    assert "StaleLease" not in source
    assert "scripts." not in source
