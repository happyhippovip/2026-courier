"""Tests for Task Dependency DAG Resolver with Cycle Detection."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.dag_resolver import (
    DAGResolver,
    DAGResolutionReport,
    CycleDetectedError,
    resolve_dag,
    main,
)


def make_item_file(dir_path: Path, item_id: str, depends_on: list[str]) -> Path:
    data = {
        "id": item_id,
        "title": f"Task {item_id}",
        "lane": "L1",
        "branch": f"lane/L1-{item_id}",
        "files_scope": [f"file_{item_id}.py"],
        "depends_on": depends_on,
        "acceptance": ["tests"],
        "provider_hints": ["headless"],
        "status": "READY",
        "lease": None,
    }
    file_p = dir_path / f"{item_id}.json"
    file_p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return file_p


def test_linear_dependencies_order(tmp_path):
    items_dir = tmp_path / "work_items"
    items_dir.mkdir()

    make_item_file(items_dir, "A", depends_on=[])
    make_item_file(items_dir, "B", depends_on=["A"])
    make_item_file(items_dir, "C", depends_on=["B"])

    resolver = DAGResolver(items_dir=str(items_dir))
    report = resolver.resolve()

    assert report.is_acyclic is True
    assert report.execution_order == ["A", "B", "C"]
    assert len(report.stages) == 3
    assert report.stages == [["A"], ["B"], ["C"]]


def test_parallel_branches_order(tmp_path):
    items_dir = tmp_path / "work_items"
    items_dir.mkdir()

    make_item_file(items_dir, "Root", depends_on=[])
    make_item_file(items_dir, "Branch1", depends_on=["Root"])
    make_item_file(items_dir, "Branch2", depends_on=["Root"])
    make_item_file(items_dir, "Join", depends_on=["Branch1", "Branch2"])

    resolver = DAGResolver(items_dir=str(items_dir))
    report = resolver.resolve()

    assert report.is_acyclic is True
    assert report.stages[0] == ["Root"]
    assert set(report.stages[1]) == {"Branch1", "Branch2"}
    assert report.stages[2] == ["Join"]


def test_circular_dependency_detected(tmp_path):
    items_dir = tmp_path / "work_items"
    items_dir.mkdir()

    make_item_file(items_dir, "NodeA", depends_on=["NodeC"])
    make_item_file(items_dir, "NodeB", depends_on=["NodeA"])
    make_item_file(items_dir, "NodeC", depends_on=["NodeB"])

    resolver = DAGResolver(items_dir=str(items_dir))
    with pytest.raises(CycleDetectedError, match="Circular dependency detected"):
        resolver.resolve()


def test_ledger_prerequisite_filtering(tmp_path):
    items_dir = tmp_path / "work_items"
    items_dir.mkdir()

    make_item_file(items_dir, "TaskReady", depends_on=["Done1", "Done2"])
    make_item_file(items_dir, "TaskBlocked", depends_on=["Done1", "PendingTask"])

    completed_in_ledger = {"Done1", "Done2"}

    resolver = DAGResolver(items_dir=str(items_dir))
    report = resolver.evaluate_readiness(completed_ids=completed_in_ledger)

    assert "TaskReady" in report.eligible_items
    assert "TaskBlocked" in report.blocked_items
    assert "PendingTask" in report.blocked_items["TaskBlocked"]

    # Also verify reading real work_queue_ledger.jsonl RELEASE events vs FAIL releases
    ledger_file = tmp_path / "work_queue_ledger.jsonl"
    ledger_file.write_text(
        "\n".join([
            json.dumps({"type": "CLAIM", "item_id": "Done1", "holder": "w1", "at": "2026-10-18T10:00:00Z"}),
            json.dumps({"type": "RELEASE", "item_id": "Done1", "holder": "w1", "result": "DONE", "at": "2026-10-18T10:01:00Z"}),
            json.dumps({"type": "CLAIM", "item_id": "Done2", "holder": "w1", "at": "2026-10-18T10:02:00Z"}),
            json.dumps({"type": "RELEASE", "item_id": "Done2", "holder": "w1", "result": "tests pass: 6/6", "at": "2026-10-18T10:03:00Z"}),
            json.dumps({"type": "CLAIM", "item_id": "PendingTask", "holder": "w1", "at": "2026-10-18T10:04:00Z"}),
            json.dumps({"type": "RELEASE", "item_id": "PendingTask", "holder": "w1", "result": "FAILED: timeout", "at": "2026-10-18T10:05:00Z"}),
        ]) + "\n",
        encoding="utf-8",
    )
    resolver_with_ledger = DAGResolver(items_dir=str(items_dir), ledger_path=str(ledger_file))
    report_from_ledger = resolver_with_ledger.evaluate_readiness()
    assert "TaskReady" in report_from_ledger.eligible_items
    assert "TaskBlocked" in report_from_ledger.blocked_items


def test_missing_prerequisite_declaration(tmp_path):
    items_dir = tmp_path / "work_items"
    items_dir.mkdir()

    make_item_file(items_dir, "OrphanTask", depends_on=["GhostTask"])

    resolver = DAGResolver(items_dir=str(items_dir))
    report = resolver.evaluate_readiness(completed_ids=set())

    assert "OrphanTask" in report.blocked_items
    assert "GhostTask" in report.blocked_items["OrphanTask"]


def test_cli_invocation(tmp_path):
    items_dir = tmp_path / "work_items"
    items_dir.mkdir()

    make_item_file(items_dir, "T1", depends_on=[])
    make_item_file(items_dir, "T2", depends_on=["T1"])

    code = main([
        "--items-dir", str(items_dir),
    ])
    assert code == 0
