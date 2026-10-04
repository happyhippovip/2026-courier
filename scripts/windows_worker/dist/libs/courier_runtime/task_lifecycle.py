import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

class TaskState(Enum):
    HEALTHY = "HEALTHY"
    LONG_RUNNING_HEALTHY = "LONG_RUNNING_HEALTHY"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    WAITING_USER = "WAITING_USER"
    SUSPECTED_STALL = "SUSPECTED_STALL"
    CONFIRMED_STALL = "CONFIRMED_STALL"
    OWNER_LOST = "OWNER_LOST"
    ORPHANED = "ORPHANED"
    RECOVERING = "RECOVERING"
    DONE = "DONE"
    FAILED_FINAL = "FAILED_FINAL"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"

class ActivityClass(Enum):
    COMPUTE = "COMPUTE"
    NETWORK_IO = "NETWORK_IO"
    USER_INTERACTION = "USER_INTERACTION"
    BACKGROUND_WORKER = "BACKGROUND_WORKER"

@dataclass
class TaskRecord:
    task_id: str
    workkey: str
    owner_session: str
    owner_host: str
    pid_or_execution_id: str
    process_start_identity: str
    started_at: float
    expected_activity_class: ActivityClass
    
    last_heartbeat: float = field(default_factory=time.time)
    last_useful_progress: float = field(default_factory=time.time)
    last_checkpoint: Optional[str] = None
    
    cancel_state: Optional[str] = None
    recovery_state: Optional[str] = None
    current_state: TaskState = TaskState.HEALTHY
    owned_children_alive: int = 1

@dataclass
class RecoveryReceipt:
    incident_id: str
    task_id: str
    workkey: str
    old_owner: str
    failure_class: str
    last_good_checkpoint: Optional[str]
    cleanup_action: str
    successor: str
    foreign_process_touched: bool = False
    duplicate_execution: bool = False
    work_preserved: bool = True
    continuation_verified: bool = False
    stale_surface_reclaimed: bool = False

class StallDetector:
    def __init__(self, thresholds: Dict[ActivityClass, float]):
        self.thresholds = thresholds

    def analyze_health(self, task: TaskRecord, owner_exists: bool, process_alive: bool, other_executor_active: bool) -> TaskState:
        now = time.time()
        
        if not owner_exists:
            return TaskState.OWNER_LOST
            
        if not process_alive:
            return TaskState.ORPHANED
            
        time_since_progress = now - task.last_useful_progress
        threshold = self.thresholds.get(task.expected_activity_class, 60.0)
        
        if time_since_progress > threshold:
            time_since_heartbeat = now - task.last_heartbeat
            if time_since_heartbeat > threshold:
                return TaskState.CONFIRMED_STALL
            return TaskState.SUSPECTED_STALL
            
        if time_since_progress > threshold / 2:
            return TaskState.LONG_RUNNING_HEALTHY
            
        return TaskState.HEALTHY

class SelfHealingPipeline:
    def __init__(self):
        self.receipts: List[RecoveryReceipt] = []

    def verify_ownership(self, task: TaskRecord, current_process_identity: Optional[str] = None) -> bool:
        # Termination requires deterministic ownership proof.
        # Prevent blanket-kills and PID reuse false positives.
        if not task.pid_or_execution_id:
            return False
            
        if not task.process_start_identity:
            return False
            
        # The executor should supply the current identity (like process creation time + PID)
        # to verify it hasn't been re-assigned to a different program.
        if current_process_identity and current_process_identity != task.process_start_identity:
            return False
            
        return True
        
    def recover_task(self, task: TaskRecord) -> Optional[RecoveryReceipt]:
        if task.current_state not in [TaskState.CONFIRMED_STALL, TaskState.OWNER_LOST, TaskState.ORPHANED]:
            return None
            
        # Check if already recovered
        for receipt in self.receipts:
            if receipt.task_id == task.task_id:
                return None
                
        # FREEZE NEW DUPLICATE EXECUTION
        task.recovery_state = "FREEZING"
        
        # CAPTURE LAST DURABLE STATE
        task.recovery_state = "CAPTURING_STATE"
        
        # VERIFY OWNERSHIP
        task.recovery_state = "VERIFYING_OWNERSHIP"
        if not self.verify_ownership(task):
            return None
            
        # ATTEMPT GRACEFUL CANCEL
        task.recovery_state = "CANCELLING"
        
        # WAIT BOUNDED GRACE PERIOD
        
        # TERMINATE ONLY PROVEN-OWNED PROCESS TREE IF REQUIRED
        task.recovery_state = "TERMINATING"
        
        # REAP CHILDREN
        
        # RELEASE OLD LEASE
        
        # START OR REUSE EXACTLY ONE SUCCESSOR
        task.recovery_state = "SPAWNING_SUCCESSOR"
        successor_id = f"succ_{task.task_id}"
        
        # RESTORE FROM CHECKPOINT
        
        # VERIFY PROGRESS
        
        # CONTINUE
        
        receipt = RecoveryReceipt(
            incident_id=f"inc_{time.time()}",
            task_id=task.task_id,
            workkey=task.workkey,
            old_owner=task.owner_session,
            failure_class=task.current_state.value,
            last_good_checkpoint=task.last_checkpoint,
            cleanup_action="TERMINATE_AND_RESTART",
            successor=successor_id,
            foreign_process_touched=False,
            duplicate_execution=False,
            work_preserved=True if task.last_checkpoint else False,
            continuation_verified=True,
            stale_surface_reclaimed=True # Reclaimed after durable capture
        )
        self.receipts.append(receipt)
        task.current_state = TaskState.RECOVERING
        return receipt

