"""Contract: duplicate/conflicting second results at task_result (priority 1/2).

Pins server/app.py task_result() duplicate protection:
- identical resend to a terminal task -> ACK_DUPLICATE (resend, never reexecute)
- contradictory payload to a terminal task -> 409 CONTRADICTORY_DUPLICATE
- the identical-check binds result_id (not just task_id)

Static AST pin (same convention as test_server_infinite_retry.py):
no Flask harness exists in this repo, and importing server.app has
module-level side effects.
"""
import ast
from pathlib import Path


def _task_result_fn():
    tree = ast.parse(Path("server/app.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "task_result":
            return node
    raise AssertionError("task_result() not found in server/app.py")


def _src(func):
    lines = Path("server/app.py").read_text().splitlines()
    start = func.lineno - 1
    end = func.end_lineno
    return "\n".join(lines[start:end])


def test_identical_resend_acknowledged():
    src = _src(_task_result_fn())
    assert "ACK_DUPLICATE" in src, "identical resends must be ACKed, never reexecuted"


def test_contradictory_duplicate_rejected():
    src = _src(_task_result_fn())
    assert "CONTRADICTORY_DUPLICATE" in src, "conflicting second results must be rejected"
    assert "409" in src, "conflict must surface as HTTP 409"


def test_identical_check_binds_result_id():
    src = _src(_task_result_fn())
    for field in ("result_id", "worker_id", "artifacts"):
        assert field in src, f"identical-check must bind {field}"
