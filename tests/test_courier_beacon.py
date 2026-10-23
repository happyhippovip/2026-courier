import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure we can import courier_beacon by adding scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from scripts.courier_beacon import (
    fetch_metrics,
    halt_system,
    get_bodyguard_invocations,
    main,
    API_URL,
    HEADERS
)

def test_fetch_metrics_success():
    with patch("scripts.courier_beacon.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"active_tasks": 5}
        mock_get.return_value = mock_resp
        
        result = fetch_metrics()
        assert result == {"active_tasks": 5}
        mock_get.assert_called_once_with(f"{API_URL}/system/metrics", headers=HEADERS, timeout=5)

def test_fetch_metrics_error():
    with patch("scripts.courier_beacon.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp
        
        result = fetch_metrics()
        assert result is None

def test_fetch_metrics_exception():
    with patch("scripts.courier_beacon.requests.get", side_effect=Exception("Timeout")):
        result = fetch_metrics()
        assert result is None

def test_halt_system_success(capsys):
    with patch("scripts.courier_beacon.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        
        halt_system("Too expensive")
        
        mock_post.assert_called_once_with(
            f"{API_URL}/system/halt",
            json={"reason": "Too expensive"},
            headers=HEADERS,
            timeout=5
        )
        
        out = capsys.readouterr().out
        assert "HALTING SYSTEM: Too expensive" in out
        assert "System successfully halted at control plane." in out

def test_halt_system_failure(capsys):
    with patch("scripts.courier_beacon.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_post.return_value = mock_resp
        
        halt_system("Too expensive")
        
        out = capsys.readouterr().out
        assert "Failed to halt system: Internal Server Error" in out

def test_halt_system_exception(capsys):
    with patch("scripts.courier_beacon.requests.post", side_effect=Exception("Connection refused")):
        halt_system("Too expensive")
        
        out = capsys.readouterr().out
        assert "Failed to issue halt to API: Connection refused" in out

def test_get_bodyguard_invocations_no_dir():
    with patch("scripts.courier_beacon.Path.exists", return_value=False):
        assert get_bodyguard_invocations() == 0

def test_get_bodyguard_invocations_success(tmp_path):
    states_dir = tmp_path / "events" / "agent-states"
    states_dir.mkdir(parents=True)
    
    (states_dir / "state1.json").write_text(json.dumps({"model_calls_incurred": 10}), encoding="utf-8")
    (states_dir / "state2.json").write_text(json.dumps({"model_calls_incurred": 5}), encoding="utf-8")
    (states_dir / "state3.json").write_text("invalid json", encoding="utf-8")
    
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        invocations = get_bodyguard_invocations()
        assert invocations == 15
    finally:
        os.chdir(old_cwd)


def test_state_files_do_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "a.json").write_text(json.dumps({"model_calls_incurred": 9}), encoding="utf-8")
    dir_root = tmp_path / "dir-case"
    (dir_root / "events").mkdir(parents=True)
    (dir_root / "events" / "agent-states").symlink_to(outside)

    file_outside = tmp_path / "file-outside.json"
    file_outside.write_text(json.dumps({"model_calls_incurred": 4}), encoding="utf-8")
    file_root = tmp_path / "file-case"
    states = file_root / "events" / "agent-states"
    states.mkdir(parents=True)
    (states / "b.json").symlink_to(file_outside)
    (states / "ok.json").write_text(json.dumps({"model_calls_incurred": 2}), encoding="utf-8")

    def run(root):
        old = os.getcwd()
        try:
            os.chdir(root)
            try:
                return get_bodyguard_invocations(), None
            except ValueError as exc:
                return None, str(exc)
        finally:
            os.chdir(old)

    dir_count, dir_err = run(dir_root)
    file_count, file_err = run(file_root)
    refused = "refusing to follow a symlink"
    assert (
        dir_err == refused and dir_count is None
        and file_err == refused and file_count is None
        and json.loads((outside / "a.json").read_text())["model_calls_incurred"] == 9
        and (dir_root / "events" / "agent-states").is_symlink()
        and (states / "b.json").is_symlink()
    ), (dir_count, dir_err, file_count, file_err)


def test_bool_model_calls_are_not_a_count(tmp_path):
    def plant(name, value):
        root = tmp_path / name
        states = root / "events" / "agent-states"
        states.mkdir(parents=True)
        (states / "a.json").write_text(
            json.dumps({"model_calls_incurred": value}), encoding="utf-8",
        )
        old = os.getcwd()
        try:
            os.chdir(root)
            try:
                return get_bodyguard_invocations(), None
            except ValueError as exc:
                return None, str(exc)
        finally:
            os.chdir(old)

    true_count, true_err = plant("true-case", True)
    false_count, false_err = plant("false-case", False)
    num_count, num_err = plant("num-case", 2)
    refused = "Bool is not a number."
    assert (
        true_err == refused and true_count is None
        and false_err == refused and false_count is None
        and num_err is None and num_count == 2
    ), (true_count, true_err, false_count, false_err, num_count, num_err)

def test_float_model_calls_are_not_a_count(tmp_path):
    def plant(name, value):
        root = tmp_path / name
        states = root / "events" / "agent-states"
        states.mkdir(parents=True)
        (states / "a.json").write_text(
            json.dumps({"model_calls_incurred": value}), encoding="utf-8",
        )
        old = os.getcwd()
        try:
            os.chdir(root)
            try:
                return get_bodyguard_invocations(), None
            except ValueError as exc:
                return None, str(exc)
        finally:
            os.chdir(old)

    one_count, one_err = plant("one-case", 1.0)
    half_count, half_err = plant("half-case", 1.5)
    num_count, num_err = plant("int-case", 2)
    refused = "Count must be an int."
    assert (
        one_err == refused and one_count is None
        and half_err == refused and half_count is None
        and num_err is None and num_count == 2
    ), (one_count, one_err, half_count, half_err, num_count, num_err)

def test_main_already_halted(capsys):
    with patch("scripts.courier_beacon.fetch_metrics", return_value={"system_halted": True, "halt_reason": "Admin request"}), \
         patch("scripts.courier_beacon.time.sleep", side_effect=KeyboardInterrupt):
        
        try:
            main()
        except KeyboardInterrupt:
            pass
            
        out = capsys.readouterr().out
        assert "[BEACON] SYSTEM IS HALTED. Reason: Admin request" in out

def test_main_safe(capsys):
    with patch("scripts.courier_beacon.fetch_metrics", return_value={"active_tasks": 2}), \
         patch("scripts.courier_beacon.get_bodyguard_invocations", return_value=100), \
         patch("scripts.courier_beacon.verify_safety", return_value=(True, "Safe")), \
         patch("scripts.courier_beacon.time.sleep", side_effect=KeyboardInterrupt):
        
        try:
            main()
        except KeyboardInterrupt:
            pass
            
        out = capsys.readouterr().out
        assert "[BEACON] Cost: $1.00 | Invocations: 100 | Active Tasks: 2" in out

def test_main_unsafe(capsys):
    with patch("scripts.courier_beacon.fetch_metrics", return_value={"active_tasks": 1}), \
         patch("scripts.courier_beacon.get_bodyguard_invocations", return_value=500), \
         patch("scripts.courier_beacon.verify_safety", return_value=(False, "Cost exceeded")), \
         patch("scripts.courier_beacon.halt_system") as mock_halt, \
         patch("scripts.courier_beacon.time.sleep", side_effect=KeyboardInterrupt):
        
        try:
            main()
        except KeyboardInterrupt:
            pass
            
        mock_halt.assert_called_once_with("Cost exceeded")
        out = capsys.readouterr().out
        assert "[BEACON] Cost: $5.00 | Invocations: 500 | Active Tasks: 1" in out

def test_main_fetch_failed(capsys):
    with patch("scripts.courier_beacon.fetch_metrics", return_value=None), \
         patch("scripts.courier_beacon.time.sleep", side_effect=KeyboardInterrupt):
        
        try:
            main()
        except KeyboardInterrupt:
            pass
            
        out = capsys.readouterr().out
        assert "[BEACON] Failed to fetch metrics from Courier server." in out