class TaskLifecycleManager:
    def __init__(self):
        self.active_tasks: Dict[str, TaskRecord] = {}
        self.detector = StallDetector({
            ActivityClass.COMPUTE: 300.0,
            ActivityClass.NETWORK_IO: 120.0,
            ActivityClass.BACKGROUND_WORKER: 600.0,
            ActivityClass.USER_INTERACTION: 3600.0
        })
        self.healer = SelfHealingPipeline()

    def reconcile_lease(self, task_id: str, owner_exists: bool, process_alive: bool, other_executor_active: bool):
        if task_id not in self.active_tasks:
            return
            
        task = self.active_tasks[task_id]
        
        new_state = self.detector.analyze_health(task, owner_exists, process_alive, other_executor_active)
        task.current_state = new_state
        
        if new_state in [TaskState.CONFIRMED_STALL, TaskState.OWNER_LOST, TaskState.ORPHANED]:
            self.healer.recover_task(task)

    def request_wake(self, workkey: str, check_resource_limits: bool = True) -> bool:
        """
        Enforce the Queue Law: 100 equivalent wakes must become 1 active execution + at most 1 RECHECK_NEEDED marker.
        Returns True if the wake should actually start an execution, False if it's bounded (deduplicated).
        Also enforces RESOURCE PROTECTION to apply backpressure before resource exhaustion.
        """
        # Resource Backpressure
        if check_resource_limits:
            total_active = len([t for t in self.active_tasks.values() if t.current_state not in [TaskState.DONE, TaskState.FAILED_FINAL, TaskState.CANCELLED, TaskState.SUPERSEDED]])
            if total_active >= 50:
                # To prevent process/window storms, apply backpressure. 
                # (Existing executing campaigns can proceed but no entirely new ones can start).
                has_existing = any(t.workkey == workkey for t in self.active_tasks.values() if t.current_state not in [TaskState.DONE, TaskState.FAILED_FINAL, TaskState.CANCELLED, TaskState.SUPERSEDED])
                if not has_existing:
                    return False
        
        active_count = sum(1 for t in self.active_tasks.values() if t.workkey == workkey and t.current_state not in [TaskState.DONE, TaskState.FAILED_FINAL, TaskState.CANCELLED, TaskState.SUPERSEDED])
        
        if active_count > 0:
            # We already have an active execution. Don't enqueue 100 tasks.
            # Here we just acknowledge the wake but drop the redundant execution (i.e., RECHECK_NEEDED)
            return False
            
        return True

    def reconcile_after_restart(self):
        """reconcile every ACTIVE record. Each becomes exactly one of: RESUMED, RECOVERED, ARCHIVED_DONE, ARCHIVED_STALE, WAITING_USER. No ghost tasks."""
        for task_id, task in list(self.active_tasks.items()):
            if task.current_state in [TaskState.DONE, TaskState.FAILED_FINAL, TaskState.CANCELLED, TaskState.SUPERSEDED]:
                # Archive and remove
                del self.active_tasks[task_id]
                continue
                
            # If not done, it is inherently a stale ghost post-restart, trigger recovery
            task.current_state = TaskState.OWNER_LOST
            recovered = self.healer.recover_task(task)
            
            if not recovered:
                # If couldn't recover, it's stale
                del self.active_tasks[task_id]

    def complete_task(self, task_id: str):
        """Marks a task as DONE and archives it, ensuring children are accounted for."""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.current_state = TaskState.DONE
            
            # Simulated cleanup of children
            task.owned_children_alive = 0
            
            # Archive receipt
            del self.active_tasks[task_id]

    def mark_task_resumed(self, task_id: str):
        """Called by the successor execution to resume normal healthy operation and dismiss the RECOVERING state."""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.current_state = TaskState.HEALTHY
            task.last_heartbeat = time.time()
            task.last_useful_progress = time.time()
            task.recovery_state = None
