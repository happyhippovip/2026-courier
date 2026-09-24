#!/usr/bin/env python3
"""Tests for scripts/worker_contract.py."""

import json
import pytest
from scripts.worker_contract import WorkerContract, main


def test_worker_contract_init():
    w = WorkerContract(
        worker_id="win_test_01",
        capability_set=["b_cap", "a_cap", "a_cap"],
        cost_class="cheap",
        runtime_type="WINDOWS",
    )
    assert w.worker_id == "win_test_01"
    assert w.capability_set == ["a_cap", "b_cap"]
    assert w.cost_class == "CHEAP"
    assert w.runtime_type == "windows"


def test_worker_contract_init_invalid():
    with pytest.raises(ValueError):
        WorkerContract(worker_id="")

    with pytest.raises(ValueError):
        WorkerContract(worker_id=None)  # type: ignore


def test_worker_contract_lifecycle():
    w = WorkerContract("win_01", ["local_exec"], "CHEAP", "windows")

    reg = w.register(quiet=True)
    assert reg["action"] == "REGISTER"
    assert reg["worker_id"] == "win_01"
    assert reg["status"] == "REGISTERED"

    clm = w.claim("task_42", quiet=True)
    assert clm["action"] == "CLAIM"
    assert clm["task_id"] == "task_42"
    assert clm["status"] == "CLAIMED"

    exc = w.execute("exec_99", command="run.bat", quiet=True)
    assert exc["action"] == "EXECUTE"
    assert exc["execution_ref"] == "exec_99"
    assert exc["command"] == "run.bat"
    assert exc["status"] == "RUNNING"

    res = w.result("SUCCESS", ["output.csv"], {"records": 10}, quiet=True)
    assert res["action"] == "RESULT"
    assert res["status"] == "SUCCESS"
    assert res["artifacts"] == ["output.csv"]
    assert res["details"] == {"records": 10}

    cln = w.cleanup("exec_99", quiet=True)
    assert cln["action"] == "CLEANUP"
    assert cln["execution_ref"] == "exec_99"
    assert cln["status"] == "CLEANED"


def test_worker_contract_claim_invalid():
    w = WorkerContract("win_01")
    with pytest.raises(ValueError):
        w.claim("")
    with pytest.raises(ValueError):
        w.execute("")


def test_worker_contract_serialization():
    w1 = WorkerContract("worker_xyz", ["cap1", "cap2"], "EXPENSIVE", "linux")
    d = w1.to_dict()
    w2 = WorkerContract.from_dict(d)
    assert w2.worker_id == w1.worker_id
    assert w2.capability_set == w1.capability_set
    assert w2.cost_class == w1.cost_class
    assert w2.runtime_type == w1.runtime_type


def test_main_cli_test_lifecycle(capsys):
    ret = main(["--worker-id", "w_cli", "--test-lifecycle", "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["worker"]["worker_id"] == "w_cli"
    assert len(data["lifecycle"]) == 5
