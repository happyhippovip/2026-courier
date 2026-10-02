import datetime
import enum
from dataclasses import dataclass
from typing import Any, List, Optional
from scripts.provider_circuit import ProviderCircuitBreaker, ProviderState
from scripts.automation_wake_coalescing import AutomationContext, AutoState, Wakeup

class WorkState(enum.Enum):
    LOCAL_READY = "LOCAL_READY"
    PROVIDER_READY = "PROVIDER_READY"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    WAITING_AUTHORITY = "WAITING_AUTHORITY"
    RESOURCE_PAUSED = "RESOURCE_PAUSED"
    COMPLETE = "COMPLETE"
    EFFECT_UNKNOWN = "EFFECT_UNKNOWN"

@dataclass
class TaskContext:
    task_id: str
    required_capability: str = "completion"
    is_deterministic: bool = False
    requires_human_gate: bool = False
    effect_uncertain: bool = False

@dataclass
class Provider:
    id: str
    is_authorized: bool = False
    capabilities: List[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []

class LocalReadyPlanner:
    def get_local_ready_work(self, tasks: List[TaskContext]) -> List[TaskContext]:
        return [t for t in tasks if t.is_deterministic]

class AuthorizedProviderRouter:
    def __init__(self, breaker: ProviderCircuitBreaker, get_providers):
        self.breaker = breaker
        self.get_providers = get_providers

    def find_fallback(self, failed_provider_id: str, task: TaskContext) -> Optional[Provider]:
        if task.effect_uncertain:
            return None # Effect unknown, cannot blindly retry
            
        for provider in self.get_providers():
            if provider.id == failed_provider_id:
                continue
            if not provider.is_authorized:
                continue
            if task.required_capability not in provider.capabilities:
                continue
            if self.breaker.is_open(provider.id, task.required_capability):
                continue
            return provider
        return None

    def create_compact_handoff(self, task: TaskContext, from_provider: str, to_provider: Provider) -> dict:
        return {
            "PROJECT": "Courier",
            "TASK": task.task_id,
            "AUTHORITY_BOUNDARY": "PRESERVED",
            "PREVIOUS_PROVIDER": from_provider,
            "TARGET_PROVIDER": to_provider.id
        }

class CourierScheduler:
    def __init__(self):
        self.breaker = ProviderCircuitBreaker()
        self.providers = [
            Provider(id="muse", is_authorized=True, capabilities=["completion"]),
            Provider(id="gemini", is_authorized=True, capabilities=["completion"])
        ]
        self.router = AuthorizedProviderRouter(self.breaker, lambda: self.providers)
        self.planner = LocalReadyPlanner()
        self.automation_ctx = AutomationContext()
        self.completed_tasks = []

    def handle_wake(self, wake_id: str, tasks: List[TaskContext]):
        self.automation_ctx.enqueue_wake(Wakeup(trigger_id=wake_id))
        
        if not self.automation_ctx.start_execution():
            return

        try:
            for task in tasks:
                if task.task_id in self.completed_tasks:
                    continue
                
                state = self.evaluate_task_state(task)
                if state == WorkState.LOCAL_READY:
                    self.execute_local(task)
                elif state == WorkState.PROVIDER_READY:
                    self.execute_with_provider(task, "muse")
                elif state == WorkState.WAITING_PROVIDER:
                    pass
        except OSError as e:
            if e.errno == 24: # EMFILE
                self.automation_ctx.resource_exhausted()
        finally:
            self.automation_ctx.finish_execution()

    def evaluate_task_state(self, task: TaskContext) -> WorkState:
        if task.requires_human_gate:
            return WorkState.WAITING_AUTHORITY
        if task.is_deterministic:
            return WorkState.LOCAL_READY
            
        if self.breaker.is_open("muse", task.required_capability):
            fallback = self.router.find_fallback("muse", task)
            if fallback:
                return WorkState.PROVIDER_READY
            return WorkState.WAITING_PROVIDER
            
        return WorkState.PROVIDER_READY

    def execute_local(self, task: TaskContext):
        self.completed_tasks.append(task.task_id)

    def execute_with_provider(self, task: TaskContext, primary_provider: str):
        if self.breaker.is_open(primary_provider, task.required_capability):
            fallback = self.router.find_fallback(primary_provider, task)
            if fallback:
                handoff = self.router.create_compact_handoff(task, primary_provider, fallback)
                self.completed_tasks.append(task.task_id)
            else:
                pass # WAIT
        else:
            if hasattr(self, "simulate_error") and self.simulate_error_provider == primary_provider:
                self.breaker.record_failure(
                    primary_provider, 
                    task.required_capability, 
                    self.simulate_error_code, 
                    self.simulate_error_message,
                    getattr(self, "simulate_reset_time", None)
                )
                
                fallback = self.router.find_fallback(primary_provider, task)
                if fallback:
                    handoff = self.router.create_compact_handoff(task, primary_provider, fallback)
                    self.completed_tasks.append(task.task_id)
                return
                
            self.breaker.record_success(primary_provider, task.required_capability)
            self.completed_tasks.append(task.task_id)

