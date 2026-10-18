"""Red-Team R1 F3: an existing but unreadable (empty/torn) lease must fail closed.

The O_EXCL create and the payload write are two steps; in between the lease
file exists but is empty. It must never be treated as expired/reclaimable.
"""
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.resource_policy import TaskLeaseManager


@pytest.mark.parametrize("raw", [b"", b'{"owner_id": "A", "expires_at": 1e18'])
def test_task_lease_unreadable_file_is_not_reclaimed(tmp_path, raw):
    m = TaskLeaseManager(repo_dir=tmp_path)
    m._get_lease_path("t").write_bytes(raw)
    ok, reason, _ = m.acquire_lease("t", "h", "B")
    assert ok is False
    assert reason == "LEASE_UNREADABLE_FAIL_CLOSED"
    # the unreadable file is left for its holder, not overwritten
    assert m._get_lease_path("t").read_bytes() == raw


def test_expired_readable_lease_is_still_reclaimed(tmp_path):
    m = TaskLeaseManager(repo_dir=tmp_path)
    m._get_lease_path("t").write_text('{"owner_id": "A", "task_hash": "h", "expires_at": 0}')
    ok, reason, _ = m.acquire_lease("t", "h", "B")
    assert ok is True
    assert reason == "LEASE_RECLAIMED_EXPIRED"
