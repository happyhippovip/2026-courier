"""Task Dependency DAG Resolver with Cycle Detection.

Resolves topological execution schedules, detects circular dependencies,
and evaluates readiness against ledger-verified completions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence


class CycleDetectedError(Exception):
    """Raised when a circular dependency is detected in the DAG."""


@dataclass
class DAGResolutionReport:
    """Topological ordering and parallel stages."""

    is_acyclic: bool
    execution_order: list[str]
    stages: list[list[str]]
    item_dependencies: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReadinessReport:
    """Readiness status based on ledger prerequisite completion."""

    eligible_items: list[str]
    blocked_items: dict[str, list[str]]  # item_id -> list of unmet dependency IDs

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DAGResolver:
    """Analyzes task dependencies across work item catalogs."""

    def __init__(
        self,
        items_dir: str = "registries/work_items",
        ledger_path: str = "registries/work_queue_ledger.jsonl",
    ):
        self.items_dir = Path(items_dir)
        self.ledger_path = Path(ledger_path)

    def _load_items(self) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {}
        if not self.items_dir.exists():
            return graph

        for p in sorted(self.items_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                item_id = data.get("id")
                if item_id:
                    graph[item_id] = list(data.get("depends_on", []))
            except Exception:
                continue
        return graph

    def _load_completed_from_ledger(self) -> set[str]:
        completed: set[str] = set()
        if not self.ledger_path.exists():
            return completed

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    ev = json.loads(stripped)
                    if not isinstance(ev, dict):
                        continue
                    item_id = ev.get("item_id")
                    if not item_id:
                        continue
                    if ev.get("status") == "DONE":
                        completed.add(item_id)
                    elif ev.get("type") == "RELEASE":
                        res_str = str(ev.get("result") or "").strip().upper()
                        if res_str and not res_str.startswith(("FAIL", "ABORT", "ERROR", "REJECT")):
                            completed.add(item_id)
                        else:
                            completed.discard(item_id)
                    elif ev.get("type") == "CLAIM":
                        completed.discard(item_id)
                except Exception:
                    continue
        return completed

    def resolve(self) -> DAGResolutionReport:
        graph = self._load_items()
        nodes = list(graph.keys())

        # Build in-degree map and dependents map
        in_degree: dict[str, int] = {k: 0 for k in nodes}
        dependents: dict[str, set[str]] = {k: set() for k in nodes}

        for node, deps in graph.items():
            for d in deps:
                if d in nodes:
                    in_degree[node] += 1
                    dependents[d].add(node)

        # Start with nodes that have in_degree == 0
        q = deque([k for k, deg in in_degree.items() if deg == 0])
        stages: list[list[str]] = []
        execution_order: list[str] = []

        while q:
            current_stage = sorted(list(q))
            stages.append(current_stage)
            next_q: list[str] = []

            for node in current_stage:
                execution_order.append(node)
                for dep in sorted(dependents[node]):
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        next_q.append(dep)

            q = deque(next_q)

        if len(execution_order) != len(nodes):
            cyclic_nodes = [k for k, v in in_degree.items() if v > 0]
            raise CycleDetectedError(f"Circular dependency detected among nodes: {cyclic_nodes}")

        return DAGResolutionReport(
            is_acyclic=True,
            execution_order=execution_order,
            stages=stages,
            item_dependencies=graph,
        )

    def evaluate_readiness(
        self,
        completed_ids: set[str] | None = None,
    ) -> ReadinessReport:
        graph = self._load_items()
        completed = completed_ids if completed_ids is not None else self._load_completed_from_ledger()

        eligible_items: list[str] = []
        blocked_items: dict[str, list[str]] = {}

        for item_id, deps in graph.items():
            missing = [d for d in deps if d not in completed]
            if missing:
                blocked_items[item_id] = missing
            else:
                eligible_items.append(item_id)

        return ReadinessReport(
            eligible_items=sorted(eligible_items),
            blocked_items=blocked_items,
        )


def resolve_dag(items_dir: str = "registries/work_items") -> DAGResolutionReport:
    resolver = DAGResolver(items_dir=items_dir)
    return resolver.resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task Dependency DAG Resolver.")
    parser.add_argument("--items-dir", default="registries/work_items", help="Directory of work item JSONs")
    parser.add_argument("--ledger", default="registries/work_queue_ledger.jsonl", help="Work queue ledger JSONL")

    args = parser.parse_args(argv)

    resolver = DAGResolver(items_dir=args.items_dir, ledger_path=args.ledger)
    try:
        dag_rep = resolver.resolve()
        readiness_rep = resolver.evaluate_readiness()
        print(json.dumps({
            "status": "RESOLVED",
            "dag": dag_rep.to_dict(),
            "readiness": readiness_rep.to_dict(),
        }))
        return 0
    except CycleDetectedError as err:
        print(json.dumps({
            "status": "CYCLE_DETECTED",
            "error": str(err),
        }))
        return 1


if __name__ == "__main__":
    sys.exit(main())
