"""load_bundle() must name the corrupt ledger file so recovery can find it.

The corrupt-JSON failure stays a fail-closed StorageError (never an empty
or default bundle); the message additionally carries the ledger path.
"""
from scripts.agent_handoff_ledger import StorageError, load_bundle


def test_corrupt_ledger_error_names_path(tmp_path):
    bad = tmp_path / "agent_handoff_ledger.json"
    bad.write_text('{"revision": 0, "BROKEN', encoding="utf-8")
    try:
        load_bundle(bad)
    except StorageError as exc:
        assert "corrupt JSON" in str(exc)
        assert str(bad) in str(exc)
    else:
        raise AssertionError("corrupt ledger did not fail closed")


def test_corrupt_ledger_keeps_json_detail(tmp_path):
    bad = tmp_path / "ledger.json"
    bad.write_text("{", encoding="utf-8")
    try:
        load_bundle(bad)
    except StorageError as exc:
        assert exc.__cause__ is not None
        assert "corrupt JSON" in str(exc)
    else:
        raise AssertionError("corrupt ledger did not fail closed")
