"""PRE_CODEX_READY is a ledger decision, not a self-report.

A caller-supplied narrative, including one labeled PYTEST, is not execution
proof. The gate may accept the shape of a report file and must still refuse
the product claim.
"""
import json
from pathlib import Path

import scripts.pilot_gate_readiness_check as gate


SHA_A = "a" * 40
SHA_B = "b" * 40


def _report(path: Path, *, sha=SHA_A, source="PYTEST", failed=0, skipped=0, passed=2):
    path.write_text(json.dumps({
        "source": source,
        "final_sha": sha,
        "summary": {"failed": failed, "skipped": skipped, "passed": passed},
    }), encoding="utf-8")
    return path


def _files(root: Path):
    ops = root / "ops" / "ai"
    ops.mkdir(parents=True)
    (ops / "PRE_CODEX_HANDOFF.md").write_text("handoff\n", encoding="utf-8")
    (ops / "PROOF_CARD.md").write_text("card\n", encoding="utf-8")
    (ops / "PILOT_DUMMY_TASK.json").write_text("{}\n", encoding="utf-8")


def test_hardcoded_metrics_are_not_a_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))
    _files(tmp_path)
    code = gate.check_pilot_gate_readiness()
    body = json.loads(capsys.readouterr().out)
    assert code == 1
    assert body["status"] == "BLOCKED"
    assert body["prerequisites"]["PRE_CODEX_HANDOFF"] is True
    assert body["prerequisites"]["TARGETED_TESTS_GREEN"] is False
    for metric in body["metrics"].values():
        assert metric["status"] == "NOT_PROVEN"
        assert metric["actual"] is None
    assert body["pre_codex"]["claim_allowed"] is False
    assert body["pre_codex"]["status"] == "NOT_READY"


def test_self_report_is_rejected(tmp_path):
    report = _report(tmp_path / "report.json", source="SELF_REPORT")
    decision = gate.evaluate_pre_codex_ready(report, expected_sha=SHA_A)
    assert decision["receipt_shape"] == "REJECTED"
    assert decision["claim_allowed"] is False
    assert decision["status"] == "NOT_READY"
    assert any("source" in reason for reason in decision["blockers"])


def test_stale_sha_skipped_and_failures_are_rejected(tmp_path):
    stale = _report(tmp_path / "stale.json", sha=SHA_B)
    skipped = _report(tmp_path / "skipped.json", skipped=1)
    failed = _report(tmp_path / "failed.json", failed=1)
    assert gate.evaluate_pre_codex_ready(stale, expected_sha=SHA_A)["receipt_shape"] == "REJECTED"
    assert gate.evaluate_pre_codex_ready(skipped, expected_sha=SHA_A)["receipt_shape"] == "REJECTED"
    assert gate.evaluate_pre_codex_ready(failed, expected_sha=SHA_A)["receipt_shape"] == "REJECTED"
    missing = gate.evaluate_pre_codex_ready(tmp_path / "absent.json", expected_sha=SHA_A)
    assert missing["receipt_shape"] == "REJECTED"
    assert missing["claim_allowed"] is False


def test_consistent_report_still_does_not_claim_ready(tmp_path):
    report = _report(tmp_path / "report.json")
    decision = gate.evaluate_pre_codex_ready(report, expected_sha=SHA_A)
    assert decision["receipt_shape"] == "OK"
    assert decision["status"] == "NOT_READY"
    assert decision["claim_allowed"] is False
    assert decision["final_sha"] == SHA_A


def test_receipt_reloads_and_duplicate_event_is_not_replayed(tmp_path):
    report = _report(tmp_path / "report.json")
    decision = gate.evaluate_pre_codex_ready(report, expected_sha=SHA_A)
    ledger = tmp_path / "pre_codex.jsonl"
    receipt = {"event_id": "evt-2876", "decision": decision}
    assert gate.append_pre_codex_receipt(ledger, receipt) is True
    assert gate.append_pre_codex_receipt(ledger, dict(receipt)) is False
    reloaded = gate.load_pre_codex_receipts(ledger)
    assert len(reloaded) == 1
    assert reloaded[0]["decision"] == decision
    assert reloaded[0]["decision"]["claim_allowed"] is False
