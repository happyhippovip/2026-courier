import pytest
import os
import sys
import json
from unittest import mock
import getpass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import human_gate_ux

@pytest.fixture
def gate_payload(tmp_path):
    f = tmp_path / "gate_payload.json"
    f.write_text(json.dumps({
        "action": "DELETE_DATABASE",
        "artifacts": ["db1", "db2"],
        "reason": "Security breach"
    }))
    return str(f)

def test_run_human_gate_approve(gate_payload, tmp_path, capsys):
    with mock.patch("builtins.input", return_value="APPROVE"):
        with pytest.raises(SystemExit) as excinfo:
            human_gate_ux.run_human_gate(gate_payload)
        assert excinfo.value.code == 0
            
    captured = capsys.readouterr()
    assert "ACTION PROPOSED:  DELETE_DATABASE" in captured.out
    assert "Action APPROVED" in captured.out
    
    # Check approval record
    record_file = f"{gate_payload}.approval"
    assert os.path.exists(record_file)
    with open(record_file, 'r') as f:
        record = json.load(f)
        assert record["status"] == "APPROVED"
        assert record["action"] == "DELETE_DATABASE"
        assert record["identity"] == getpass.getuser()

def test_run_human_gate_reject(gate_payload, capsys):
    with mock.patch("builtins.input", return_value="REJECT"):
        with pytest.raises(SystemExit) as excinfo:
            human_gate_ux.run_human_gate(gate_payload)
        assert excinfo.value.code == 1
            
    captured = capsys.readouterr()
    assert "Action REJECTED" in captured.out
    
    record_file = f"{gate_payload}.approval"
    assert not os.path.exists(record_file)

def test_run_human_gate_invalid_then_approve(gate_payload, capsys):
    # Multiple inputs: invalid, then approve
    with mock.patch("builtins.input", side_effect=["MAYBE", "APPROVE"]):
        with pytest.raises(SystemExit) as excinfo:
            human_gate_ux.run_human_gate(gate_payload)
        assert excinfo.value.code == 0
            
    captured = capsys.readouterr()
    assert "Please type 'APPROVE' or 'REJECT'" in captured.out
    assert "Action APPROVED" in captured.out

def test_run_human_gate_eof(gate_payload, capsys):
    with mock.patch("builtins.input", side_effect=EOFError):
        with pytest.raises(SystemExit) as excinfo:
            human_gate_ux.run_human_gate(gate_payload)
        assert excinfo.value.code == 1
            
    captured = capsys.readouterr()
    assert "Non-interactive environment detected" in captured.out

