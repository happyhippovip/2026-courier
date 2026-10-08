import json
from pathlib import Path
import pytest

from courier_runtime.home_agent import (
    ACCESS_ORDER,
    CATALOG,
    HomeAgent,
    LocalGrants,
    default_handlers,
    submit,
    why_refused,
)


class TestHomeAgentExtended:
    """Rigorous edge-case coverage for HomeAgent mailbox coordination and security fences."""

    def test_catalog_access_levels_conformance(self):
        # Every catalog item must have a level that exists in ACCESS_ORDER
        for action, (level, desc) in CATALOG.items():
            assert level in ACCESS_ORDER
            assert len(desc) > 0

    def test_why_refused_prohibits_all_command_variants(self):
        g = LocalGrants(max_access="control", allowed_actions=frozenset({"host_health"}))
        # Any attempt to smuggle arbitrary execution parameters must be refused
        for poison_key in ["argv", "command", "script"]:
            job = {"action": "host_health", poison_key: "echo pwned"}
            assert why_refused(job, g) == "jobs may not carry commands"

    def test_why_refused_access_order_hierarchy(self):
        # Action requires 'control', grants only have 'write'
        g_write = LocalGrants(max_access="write", allowed_actions=frozenset({"reclaim_idle_surfaces"}))
        assert "needs control access, this computer allows write" in why_refused({"action": "reclaim_idle_surfaces"}, g_write)

        # Action requires 'write', grants only have 'read'
        g_read = LocalGrants(max_access="read", allowed_actions=frozenset({"git_pull_repo"}))
        assert "needs write access, this computer allows read" in why_refused({"action": "git_pull_repo"}, g_read)

    def test_missing_inbox_directory_returns_empty_cleanly(self, tmp_path):
        agent = HomeAgent(
            mailbox_root=tmp_path / "nonexistent_mailbox",
            host="pc-isolated",
            grants=LocalGrants(),
            handlers={},
        )
        assert agent.run_once() == []

    def test_submit_creates_inbox_and_atomic_file(self, tmp_path):
        mailbox = tmp_path / "box"
        sub_path = submit(mailbox, "pc-2", "job-99", "host_health", {"metric": "ram"})
        assert sub_path.exists()
        assert sub_path.name == "job-99.json"

        content = json.loads(sub_path.read_text(encoding="utf-8"))
        assert content["action"] == "host_health"
        assert content["params"] == {"metric": "ram"}

    def test_jobs_processed_in_sorted_order(self, tmp_path):
        calls = []
        handlers = {
            "host_health": lambda p: calls.append(p["seq"]) or {"done": p["seq"]}
        }
        mailbox = tmp_path / "mb"
        agent = HomeAgent(mailbox, "pc-sorted", LocalGrants(), handlers)

        # Submit jobs in random order: job-c, job-a, job-b
        submit(mailbox, "pc-sorted", "job-c", "host_health", {"seq": 3})
        submit(mailbox, "pc-sorted", "job-a", "host_health", {"seq": 1})
        submit(mailbox, "pc-sorted", "job-b", "host_health", {"seq": 2})

        receipts = agent.run_once()
        assert len(receipts) == 3
        # Should execute in alphabetical order: job-a (1), job-b (2), job-c (3)
        assert calls == [1, 2, 3]

    def test_receipt_metadata_and_written_at_timestamp(self, tmp_path):
        mock_clock = lambda: 123456.78
        mailbox = tmp_path / "mb"
        handlers = {"host_health": lambda p: {"status": "healthy"}}
        agent = HomeAgent(mailbox, "pc-meta", LocalGrants(), handlers, clock=mock_clock)

        submit(mailbox, "pc-meta", "job-alpha", "host_health")
        receipts = agent.run_once()

        assert len(receipts) == 1
        r = receipts[0]
        assert r["job_id"] == "job-alpha"
        assert r["status"] == "DONE"
        assert r["finished_at"] == 123456.78
        assert r["host"] == "pc-meta"

        out_file = mailbox / "pc-meta" / "outbox" / "job-alpha.json"
        assert out_file.exists()
        persisted = json.loads(out_file.read_text(encoding="utf-8"))
        assert persisted == r
