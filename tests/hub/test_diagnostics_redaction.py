"""Support diagnostics keep the failure and the ids, and hide credentials.

Synthetic strings only. Nothing here reads a real home directory or writes a log.
"""

from courier_hub.diagnostics import diagnostic_evidence_name, redact_diagnostics_text
from courier_hub.model import receipt, support

_TOKEN = "ghp_fakecourierTOKEN9999abcd"
_PASSWORD = "p@ssw0rd"
_WIN_PATH = r"C:\Users\Alice\Documents\taxes-2026.pdf"
_POSIX_PATH = "/home/alice/Documents/taxes-2026.pdf"
_TASK = "task-diag-018"
_DISPATCH = "disp-018"
_WORKER = "worker-018"
_RESULT = "r-018"


def _task():
    return {
        "task_id": _TASK,
        "status": "FAILED",
        "adapter": "synthetic",
        "params": {"title": f"read {_WIN_PATH}"},
        "effect_class": "idempotent",
        "attempt": 1,
        "dispatch_id": _DISPATCH,
        "worker_id": _WORKER,
        "resolution": None,
        "decided_by": None,
        "late_results": 0,
        "last_reason": (
            f"PermissionError reading {_WIN_PATH} "
            f"(password={_PASSWORD} api_key=abcd+fakecourierLEAK Bearer {_TOKEN})"
        ),
    }


def _events():
    return [
        {
            "seq": 4,
            "type": "TASK_FAILED",
            "attempt": 1,
            "dispatch_id": _DISPATCH,
            "result_id": _RESULT,
            "task_id": _TASK,
            "ts_utc": "2026-10-11T00:00:00Z",
            "hash": "hash-failed-018",
            "payload": {},
        },
        {
            "seq": 3,
            "type": "RESULT_READY",
            "attempt": 1,
            "dispatch_id": _DISPATCH,
            "result_id": _RESULT,
            "task_id": _TASK,
            "ts_utc": "2026-10-11T00:00:01Z",
            "hash": "hash-ready-018",
            "payload": {
                "artifacts": [
                    {"path": _WIN_PATH},
                    {"path": "artifacts/disp-018/report.pdf"},
                ]
            },
        },
        {
            "seq": 5,
            "type": "EFFECT_CONFIRMED",
            "attempt": 1,
            "dispatch_id": _DISPATCH,
            "result_id": None,
            "task_id": _TASK,
            "ts_utc": "2026-10-11T00:00:02Z",
            "hash": "hash-decision-018",
            "payload": {"actor": "desktop:tester", "reason": f"note mentioned {_POSIX_PATH}"},
        },
    ]


def test_synthetic_secrets_and_user_paths_are_masked_without_erasing_the_cause():
    reason = redact_diagnostics_text(_task()["last_reason"])
    assert _PASSWORD not in reason
    assert _TOKEN not in reason
    assert "abcd+fakecourierLEAK" not in reason
    assert "Alice" not in reason
    assert "PermissionError" in reason
    assert "<HOME>/Documents/taxes-2026.pdf" in reason
    assert "password=***REDACTED***" in reason

    posix = redact_diagnostics_text(f"failed {_POSIX_PATH}")
    assert "alice" not in posix
    assert posix == "failed <HOME>/Documents/taxes-2026.pdf"

    # A non-profile path is evidence, not a secret.
    assert redact_diagnostics_text("kept /tmp/inbox") == "kept /tmp/inbox"
    assert redact_diagnostics_text("I saw the file") == "I saw the file"
    # The same filter again does not eat the redacted text or the path.
    assert redact_diagnostics_text(reason) == reason
    assert redact_diagnostics_text(posix) == posix


def test_support_record_keeps_controller_worker_ids_and_survives_replay():
    task, events = _task(), _events()
    record = support(task, events)
    body = record["task"]["last_reason"]
    assert _PASSWORD not in body and _TOKEN not in body and "Alice" not in body
    assert "PermissionError" in body
    assert body.count("<HOME>/Documents/taxes-2026.pdf") == 1

    assert body and record["task"]["task_id"] == _TASK
    assert record["task"]["dispatch_id"] == _DISPATCH
    assert record["task"]["worker_id"] == _WORKER
    assert record["task"]["late_results"] == 0
    failed = record["events"][0]
    assert failed["type"] == "TASK_FAILED"
    assert failed["seq"] == 4
    assert failed["dispatch_id"] == record["task"]["dispatch_id"]
    assert failed["hash"] == "hash-failed-018"
    assert all(event["dispatch_id"] == _DISPATCH for event in record["events"])

    # A restart reads the same journal rows again. The package does not depend
    # on process memory, so the second read matches the first.
    replayed = support(dict(task), [dict(event) for event in events])
    assert replayed == record


def test_receipt_in_the_support_package_redacts_paths_and_keeps_file_names():
    shown = receipt(_task(), _events())
    rendered = str(shown)
    assert _PASSWORD not in rendered
    assert "Alice" not in rendered
    assert "alice" not in rendered
    assert "<HOME>/Documents/taxes-2026.pdf" in shown["understood"]
    assert "write the test file" in shown["understood"]
    names = [item["name"] for item in shown["evidence"]]
    assert names == ["<HOME>/Documents/taxes-2026.pdf", "report.pdf"]
    assert shown["decisions"][0]["who"] == "tester"
    assert shown["decisions"][0]["reason"] == "note mentioned <HOME>/Documents/taxes-2026.pdf"
    assert shown["happened"] == "Couldn't complete this safely"
    assert receipt(_task(), _events()) == shown


def test_evidence_name_contract():
    assert diagnostic_evidence_name(_WIN_PATH) == "<HOME>/Documents/taxes-2026.pdf"
    assert diagnostic_evidence_name(r"D:\work\report.pdf") == "report.pdf"
    assert diagnostic_evidence_name("artifacts/disp-018/report.pdf") == "report.pdf"
    assert diagnostic_evidence_name(f"/Users/alice/Library/Application Support/{_TOKEN}.log") == (
        "<HOME>/Library/Application Support/***REDACTED***.log"
    )
