"""Tests for CP-22 / CQ-22 / GB-SCOPE-01: Resource Scope, Shared Mutable Guard & Snapshot Consistency

Verifies:
1. Overlapping directory hierarchies and file containment detect conflicts.
2. Git working tree index modifications are mutually exclusive.
3. Network port collisions are strictly prevented.
4. Test database write contention enforces mutual exclusion.
5. Concurrent readers run safely under snapshot isolation.
6. The parallel label does not grant permission to bypass physical conflicts.
7. Evidence generated with ['scope-model', 'shared-resources', 'snapshot-policy'].
"""

import pytest

from courier_core.resource_scope_boundary import (
    AccessMode,
    ResourceClaim,
    ResourceScopeBoundary,
    ResourceType,
    ScopeConflictError,
    TaskScope,
)


def test_overlapping_directories_and_file_containment_conflicts():
    boundary = ResourceScopeBoundary()

    # Task A writes to root src/ directory tree
    scope_a = TaskScope(
        task_id="task-refactor-src",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.DIRECTORY_TREE,
                identifier="src",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )
    boundary.acquire(scope_a)

    # Task B writes to a specific file inside src/
    scope_b = TaskScope(
        task_id="task-edit-controller",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.FILE,
                identifier="src/controllers/user.py",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )

    allowed, reason = boundary.can_admit(scope_b)
    assert allowed is False
    assert "FILE_IN_MUTABLE_DIRECTORY" in reason

    with pytest.raises(ScopeConflictError, match="FILE_IN_MUTABLE_DIRECTORY"):
        boundary.acquire(scope_b)

    # Task C writes to a child directory tree
    scope_c = TaskScope(
        task_id="task-child-dir",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.DIRECTORY_TREE,
                identifier="src/controllers",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )
    allowed_c, reason_c = boundary.can_admit(scope_c)
    assert allowed_c is False
    assert "DIRECTORY_TREE_OVERLAP" in reason_c

    # Releasing Task A allows Task B
    boundary.release("task-refactor-src")
    boundary.acquire(scope_b)
    assert "task-edit-controller" in boundary.active_scopes


def test_git_index_exclusive_mutation_conflicts():
    boundary = ResourceScopeBoundary()

    scope_git_1 = TaskScope(
        task_id="task-git-add",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.GIT_INDEX,
                identifier=".git/index",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )
    boundary.acquire(scope_git_1)

    scope_git_2 = TaskScope(
        task_id="task-git-commit",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.GIT_INDEX,
                identifier=".git/index",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )

    allowed, reason = boundary.can_admit(scope_git_2)
    assert allowed is False
    assert "GIT_INDEX_EXCLUSIVE_MUTATION" in reason


def test_port_collision_conflicts():
    boundary = ResourceScopeBoundary()

    server_1 = TaskScope(
        task_id="test-server-1",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.PORT,
                identifier="8080",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )
    boundary.acquire(server_1)

    # Same port collides
    server_2 = TaskScope(
        task_id="test-server-2",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.PORT,
                identifier="8080",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )
    allowed_2, reason_2 = boundary.can_admit(server_2)
    assert allowed_2 is False
    assert "PORT_COLLISION" in reason_2

    # Different port succeeds concurrently
    server_3 = TaskScope(
        task_id="test-server-3",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.PORT,
                identifier="9090",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )
    allowed_3, reason_3 = boundary.can_admit(server_3)
    assert allowed_3 is True
    assert reason_3 is None
    boundary.acquire(server_3)
    assert len(boundary.active_scopes) == 2


def test_test_database_write_contention():
    boundary = ResourceScopeBoundary()

    db_test_1 = TaskScope(
        task_id="db-migration-test",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.TEST_DATABASE,
                identifier="tests/test_data.sqlite",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )
    boundary.acquire(db_test_1)

    db_test_2 = TaskScope(
        task_id="db-seeding-test",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.TEST_DATABASE,
                identifier="tests\\test_data.sqlite",  # tests path normalization
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )

    allowed, reason = boundary.can_admit(db_test_2)
    assert allowed is False
    assert "TEST_DB_WRITE_CONTENTION" in reason


def test_reader_shared_concurrency_under_snapshot_policy():
    boundary = ResourceScopeBoundary()

    # Two concurrent read-only tasks on the same file under snapshot
    reader_1 = TaskScope(
        task_id="audit-reader-1",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.FILE,
                identifier="config/settings.json",
                access_mode=AccessMode.READ_SHARED,
                snapshot_id="sha-commit-v10",
            )
        ],
    )
    reader_2 = TaskScope(
        task_id="audit-reader-2",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.FILE,
                identifier="config/settings.json",
                access_mode=AccessMode.READ_SHARED,
                snapshot_id="sha-commit-v10",
            )
        ],
    )

    boundary.acquire(reader_1)
    boundary.acquire(reader_2)
    assert len(boundary.active_scopes) == 2

    # A writer attempts to modify config/settings.json
    writer = TaskScope(
        task_id="config-updater",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.FILE,
                identifier="config/settings.json",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )

    allowed_w, reason_w = boundary.can_admit(writer)
    assert allowed_w is False
    assert "EXACT_RESOURCE_COLLISION" in reason_w


def test_parallel_label_is_not_permission_to_bypass_conflict():
    boundary = ResourceScopeBoundary()

    writer = TaskScope(
        task_id="task-writer",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.FILE,
                identifier="dist/bundle.js",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
    )
    boundary.acquire(writer)

    # Candidate has parallel=True label, but conflicts on same resource
    parallel_labeled_task = TaskScope(
        task_id="task-labeled-parallel",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.FILE,
                identifier="dist/bundle.js",
                access_mode=AccessMode.WRITE_EXCLUSIVE,
            )
        ],
        has_parallel_label=True,
    )

    allowed, reason = boundary.can_admit(parallel_labeled_task)
    assert allowed is False
    assert "task parallel label does not grant permission to bypass scope conflict" in reason

    with pytest.raises(ScopeConflictError, match="task parallel label does not grant permission"):
        boundary.acquire(parallel_labeled_task)


def test_evidence_generation():
    boundary = ResourceScopeBoundary()

    scope = TaskScope(
        task_id="task-demo",
        claims=[
            ResourceClaim(
                resource_type=ResourceType.FILE,
                identifier="demo.txt",
                access_mode=AccessMode.READ_SHARED,
                snapshot_id="v1",
            )
        ],
    )
    boundary.acquire(scope)

    evidence = boundary.generate_scope_evidence()

    assert evidence["required_evidence"] == ["scope-model", "shared-resources", "snapshot-policy"]
    assert "FILE" in evidence["scope-model"]["supported_resource_types"]
    assert "DIRECTORY_TREE" in evidence["scope-model"]["supported_resource_types"]
    assert evidence["shared-resources"]["active_claimed_resources_count"] == 1
    assert "snapshot_isolation" in evidence["snapshot-policy"]
