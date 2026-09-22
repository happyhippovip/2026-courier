"""storage.read() must name the corrupt file so recovery can find it.

Corrupt durable state stays a loud json.JSONDecodeError (never an empty
queue); the message additionally carries the file path.
"""
import json

import pytest

from app.cannon.storage import read


def test_corrupt_file_error_names_path(tmp_path):
    bad = tmp_path / "controller.json"
    bad.write_text('{"tasks": [TRUNCATED', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as excinfo:
        read(bad)
    assert str(bad) in str(excinfo.value)


def test_corrupt_file_keeps_decode_position(tmp_path):
    bad = tmp_path / "event.json"
    bad.write_text("not json at all", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as excinfo:
        read(bad)
    assert excinfo.value.doc == "not json at all"
    assert excinfo.value.pos == 0


def test_missing_file_returns_default(tmp_path):
    assert read(tmp_path / "absent.json") is None
    assert read(tmp_path / "absent.json", {"empty": True}) == {"empty": True}


def test_valid_file_still_reads(tmp_path):
    good = tmp_path / "ok.json"
    good.write_text('{"a": 1}', encoding="utf-8")
    assert read(good) == {"a": 1}
