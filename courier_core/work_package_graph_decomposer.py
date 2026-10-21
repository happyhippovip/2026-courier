"""Work Package Graph Decomposer & First-Wave Boundary Engine (CP-34 / CQ-34).

Verifies and enforces:
1. Decomposes large work recipes into small, verifiable dependency graphs.
2. Max 5 Tasks First Wave ("Maximal fünf erste Tasks im Beispiel"): The initial execution wave
   is strictly bounded to at most 5 tasks.
3. Strict Reader-Before-Writer Ordering ("Reader-Brief vor Writer"): Mutating writer tasks must
   depend upon verified reader/inspection tasks.
4. Scope and Safety Boundaries ("Keine neuen bezahlten Dienste oder Veröffentlichung"):
   Blocks tasks requesting paid services or deployment/publication actions; restricts file access
   to explicit allowed directory paths.
5. Emits structured evidence matching ["existing-recipe", "acceptance", "allowed-scope"].
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class TaskRoleType(str, Enum):
    READER_BRIEF = "READER_BRIEF"
    INSPECTION = "INSPECTION"
    WRITER_MUTATION = "WRITER_MUTATION"
    VERIFIER = "VERIFIER"


class WaveLimitExceededError(ValueError):
    """Raised when first wave task count exceeds maximum allowed limit."""
    pass


class MissingReaderBriefDependencyError(ValueError):
    """Raised when a writer mutation task lacks a prerequisite reader-brief dependency."""
    pass


class ForbiddenExternalActionError(PermissionError):
    """Raised when a task requests paid services, deployments, or public releases."""
    pass


class ScopeExceededError(ValueError):
    """Raised when a task scope exceeds the allowed root workspace boundaries."""
    pass


@dataclass(frozen=True)
class GraphTaskNode:
    """A single verifiable node in a decomposed execution DAG."""
    task_id: str
    title: str
    role_type: TaskRoleType
    dependencies: List[str] = field(default_factory=list)
    allowed_scope_paths: List[str] = field(default_factory=list)
    requires_paid_services: bool = False
    requires_publication: bool = False
    acceptance_criteria: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "role_type": self.role_type.value,
            "dependencies": list(self.dependencies),
            "allowed_scope_paths": list(self.allowed_scope_paths),
            "requires_paid_services": self.requires_paid_services,
            "requires_publication": self.requires_publication,
            "acceptance_criteria": list(self.acceptance_criteria),
        }


@dataclass(frozen=True)
class DecompositionRecipe:
    """High-level work package recipe."""
    recipe_id: str
    name: str
    description: str
    allowed_root_scope: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "name": self.name,
            "description": self.description,
            "allowed_root_scope": self.allowed_root_scope,
        }


@dataclass
class DecomposedGraph:
    """The validated execution DAG with bounded first wave."""
    recipe: DecompositionRecipe
    tasks: Dict[str, GraphTaskNode]
    first_wave_task_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recipe": self.recipe.to_dict(),
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "first_wave_task_ids": list(self.first_wave_task_ids),
        }


class WorkPackageGraphDecomposer:
    """Decomposes recipes into minimal, safe, verifiable DAGs with reader-before-writer gates."""

    MAX_FIRST_WAVE_SIZE: int = 5

    def __init__(self) -> None:
        self.decomposed_graphs: Dict[str, DecomposedGraph] = {}

    def decompose(
        self,
        recipe: DecompositionRecipe,
        raw_tasks: List[GraphTaskNode],
    ) -> DecomposedGraph:
        """Validates and constructs a decomposed graph ensuring safety and ordering invariants."""
        task_map: Dict[str, GraphTaskNode] = {t.task_id: t for t in raw_tasks}
        first_wave: List[str] = []

        for task in raw_tasks:
            # Invariant: No paid services or publication
            if task.requires_paid_services or task.requires_publication:
                raise ForbiddenExternalActionError(
                    f"Task '{task.task_id}' requests paid services or publication. "
                    "Paid services and deployment actions are strictly forbidden in decomposed graphs."
                )

            # Invariant: Allowed scope boundary enforcement
            for path in task.allowed_scope_paths:
                norm_root = os.path.normpath(recipe.allowed_root_scope)
                norm_path = os.path.normpath(path)
                if not (norm_path == norm_root or norm_path.startswith(norm_root + os.sep)):
                    raise ScopeExceededError(
                        f"Task '{task.task_id}' path '{path}' falls outside allowed root '{recipe.allowed_root_scope}'"
                    )

            # Invariant: Reader-Brief before Writer
            if task.role_type == TaskRoleType.WRITER_MUTATION:
                reader_prereqs = [
                    dep_id for dep_id in task.dependencies
                    if dep_id in task_map and task_map[dep_id].role_type in {
                        TaskRoleType.READER_BRIEF,
                        TaskRoleType.INSPECTION,
                    }
                ]
                if not reader_prereqs:
                    raise MissingReaderBriefDependencyError(
                        f"Writer task '{task.task_id}' lacks a required prerequisite READER_BRIEF "
                        "or INSPECTION dependency."
                    )

            # Determine first wave (no prerequisites)
            if not task.dependencies:
                first_wave.append(task.task_id)

        # Invariant: Max 5 tasks in the first wave
        if len(first_wave) > self.MAX_FIRST_WAVE_SIZE:
            raise WaveLimitExceededError(
                f"First wave contains {len(first_wave)} tasks, exceeding maximum allowed {self.MAX_FIRST_WAVE_SIZE}"
            )

        graph = DecomposedGraph(
            recipe=recipe,
            tasks=task_map,
            first_wave_task_ids=first_wave,
        )
        self.decomposed_graphs[recipe.recipe_id] = graph
        return graph

    def generate_graph_evidence(self, recipe_id: str) -> Dict[str, Any]:
        """Emits required evidence dictionary for CP-34.

        Required fields:
        - 'existing-recipe'
        - 'acceptance'
        - 'allowed-scope'
        """
        if recipe_id not in self.decomposed_graphs:
            raise KeyError(f"Recipe '{recipe_id}' not found in decomposer registry")

        graph = self.decomposed_graphs[recipe_id]
        return {
            "existing-recipe": graph.recipe.to_dict(),
            "acceptance": {
                "max_first_wave_allowed": self.MAX_FIRST_WAVE_SIZE,
                "first_wave_task_count": len(graph.first_wave_task_ids),
                "first_wave_tasks": graph.first_wave_task_ids,
                "reader_before_writer_enforced": True,
                "paid_services_blocked": True,
                "publication_blocked": True,
            },
            "allowed-scope": {
                "root_scope": graph.recipe.allowed_root_scope,
                "all_task_scopes_verified": True,
            },
        }
