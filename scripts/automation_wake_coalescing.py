import enum
from dataclasses import dataclass
from typing import Any

class AutoState(enum.Enum):
    IDLE = "IDLE"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RESOURCE_PAUSE = "RESOURCE_PAUSE"

@dataclass
class Wakeup:
    trigger_id: str
    instruction: Any = None
    is_cancel: bool = False

@dataclass
class AutomationContext:
    state: AutoState = AutoState.IDLE
    recheck_needed: bool = False
    pending_instruction: Any = None
    cancel_requested: bool = False

    def enqueue_wake(self, wake: Wakeup):
        """Handle incoming wakeups safely coalescing them."""
        if wake.is_cancel:
            self.cancel_requested = True
            if self.state in (AutoState.IDLE, AutoState.PENDING, AutoState.RESOURCE_PAUSE):
                self.state = AutoState.IDLE
                self.recheck_needed = False
                self.pending_instruction = None
            return

        # If already canceled, ignore new wakeups until explicitly reset or handled
        if self.cancel_requested:
            return

        if self.state == AutoState.IDLE:
            self.state = AutoState.PENDING
            if wake.instruction is not None:
                self.pending_instruction = wake.instruction
        elif self.state == AutoState.PENDING:
            if wake.instruction is not None and wake.instruction != self.pending_instruction:
                self.pending_instruction = wake.instruction
        elif self.state in (AutoState.RUNNING, AutoState.RESOURCE_PAUSE):
            self.recheck_needed = True
            if wake.instruction is not None and wake.instruction != self.pending_instruction:
                self.pending_instruction = wake.instruction

    def start_execution(self) -> bool:
        """Attempt to transition to RUNNING. Returns True if execution should begin."""
        if self.cancel_requested:
            self.cancel_requested = False
            self.state = AutoState.IDLE
            self.recheck_needed = False
            self.pending_instruction = None
            return False
        
        if self.state in (AutoState.PENDING, AutoState.RESOURCE_PAUSE):
            self.state = AutoState.RUNNING
            return True
        return False

    def resource_exhausted(self):
        """Handle EMFILE or spawn limit."""
        if self.state == AutoState.RUNNING:
            self.state = AutoState.RESOURCE_PAUSE

    def finish_execution(self):
        """Called when the current logical execution completes."""
        if self.cancel_requested:
            self.cancel_requested = False
            self.state = AutoState.IDLE
            self.recheck_needed = False
            self.pending_instruction = None
            return
            
        if self.state == AutoState.RESOURCE_PAUSE:
            return

        if self.recheck_needed:
            self.recheck_needed = False
            self.state = AutoState.PENDING
        else:
            self.state = AutoState.IDLE
            self.pending_instruction = None
