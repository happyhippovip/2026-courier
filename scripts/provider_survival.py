import datetime
import enum
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from scripts.provider_circuit import ProviderCircuitBreaker, ProviderState
from scripts.automation_wake_coalescing import AutomationContext, AutoState, Wakeup
from scripts.provider_hibernation import LaneHibernator, should_hibernate

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
    effect_key: Optional[str] = None
    attempt: int = 1
    dispatch_id: Optional[str] = None

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
            "TARGET_PROVIDER": to_provider.id,
            "EFFECT_KEY": task.effect_key,
            "ATTEMPT": task.attempt,
            "DISPATCH_ID": task.dispatch_id,
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
        # Every real provider attempt is logged here as (provider_id, task_id).
        # Deterministic fake-provider tests assert on this log instead of
        # touching the network. A recovery probe counts as one attempt.
        self.provider_calls: List[Tuple[str, str]] = []
        # Optional fake probe used after reset: () -> (ok, code, message).
        # When None, a claimed probe succeeds and completes the unit.
        self.recovery_probe: Optional[Callable[[], Tuple[bool, int, str]]] = None

    def handle_wake(self, wake_id: str, tasks: List[TaskContext],
                    hibernator: Optional[LaneHibernator] = None,
                    checkpoint: Optional[Any] = None):
        self.automation_ctx.enqueue_wake(Wakeup(trigger_id=wake_id))
        
        if not self.automation_ctx.start_execution():
            return

        try:
            local_tasks = []
            provider_tasks = []
            
            for task in tasks:
                if task.task_id in self.completed_tasks:
                    continue
                
                state = self.evaluate_task_state(task)
                if state == WorkState.LOCAL_READY:
                    local_tasks.append(task)
                    self.execute_local(task)
                elif state == WorkState.PROVIDER_READY:
                    provider_tasks.append(task)
                    self.execute_with_provider(task, "muse")
                elif state == WorkState.WAITING_PROVIDER:
                    provider_tasks.append(task)
                    pass
            
            if hibernator and checkpoint:
                self.hibernate_if_quota_blocked_idle(hibernator, checkpoint, local_tasks, provider_tasks)
            
            # Compaction (Issue #75)
            if len(self.completed_tasks) > 1000:
                self.completed_tasks = self.completed_tasks[-1000:]
            if len(self.provider_calls) > 1000:
                self.provider_calls = self.provider_calls[-1000:]
                
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
            circuit = self.breaker.get_circuit(primary_provider, task.required_capability)
            if circuit.state == ProviderState.RECOVERY_PROBE_DUE:
                # Only one bounded recovery probe per episode; the rest wait.
                if not circuit.claim_probe():
                    return
                self.provider_calls.append((primary_provider, task.task_id))
                if self.recovery_probe is not None:
                    ok, code, message = self.recovery_probe()
                    if ok:
                        self.breaker.record_success(primary_provider, task.required_capability)
                        self.completed_tasks.append(task.task_id)
                    else:
                        self.breaker.record_failure(
                            primary_provider, task.required_capability, code, message
                        )
                        # The episode's reset is consumed; without fresh reset
                        # metadata the circuit holds OPEN instead of probing
                        # continuously.
                        circuit.reset_time = None
                    return
                self.breaker.record_success(primary_provider, task.required_capability)
                self.completed_tasks.append(task.task_id)
                return
            if hasattr(self, "simulate_error") and self.simulate_error_provider == primary_provider:
                self.provider_calls.append((primary_provider, task.task_id))
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

            self.provider_calls.append((primary_provider, task.task_id))
            self.breaker.record_success(primary_provider, task.required_capability)
            self.completed_tasks.append(task.task_id)

    def customer_state(self, tasks: List[TaskContext], needs_connection: bool = False) -> str:
        """Customer projection: WORKING / NEEDS YOU / DONE.

        Raw provider internals (429, quota strings, stack traces) never
        appear here: this function does not even accept error text.
        """
        pending = [t for t in tasks if t.task_id not in self.completed_tasks]
        if not pending:
            return "DONE"
        if any(t.requires_human_gate for t in pending):
            return "NEEDS YOU"
        if needs_connection:
            return "NEEDS YOU"
        return "WORKING"

    def hibernate_if_quota_blocked_idle(
        self,
        hibernator: LaneHibernator,
        checkpoint,
        local_tasks: List[TaskContext],
        provider_tasks: List[TaskContext],
    ) -> Optional[Dict[str, Any]]:
        """Checkpoint + release + HIBERNATED when the lane is quota-blocked/idle.

        Returns the release report, or None when the lane still has useful
        work (local units, a healthy circuit, or an authorized fallback).
        """
        if provider_tasks:
            capability = provider_tasks[0].required_capability
            circuits_open = self.breaker.is_open("muse", capability)
        else:
            circuits_open = False
        fallback_available = any(
            self.router.find_fallback("muse", t) is not None for t in provider_tasks
        )
        if should_hibernate(
            [t.task_id for t in local_tasks],
            [t.task_id for t in provider_tasks],
            circuits_open,
            fallback_available,
        ):
            return hibernator.hibernate(checkpoint)
        return None

