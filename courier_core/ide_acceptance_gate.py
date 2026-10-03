from dataclasses import dataclass
from typing import List, Optional
from courier_core.recovery_state_machine import RecoveryState

@dataclass
class PendingChange:
    file_path: str
    writer_id: str
    is_user_edit: bool
    has_merge_conflict: bool
    is_permission_sensitive: bool

@dataclass
class IdeSurfaceState:
    is_review_changes_visible: bool
    is_accept_all_visible: bool
    queued_messages_count: int
    agent_actively_editing: bool

class AcceptanceGate:
    def __init__(self, authorized_writer_id: str, permitted_scopes: List[str]):
        self.authorized_writer_id = authorized_writer_id
        self.permitted_scopes = permitted_scopes

    def detect_gate(self, surface: IdeSurfaceState) -> Optional[RecoveryState]:
        if surface.is_review_changes_visible and surface.is_accept_all_visible:
            if surface.queued_messages_count > 0 and not surface.agent_actively_editing:
                return RecoveryState.WAITING_FOR_CHANGE_ACCEPTANCE
        return None

    def can_auto_accept(self, changes: List[PendingChange]) -> bool:
        if not changes:
            return True
            
        for change in changes:
            # A. writer ownership matches
            if change.writer_id != self.authorized_writer_id:
                return False
            # B. file scope matches
            in_scope = False
            for scope in self.permitted_scopes:
                if change.file_path.startswith(scope):
                    in_scope = True
                    break
            if not in_scope:
                return False
            # C. no external/user edits are mixed in
            if change.is_user_edit:
                return False
            # D. no dangerous command/permission is bundled
            if change.is_permission_sensitive:
                return False
            # E. no merge/conflict exists
            if change.has_merge_conflict:
                return False
        return True

    def process_review_gate(
        self, 
        surface: IdeSurfaceState, 
        changes: List[PendingChange], 
        tests_pass: bool,
        workspace_reconciled: bool = True
    ) -> RecoveryState:
        
        # 10. IDE/review surface disappears unexpectedly; reconcile actual filesystem state
        if not surface.is_review_changes_visible and not workspace_reconciled:
            return RecoveryState.RECOVERING

        gate_state = self.detect_gate(surface)
        if gate_state != RecoveryState.WAITING_FOR_CHANGE_ACCEPTANCE:
            return RecoveryState.IDLE_READY

        if not self.can_auto_accept(changes):
            return RecoveryState.WAITING_FOR_USER_ACCEPTANCE
            
        # Review accepted -> verify workspace -> run required tests
        if not tests_pass:
            return RecoveryState.FAILED
            
        # -> create evidence/checkpoint -> mark workkey state -> immediately start next queued workkey
        if surface.queued_messages_count > 0:
            return RecoveryState.EXECUTING
        else:
            return RecoveryState.IDLE_READY

