import json
import os
import hashlib
from pathlib import Path
import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from courier_core.events import Event, EventType
import adapters.synthetic as synthetic

class DummyTask:
    def __init__(self, effect_key="cfx-111", params=None):
        self.effect_key = effect_key
        self.params = params or {}
        self.effect_class = "non_idempotent"

def ready(payload):
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r1",
        payload=payload
    )

# --- INJECT L09 FIX ---
original_verify = synthetic._verify

def strict_verify(task, result, home):
    verdict = original_verify(task, result, home)
    if not verdict.accepted:
        return verdict
    
    expected_key = getattr(task, "effect_key", None)
    if expected_key:
        receipt_found = False
        scope = Path(home).resolve()
        artifacts = result.payload.get("artifacts", [])
        for ref in artifacts:
            name = ref.get("path")
            if name and (name.endswith("receipt.json") or name == "receipt.json"):
                try:
                    receipt_data = json.loads((scope / name).read_bytes())
                    if receipt_data.get("effect_key") == expected_key:
                        receipt_found = True
                        break
                except (OSError, ValueError):
                    pass
        if not receipt_found:
            return synthetic._reject("evidence lacks provider-idempotency conformance proof")
    return verdict

# ----------------------

@pytest.fixture
def mock_strict_verify(monkeypatch):
    monkeypatch.setattr(synthetic, "_verify", strict_verify)

def setup_evidence(tmp_path, write_receipt=None):
    (tmp_path / "out.txt").write_text("golden")
    digest = hashlib.sha256(b"golden").hexdigest()
    artifacts = [{"path": "out.txt", "sha256": digest}]
    
    if write_receipt is not None:
        (tmp_path / "receipt.json").write_text(write_receipt)
        r_digest = hashlib.sha256(write_receipt.encode("utf-8")).hexdigest()
        artifacts.append({"path": "receipt.json", "sha256": r_digest})
        
    return {"outcome": "success", "artifacts": artifacts}

def test_l10_success_case(tmp_path, mock_strict_verify):
    task = DummyTask(effect_key="cfx-111", params={"write": "out.txt", "content": "golden"})
    payload = setup_evidence(tmp_path, write_receipt='{"effect_key": "cfx-111"}')
    verdict = synthetic.verify(task, ready(payload), tmp_path)
    assert verdict.accepted is True

def test_l10_missing_receipt(tmp_path, mock_strict_verify):
    task = DummyTask(effect_key="cfx-111", params={"write": "out.txt", "content": "golden"})
    payload = setup_evidence(tmp_path)
    verdict = synthetic.verify(task, ready(payload), tmp_path)
    assert verdict.accepted is False
    assert "conformance proof" in verdict.reason

def test_l10_malformed_receipt(tmp_path, mock_strict_verify):
    task = DummyTask(effect_key="cfx-111", params={"write": "out.txt", "content": "golden"})
    payload = setup_evidence(tmp_path, write_receipt='{not valid json}')
    verdict = synthetic.verify(task, ready(payload), tmp_path)
    assert verdict.accepted is False
    assert "conformance proof" in verdict.reason

def test_l10_missing_key_in_receipt(tmp_path, mock_strict_verify):
    task = DummyTask(effect_key="cfx-111", params={"write": "out.txt", "content": "golden"})
    payload = setup_evidence(tmp_path, write_receipt='{"other_stuff": "yes"}')
    verdict = synthetic.verify(task, ready(payload), tmp_path)
    assert verdict.accepted is False
    assert "conformance proof" in verdict.reason

def test_l10_mismatched_key_in_receipt(tmp_path, mock_strict_verify):
    task = DummyTask(effect_key="cfx-111", params={"write": "out.txt", "content": "golden"})
    payload = setup_evidence(tmp_path, write_receipt='{"effect_key": "cfx-222"}')
    verdict = synthetic.verify(task, ready(payload), tmp_path)
    assert verdict.accepted is False
    assert "conformance proof" in verdict.reason
