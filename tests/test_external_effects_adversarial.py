import pytest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from scripts.courier_continue import execute_task

def test_release_returns_false():
    task = {"instruction": "x", "edge_name": "RELEASE"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert not success
    assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_RELEASE"

def test_public_deployment_returns_false():
    task = {"instruction": "x", "edge_name": "PUBLIC DEPLOYMENT"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert not success
    assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_PUBLIC DEPLOYMENT"

    task2 = {"instruction": "x", "edge_name": "PUBLIC_DEPLOYMENT"}
    res_task2, success2, blocker2 = execute_task(task2, "ledger.json", {})
    assert not success2
    assert blocker2 == "UNVERIFIED_EXTERNAL_EFFECT_PUBLIC_DEPLOYMENT"

def test_first_pilot_returns_false():
    task = {"instruction": "x", "edge_name": "FIRST PILOT"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert not success
    assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_FIRST PILOT"

    task2 = {"instruction": "x", "edge_name": "FIRST_PILOT"}
    res_task2, success2, blocker2 = execute_task(task2, "ledger.json", {})
    assert not success2
    assert blocker2 == "UNVERIFIED_EXTERNAL_EFFECT_FIRST_PILOT"

def test_payment_only_when_actually_required_returns_false():
    task = {"instruction": "x", "edge_name": "PAYMENT ONLY WHEN ACTUALLY REQUIRED"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert not success
    assert blocker == "MONEY_REQUIRED_PAYMENT_PROOF"

    task2 = {"instruction": "x", "edge_name": "PAYMENT_ONLY_WHEN_ACTUALLY_REQUIRED"}
    res_task2, success2, blocker2 = execute_task(task2, "ledger.json", {})
    assert not success2
    assert blocker2 == "MONEY_REQUIRED_PAYMENT_PROOF"

def test_onboard_first_pilot_customer_returns_false():
    task = {"instruction": "x", "edge_name": "ONBOARD_FIRST_PILOT_CUSTOMER"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert not success
    assert blocker == "HUMAN_REQUIRED_PILOT_ONBOARDING"

def test_external_publication_returns_false():
    task = {"instruction": "x", "edge_name": "EXTERNAL_PUBLICATION"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert not success
    assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_EXTERNAL_PUBLICATION"

def test_sales_package_returns_false():
    task = {"instruction": "x", "edge_name": "SALES PACKAGE"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert success

    task2 = {"instruction": "x", "edge_name": "SALES_PACKAGE"}
    res_task2, success2, blocker2 = execute_task(task2, "ledger.json", {})
    assert success2

def test_post_pilot_hardening_returns_false():
    task = {"instruction": "x", "edge_name": "POST-PILOT HARDENING"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert success

    task2 = {"instruction": "x", "edge_name": "POST_PILOT_HARDENING"}
    res_task2, success2, blocker2 = execute_task(task2, "ledger.json", {})
    assert success2

def test_pilot_intake_returns_false_without_verification():
    task = {"instruction": "x", "edge_name": "PILOT INTAKE"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert not success
    assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_PILOT INTAKE"

    task2 = {"instruction": "x", "edge_name": "PILOT_INTAKE"}
    res_task2, success2, blocker2 = execute_task(task2, "ledger.json", {})
    assert not success2
    assert blocker2 == "UNVERIFIED_EXTERNAL_EFFECT_PILOT_INTAKE"

def test_pr41_acceptance_fails_closed_when_unmerged():
    task = {"instruction": "x", "edge_name": "PR41 ACCEPTANCE"}
    with patch("subprocess.check_output", side_effect=Exception("not ancestor")):
        res_task, success, blocker = execute_task(task, "ledger.json", {})
        assert not success
        assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_PR41 ACCEPTANCE"

def test_ledger_handoff_fails_closed_when_ledger_missing():
    task = {"instruction": "x", "edge_name": "LEDGER/HANDOFF"}
    res_task, success, blocker = execute_task(task, "non_existent_ledger.json", {})
    assert not success
    assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_LEDGER/HANDOFF"

def test_generic_fallback_fails_closed():
    task = {"instruction": "x", "edge_name": "ARBITRARY_TASK_NAME"}
    res_task, success, blocker = execute_task(task, "ledger.json", {})
    assert not success
    assert blocker == "UNRECOGNIZED_OR_UNVERIFIED_TASK_ARBITRARY_TASK_NAME"
