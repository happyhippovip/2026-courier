"""Tests for CP-43 / CQ-43 / GB-WORKSPACE-LAYOUT-01: Workspace Layout & Tile Decoupling.

Verifies:
1. Switching layout between 1/2/4/6/8 tiles triggers zero model jobs ("Layoutwechsel startet keinen Modelljob").
2. Closing a tile unbinds display but never deletes or alters the underlying task ("Schließen einer Kachel löscht keinen Task").
3. Unoccupied slots are authentic empty placeholders without simulated phantom workers ("unbelegte Einbettung nicht vortäuschen").
4. Tile swapping and focus movements manipulate presentation without affecting task status.
5. Evidence structure generation containing ['current-UI', 'workspace-model', 'launch-boundary'].
"""

import pytest

from courier_core.workspace_layout_manager import (
    LayoutMode,
    WorkspaceLayoutManager,
)


def test_layout_switch_triggers_zero_model_jobs():
    """Switching layout modes reconfigures grid geometry while strictly triggering 0 model jobs."""
    manager = WorkspaceLayoutManager(initial_mode=LayoutMode.SINGLE)
    assert manager.current_mode == LayoutMode.SINGLE
    assert len(manager.list_slots()) == 1
    assert manager.model_jobs_triggered == 0

    # Switch to 8-tile grid
    manager.switch_layout(LayoutMode.OCTA_GRID)
    assert manager.current_mode == LayoutMode.OCTA_GRID
    assert len(manager.list_slots()) == 8
    # Absolute contract invariant: 0 model jobs
    assert manager.model_jobs_triggered == 0

    # Switch to 4-tile grid
    manager.switch_layout(LayoutMode.QUAD_GRID)
    assert manager.current_mode == LayoutMode.QUAD_GRID
    assert len(manager.list_slots()) == 4
    assert manager.model_jobs_triggered == 0


def test_closing_tile_does_not_delete_or_cancel_task():
    """Closing a visual tile unbinds the presentation slot but preserves the underlying task."""
    manager = WorkspaceLayoutManager(initial_mode=LayoutMode.QUAD_GRID)

    manager.register_task("task-render-901", "3D Scene Rendering", status="RUNNING")
    manager.assign_task_to_slot("slot_1", "task-render-901")

    slot1 = [s for s in manager.list_slots() if s.slot_id == "slot_1"][0]
    assert slot1.assigned_task_id == "task-render-901"
    assert slot1.is_empty is False

    # Close tile
    unbound_task = manager.close_tile("slot_1")
    assert unbound_task == "task-render-901"

    # Slot is now empty
    assert slot1.assigned_task_id is None
    assert slot1.is_empty is True

    # Underlying task in external registry is completely intact and running
    task_record = manager.get_task_status("task-render-901")
    assert task_record is not None
    assert task_record["status"] == "RUNNING"
    assert task_record["deleted"] is False


def test_unoccupied_slots_explicitly_empty_without_fake_workers():
    """Unoccupied slots are explicitly empty, ensuring no fabricated worker processes or fake embeddings."""
    manager = WorkspaceLayoutManager(initial_mode=LayoutMode.HEX_GRID)

    manager.register_task("task-ci-01", "CI Gate Verification")
    manager.assign_task_to_slot("slot_0", "task-ci-01")

    slots = manager.list_slots()
    assert len(slots) == 6

    # Slot 0 is occupied
    assert slots[0].is_empty is False
    assert slots[0].assigned_task_id == "task-ci-01"

    # Slots 1-5 are authentic empty placeholders
    for slot in slots[1:]:
        assert slot.is_empty is True
        assert slot.assigned_task_id is None
        assert slot.display_title == "Empty Slot"


def test_swap_and_focus_manipulation():
    """Tile swapping and focus updates correctly manipulate presentation without affecting task status."""
    manager = WorkspaceLayoutManager(initial_mode=LayoutMode.QUAD_GRID)

    manager.register_task("task-a", "Task Alpha")
    manager.register_task("task-b", "Task Beta")
    manager.assign_task_to_slot("slot_0", "task-a")
    manager.assign_task_to_slot("slot_1", "task-b")

    # Swap slot_0 and slot_1
    manager.swap_tiles("slot_0", "slot_1")

    slots_by_id = {s.slot_id: s for s in manager.list_slots()}
    assert slots_by_id["slot_0"].assigned_task_id == "task-b"
    assert slots_by_id["slot_1"].assigned_task_id == "task-a"

    # Set focus
    manager.set_focus("slot_3")
    assert manager.focused_slot_id == "slot_3"

    # Both tasks remain untouched in registry
    assert manager.get_task_status("task-a")["deleted"] is False
    assert manager.get_task_status("task-b")["deleted"] is False


def test_evidence_generation():
    """Validates required catalog evidence keys: ['current-UI', 'workspace-model', 'launch-boundary']."""
    manager = WorkspaceLayoutManager(initial_mode=LayoutMode.QUAD_GRID)
    manager.register_task("task-test", "Test Task")
    manager.assign_task_to_slot("slot_0", "task-test")

    evidence = manager.generate_workspace_evidence()

    assert "current-UI" in evidence
    assert "workspace-model" in evidence
    assert "launch-boundary" in evidence

    assert evidence["current-UI"]["layout_mode"] == "QUAD_GRID"
    assert evidence["current-UI"]["model_jobs_triggered"] == 0
    assert evidence["workspace-model"]["occupied_slots"] == 1
    assert evidence["workspace-model"]["empty_slots"] == 3
    assert evidence["launch-boundary"]["per_tile_worker_spawn_enabled"] is False
