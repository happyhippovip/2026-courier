import pytest
import json
from courier_core.recovery_receipt import RecoveryReceipt

def valid_receipt_kwargs():
    return {
        "incident_id": "inc-123",
        "workkey": "R01",
        "host": "mac-node-01",
        "last_accepted_state": "VERIFYING",
        "failure_type": "KERNEL_PANIC",
        "surviving_work": ["/tmp/work/1.txt", "/tmp/work/2.txt"],
        "recovery_action": "ABORT_AND_CLEAR",
        "recovery_result": "SUCCESS",
        "evidence_refs": ["/logs/crash.log"],
        "safe_resume_point": "START",
        "data_loss_state": "NONE",
        "timestamp": "2026-10-02T12:00:00.000Z"
    }

def test_recovery_receipt_creation_and_validation():
    receipt = RecoveryReceipt(**valid_receipt_kwargs())
    receipt.validate() # Should not raise
    
    assert receipt.incident_id == "inc-123"
    assert receipt.data_loss_state == "NONE"

def test_recovery_receipt_serialization_roundtrip():
    original = RecoveryReceipt(**valid_receipt_kwargs())
    json_str = original.to_json()
    
    recovered = RecoveryReceipt.from_json(json_str)
    assert original == recovered
    assert recovered.surviving_work == ["/tmp/work/1.txt", "/tmp/work/2.txt"]

def test_recovery_receipt_missing_required_fields():
    kwargs = valid_receipt_kwargs()
    kwargs["incident_id"] = ""
    receipt = RecoveryReceipt(**kwargs)
    with pytest.raises(ValueError, match="incident_id is required"):
        receipt.validate()

def test_recovery_receipt_invalid_enums():
    kwargs = valid_receipt_kwargs()
    kwargs["data_loss_state"] = "INVALID_STATE"
    receipt = RecoveryReceipt(**kwargs)
    with pytest.raises(ValueError, match="data_loss_state must be one of"):
        receipt.validate()
        
    kwargs = valid_receipt_kwargs()
    kwargs["recovery_result"] = "PENDING"
    receipt = RecoveryReceipt(**kwargs)
    with pytest.raises(ValueError, match="recovery_result must be one of"):
        receipt.validate()

def test_recovery_receipt_type_validation():
    kwargs = valid_receipt_kwargs()
    kwargs["surviving_work"] = "not_a_list"
    receipt = RecoveryReceipt(**kwargs)
    with pytest.raises(TypeError, match="surviving_work must be a list"):
        receipt.validate()

def test_recovery_receipt_canonical_json():
    receipt = RecoveryReceipt(**valid_receipt_kwargs())
    json_str = receipt.to_json()
    assert " " not in json_str # check separators=(',', ':')
    # Validate keys are sorted
    parsed = json.loads(json_str)
    keys = list(parsed.keys())
    assert keys == sorted(keys)

def test_recovery_receipt_atomic_write(tmp_path):
    receipt = RecoveryReceipt(**valid_receipt_kwargs())
    file_path = tmp_path / "receipt.json"
    
    receipt.write_atomic(str(file_path))
    
    assert file_path.exists()
    
    # Read it back
    content = file_path.read_text(encoding="utf-8")
    recovered = RecoveryReceipt.from_json(content)
    assert recovered == receipt
