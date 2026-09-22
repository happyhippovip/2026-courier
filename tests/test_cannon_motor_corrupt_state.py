"""CannonMotor._load() must name the corrupt file so recovery can find it.

Corrupt backend truth stays a loud json.JSONDecodeError (never a silent
fresh IDLE that would discard durable executions); the message additionally
carries the motor.json path. Each test uses an isolated tmp state dir.
"""
import json

import pytest

from scripts.cannon_motor import CannonMotor


def test_corrupt_motor_json_error_names_path(tmp_path):
    bad = tmp_path / "motor.json"
    bad.write_text('{"state": "RUNN', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as excinfo:
        CannonMotor(tmp_path)
    assert str(bad) in str(excinfo.value)
    assert excinfo.value.doc == '{"state": "RUNN'


def test_missing_motor_json_initializes_idle(tmp_path):
    motor = CannonMotor(tmp_path)
    assert motor.state == "IDLE"
    assert json.loads((tmp_path / "motor.json").read_text(encoding="utf-8"))["state"] == "IDLE"


def test_valid_motor_json_loads(tmp_path):
    (tmp_path / "motor.json").write_text('{"state": "PAUSED", "custom": 1}', encoding="utf-8")
    motor = CannonMotor(tmp_path)
    assert motor.m == {"state": "PAUSED", "custom": 1}
