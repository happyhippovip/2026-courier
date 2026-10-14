"""Tests for courier_runtime.continuation (Item P9 test hardening).

Covers:
- AcceptedFact immutability and schema
- AcceptedLog append, validation, persistence, and filtering
- Checkpoint state restoration from log
- decide() decision matrix (DONE, NEEDS_USER, RECOVERING, WAITING, RUNNING)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from courier_runtime.continuation import (
    AcceptedFact,
    AcceptedLog,
    Checkpoint,
    decide,
)


# -----------------------------------------------------------------------------
# AcceptedFact & AcceptedLog Tests
# -----------------------------------------------------------------------------

def test_accepted_fact_dataclass():
    fact = AcceptedFact(
        workkey="P9-CONTINUATION",
        step=1,
        statement="tests verified",
        sources=("evt-101", "ev-102"),
        accepted_by="controller",
        accepted_at=1700000000.0,
    )
    assert fact.workkey == "P9-CONTINUATION"
    assert fact.step == 1
    assert fact.statement == "tests verified"
    assert fact.sources == ("evt-101", "ev-102")
    assert fact.accepted_by == "controller"
    assert fact.accepted_at == 1700000000.0


def test_accepted_log_append_and_read(tmp_path: Path):
    log_file = str(tmp_path / "accepted.jsonl")
    log = AcceptedLog(log_file)

    # Empty log
    assert log.facts() == []

    # Valid append
    fact1 = AcceptedFact(
        workkey="WK1",
        step=0,
        statement="step 0 passed",
        sources=("evt-1",),
        accepted_by="controller",
        accepted_at=time.time(),
    )
    fact2 = AcceptedFact(
        workkey="WK2",
        step=0,
        statement="step 0 passed for wk2",
        sources=("evt-2",),
        accepted_by="human",
        accepted_at=time.time(),
    )
    log.append(fact1)
    log.append(fact2)

    all_facts = log.facts()
    assert len(all_facts) == 2
    assert all_facts[0].workkey == "WK1"
    assert all_facts[1].workkey == "WK2"

    # Filtered by workkey
    wk1_facts = log.facts(workkey="WK1")
    assert len(wk1_facts) == 1
    assert wk1_facts[0].statement == "step 0 passed"


def test_accepted_log_validation_errors(tmp_path: Path):
    log_file = str(tmp_path / "accepted.jsonl")
    log = AcceptedLog(log_file)

    # Missing sources
    fact_no_sources = AcceptedFact(
        workkey="WK1",
        step=0,
        statement="no sources",
        sources=(),
        accepted_by="controller",
        accepted_at=time.time(),
    )
    with pytest.raises(ValueError, match="at least one accepted source"):
        log.append(fact_no_sources)

    # Invalid accepted_by
    fact_bad_actor = AcceptedFact(
        workkey="WK1",
        step=0,
        statement="bot actor",
        sources=("evt-1",),
        accepted_by="worker",  # type: ignore
        accepted_at=time.time(),
    )
    with pytest.raises(ValueError, match="only the controller or a human can accept"):
        log.append(fact_bad_actor)


# -----------------------------------------------------------------------------
# Checkpoint Tests
# -----------------------------------------------------------------------------

def test_checkpoint_from_log(tmp_path: Path):
    log_file = str(tmp_path / "accepted.jsonl")
    log = AcceptedLog(log_file)
    plan = ["prep", "build", "verify", "release"]

    # 1. Empty log -> last_accepted_step = -1
    cp1 = Checkpoint.from_log("WK1", plan, log)
    assert cp1.last_accepted_step == -1
    assert cp1.plan == plan

    # 2. Log with facts -> max step
    log.append(AcceptedFact("WK1", 0, "prep done", ("src-1",), "controller", time.time()))
    log.append(AcceptedFact("WK1", 1, "build done", ("src-2",), "controller", time.time()))
    log.append(AcceptedFact("OTHER", 3, "other done", ("src-3",), "controller", time.time()))

    cp2 = Checkpoint.from_log("WK1", plan, log)
    assert cp2.last_accepted_step == 1


# -----------------------------------------------------------------------------
# decide() Decision Matrix Tests
# -----------------------------------------------------------------------------

def test_decide_done():
    plan = ["step0", "step1"]
    cp = Checkpoint(workkey="W1", plan=plan, last_accepted_step=1)
    res = decide(cp, grants_valid={}, owned_alive=[], lease_available=True)
    assert res["safe"] is True
    assert res["state"] == "DONE"
    assert res["resume_step"] is None


def test_decide_unconfirmed_non_idempotent_step():
    plan = ["step0", "step1", "step2"]
    # step 0 accepted, step 1 was attempted non-idempotently without confirmation
    cp = Checkpoint(
        workkey="W1",
        plan=plan,
        last_accepted_step=0,
        attempted={1: {"effect_class": "non_idempotent", "effect_confirmed": False}},
    )
    res = decide(cp, grants_valid={}, owned_alive=[], lease_available=True)
    assert res["safe"] is False
    assert res["state"] == "NEEDS_USER"
    assert res["resume_step"] == 1
    assert "confirmation required" in res["reasons"][0]


def test_decide_confirmed_non_idempotent_step():
    plan = ["step0", "step1", "step2"]
    # step 0 accepted, step 1 was confirmed
    cp = Checkpoint(
        workkey="W1",
        plan=plan,
        last_accepted_step=0,
        attempted={1: {"effect_class": "non_idempotent", "effect_confirmed": True}},
    )
    res = decide(cp, grants_valid={}, owned_alive=[], lease_available=True)
    assert res["safe"] is True
    assert res["state"] == "RUNNING"
    assert res["resume_step"] == 1


def test_decide_expired_grant():
    plan = ["step0", "step1"]
    cp = Checkpoint(
        workkey="W1",
        plan=plan,
        last_accepted_step=-1,
        grant_ids=["grant-abc"],
    )
    res = decide(cp, grants_valid={"grant-abc": False}, owned_alive=[], lease_available=True)
    assert res["safe"] is False
    assert res["state"] == "NEEDS_USER"
    assert "authority no longer valid" in res["reasons"][0]


def test_decide_owned_alive_processes():
    plan = ["step0", "step1"]
    cp = Checkpoint(workkey="W1", plan=plan, last_accepted_step=-1)
    res = decide(cp, grants_valid={}, owned_alive=[12345], lease_available=True)
    assert res["safe"] is False
    assert res["state"] == "RECOVERING"
    assert "owned processes still running" in res["reasons"][0]


def test_decide_lease_unavailable():
    plan = ["step0", "step1"]
    cp = Checkpoint(workkey="W1", plan=plan, last_accepted_step=-1)
    res = decide(cp, grants_valid={}, owned_alive=[], lease_available=False)
    assert res["safe"] is False
    assert res["state"] == "WAITING"
    assert "write lease" in res["reasons"][0]


def test_decide_running_nominal():
    plan = ["step0", "step1"]
    cp = Checkpoint(workkey="W1", plan=plan, last_accepted_step=-1)
    res = decide(cp, grants_valid={}, owned_alive=[], lease_available=True)
    assert res["safe"] is True
    assert res["state"] == "RUNNING"
    assert res["resume_step"] == 0
