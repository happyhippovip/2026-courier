"""Tests for CP-34 / CQ-34 / GB-GRAPH-DECOMPOSE-01: Work Package Graph Decomposer & First-Wave Boundary.

Verifies:
1. Valid decomposition into a minimal DAG with at most 5 tasks in the first wave.
2. First wave exceeding 5 tasks fails closed with WaveLimitExceededError.
3. Writer tasks without a prerequisite reader brief or inspection fail closed.
4. Paid services or deployment/publication actions are strictly blocked.
5. Task scope exceeding the allowed root directory is rejected.
6. Evidence generated with ['existing-recipe', 'acceptance', 'allowed-scope'].
"""

import pytest

from courier_core.work_package_graph_decomposer import (
    DecompositionRecipe,
    ForbiddenExternalActionError,
    GraphTaskNode,
    MissingReaderBriefDependencyError,
    ScopeExceededError,
    TaskRoleType,
    WaveLimitExceededError,
    WorkPackageGraphDecomposer,
)


@pytest.fixture
def sample_recipe():
    return DecompositionRecipe(
        recipe_id="RECIPE-WEB-MODERNIZE",
        name="Modernize Landing Page Components",
        description="Extract components and migrate styling safely",
        allowed_root_scope="src/web_ui",
    )


def test_valid_decomposition_within_first_wave_limit(sample_recipe):
    """A valid decomposition with 3 first wave tasks and reader-before-writer succeeds."""
    decomposer = WorkPackageGraphDecomposer()

    tasks = [
        # First wave tasks (no dependencies, count = 2)
        GraphTaskNode(
            task_id="task-r1",
            title="Inspect current header layout",
            role_type=TaskRoleType.READER_BRIEF,
            allowed_scope_paths=["src/web_ui/header.html"],
            acceptance_criteria=["Header DOM nodes cataloged"],
        ),
        GraphTaskNode(
            task_id="task-r2",
            title="Inspect CSS token definitions",
            role_type=TaskRoleType.INSPECTION,
            allowed_scope_paths=["src/web_ui/styles.css"],
            acceptance_criteria=["Color tokens verified"],
        ),
        # Second wave task (depends on r1 and r2)
        GraphTaskNode(
            task_id="task-w1",
            title="Refactor header CSS markup",
            role_type=TaskRoleType.WRITER_MUTATION,
            dependencies=["task-r1", "task-r2"],
            allowed_scope_paths=["src/web_ui/header.html"],
            acceptance_criteria=["Header conforms to new tokens"],
        ),
    ]

    graph = decomposer.decompose(sample_recipe, tasks)
    assert len(graph.first_wave_task_ids) == 2
    assert "task-r1" in graph.first_wave_task_ids
    assert "task-r2" in graph.first_wave_task_ids
    assert "task-w1" not in graph.first_wave_task_ids


def test_first_wave_exceeding_five_tasks_fails_closed(sample_recipe):
    """Creating more than 5 tasks in the first wave raises WaveLimitExceededError."""
    decomposer = WorkPackageGraphDecomposer()

    # 6 independent tasks with no dependencies
    tasks = [
        GraphTaskNode(
            task_id=f"task-r{i}",
            title=f"Inspect part {i}",
            role_type=TaskRoleType.READER_BRIEF,
            allowed_scope_paths=["src/web_ui/parts"],
        )
        for i in range(1, 7)
    ]

    with pytest.raises(WaveLimitExceededError) as exc_info:
        decomposer.decompose(sample_recipe, tasks)
    assert "exceeding maximum allowed 5" in str(exc_info.value)


def test_writer_without_reader_brief_dependency_rejected(sample_recipe):
    """A writer task that attempts to run without a prerequisite reader brief fails closed."""
    decomposer = WorkPackageGraphDecomposer()

    tasks = [
        GraphTaskNode(
            task_id="task-w-blind",
            title="Blind writer without reader brief",
            role_type=TaskRoleType.WRITER_MUTATION,
            dependencies=[],  # No reader dependency!
            allowed_scope_paths=["src/web_ui/code.js"],
        ),
    ]

    with pytest.raises(MissingReaderBriefDependencyError) as exc_info:
        decomposer.decompose(sample_recipe, tasks)
    assert "lacks a required prerequisite READER_BRIEF" in str(exc_info.value)


def test_paid_services_or_publication_strictly_forbidden(sample_recipe):
    """Tasks requesting paid services or deployment/publication are strictly blocked."""
    decomposer = WorkPackageGraphDecomposer()

    tasks_paid = [
        GraphTaskNode(
            task_id="task-paid",
            title="External paid scan",
            role_type=TaskRoleType.READER_BRIEF,
            requires_paid_services=True,
            allowed_scope_paths=["src/web_ui"],
        ),
    ]
    with pytest.raises(ForbiddenExternalActionError):
        decomposer.decompose(sample_recipe, tasks_paid)

    tasks_pub = [
        GraphTaskNode(
            task_id="task-pub",
            title="Deploy to production hosting",
            role_type=TaskRoleType.READER_BRIEF,
            requires_publication=True,
            allowed_scope_paths=["src/web_ui"],
        ),
    ]
    with pytest.raises(ForbiddenExternalActionError):
        decomposer.decompose(sample_recipe, tasks_pub)


def test_task_scope_exceeding_root_directory_rejected(sample_recipe):
    """Tasks attempting to touch paths outside the recipe root scope raise ScopeExceededError."""
    decomposer = WorkPackageGraphDecomposer()

    tasks = [
        GraphTaskNode(
            task_id="task-out-of-scope",
            title="Inspect external directory",
            role_type=TaskRoleType.READER_BRIEF,
            allowed_scope_paths=["other_service/secret_config"],
        ),
    ]

    with pytest.raises(ScopeExceededError) as exc_info:
        decomposer.decompose(sample_recipe, tasks)
    assert "falls outside allowed root" in str(exc_info.value)


def test_evidence_generation(sample_recipe):
    """Emits required evidence with existing-recipe, acceptance, and allowed-scope."""
    decomposer = WorkPackageGraphDecomposer()
    tasks = [
        GraphTaskNode(
            task_id="task-r1",
            title="Briefing",
            role_type=TaskRoleType.READER_BRIEF,
            allowed_scope_paths=["src/web_ui/index.html"],
        ),
    ]
    decomposer.decompose(sample_recipe, tasks)

    evidence = decomposer.generate_graph_evidence("RECIPE-WEB-MODERNIZE")
    required_keys = ["existing-recipe", "acceptance", "allowed-scope"]
    for k in required_keys:
        assert k in evidence

    assert evidence["acceptance"]["max_first_wave_allowed"] == 5
    assert evidence["acceptance"]["first_wave_task_count"] == 1
    assert evidence["acceptance"]["reader_before_writer_enforced"] is True
    assert evidence["allowed-scope"]["all_task_scopes_verified"] is True
