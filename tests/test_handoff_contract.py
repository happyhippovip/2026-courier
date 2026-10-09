"""Contract for Courier agent-handoff records (false human-gate family).

A stuck or restarted agent window must be disposable: a fresh worker resumes
from ``handoffs/*.json``. That only works if every record parses and declares
who it is and what state it is in. This suite enforces parseability
repo-wide and proves the identity/state validator with fixtures.

Three key conventions exist in the wild and all are accepted:
- lowercase: ``workkey`` + ``status`` (+ ``window``)
- UPPER: ``WORKKEY`` + ``CURRENT_STATE``
- review-checkpoint: ``unit`` + ``status`` (this session's ``pr*.json`` family)

Scope (deliberate): the identity/state validator below is proven by the
inline fixtures. The repository-wide test only pins what every window
already owes every other window — that each record parses as a JSON
object. Peer windows' records predate any shared identity convention
(e.g. ``dep_*``/``l3_*`` carry ``WORKKEY`` with no state key) and are
owned by those windows, so this suite must not fail on their key
choices. Promoting identity/state to a repo-wide gate is an L1
convention decision; until then, records that adopt the contract
(the ``pr*.json`` family and this session's aggregates) conform to it
voluntarily. A missing ``handoffs/`` directory passes vacuously.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HANDOFFS_DIR = ROOT / "handoffs"

IDENTITY_KEYS = ("workkey", "WORKKEY", "unit")
STATE_KEYS = ("status", "CURRENT_STATE")


def load_handoff_record(path: Path) -> dict:
    """Parse one handoff record; raise AssertionError when unusable."""
    try:
        record = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssertionError(f"{path.name}: not valid JSON ({exc})")
    if not isinstance(record, dict):
        raise AssertionError(f"{path.name}: top level must be an object")
    return record


def handoff_identity(record: dict, name: str) -> str:
    for key in IDENTITY_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise AssertionError(f"{name}: needs identity key {IDENTITY_KEYS}")


def handoff_state(record: dict, name: str) -> str:
    for key in STATE_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise AssertionError(f"{name}: needs state key {STATE_KEYS}")


def check_record(path: Path) -> tuple[str, str]:
    record = load_handoff_record(path)
    return handoff_identity(record, path.name), handoff_state(record, path.name)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


def test_fixture_lowercase_convention(tmp_path):
    path = _write(tmp_path, "a.json", '{"workkey": "K-1", "status": "done"}')
    assert check_record(path) == ("K-1", "done")


def test_fixture_uppercase_convention(tmp_path):
    path = _write(tmp_path, "b.json", '{"WORKKEY": "K-2", "CURRENT_STATE": "FINAL"}')
    assert check_record(path) == ("K-2", "FINAL")


def test_fixture_unit_convention(tmp_path):
    path = _write(tmp_path, "g.json", '{"unit": "REVIEW-L2-245", "status": "DONE"}')
    assert check_record(path) == ("REVIEW-L2-245", "DONE")


def test_fixture_missing_identity_fails(tmp_path):
    path = _write(tmp_path, "c.json", '{"status": "done"}')
    with pytest.raises(AssertionError, match="identity"):
        check_record(path)


def test_fixture_missing_state_fails(tmp_path):
    path = _write(tmp_path, "d.json", '{"workkey": "K-4"}')
    with pytest.raises(AssertionError, match="state"):
        check_record(path)


def test_fixture_invalid_json_fails(tmp_path):
    path = _write(tmp_path, "e.json", "{not json")
    with pytest.raises(AssertionError, match="not valid JSON"):
        check_record(path)


def test_fixture_non_object_fails(tmp_path):
    path = _write(tmp_path, "f.json", '["workkey"]')
    with pytest.raises(AssertionError, match="object"):
        check_record(path)


def test_repository_handoffs_parse_as_objects():
    """Every handoff record must be parseable JSON with an object top level.

    Convention-neutral by design (see module docstring): peer windows own
    their key choices. Identity/state enforcement lives in the validator
    above, proven by the fixtures.
    """
    if not HANDOFFS_DIR.is_dir():
        return
    records = sorted(HANDOFFS_DIR.glob("*.json"))
    if not records:
        return
    for path in records:
        load_handoff_record(path)
