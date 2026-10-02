import datetime
import enum
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from scripts.provider_circuit import ProviderCircuitBreaker, ProviderState, CircuitState
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
    accepted_evidence: Optional[str] = None

@dataclass
class Provider:
    id: str
    is_authorized: bool = False
    capabilities: List[str] = None
    account_id: str = "default"

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
            if self.breaker.is_open(provider.id, provider.account_id, task.required_capability):
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
        self.pending_handoffs: List[Tuple[str, str, dict]] = []
        # Every real provider attempt is logged here as (provider_id, task_id).
        # Deterministic fake-provider tests assert on this log instead of
        # touching the network. A recovery probe counts as one attempt.
        self.provider_calls: List[Tuple[str, str]] = []
        # Optional fake probe used after reset: () -> (ok, code, message).
        # When None, a claimed probe silently re-arms the circuit (success)
        # but does NOT complete the task.
        self.recovery_probe: Optional[Callable[[], Tuple[bool, int, str]]] = None

    def handle_wake(self, wake_id: str, tasks: List[TaskContext]):
        self.automation_ctx.enqueue_wake(Wakeup(trigger_id=wake_id))
        
        if not self.automation_ctx.start_execution():
            return

        try:
            task_by_id = {t.task_id: t for t in tasks}
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
            
            # Consume pending handoffs created in this or prior wakes
            handoffs_to_process = self.pending_handoffs.copy()
            self.pending_handoffs.clear()
            for fallback_id, task_id, handoff in handoffs_to_process:
                if task_id in self.completed_tasks:
                    continue
                task = task_by_id.get(task_id)
                if not task:
                    # Task not in current wake, preserve handoff for later
                    self.pending_handoffs.append((fallback_id, task_id, handoff))
                    continue
                # Execute on the fallback provider.
                self.execute_with_provider(task, fallback_id)
                
        except OSError as e:
            if e.errno in (24, 23): # EMFILE or ENFILE
                self.automation_ctx.resource_exhausted()
        finally:
            self.automation_ctx.finish_execution()

    def evaluate_task_state(self, task: TaskContext) -> WorkState:
        if task.requires_human_gate:
            return WorkState.WAITING_AUTHORITY
        if task.is_deterministic:
            return WorkState.LOCAL_READY
            
        if self.breaker.is_open("muse", self._get_account_id("muse"), task.required_capability):
            fallback = self.router.find_fallback("muse", task)
            if fallback:
                return WorkState.PROVIDER_READY
            return WorkState.WAITING_PROVIDER
            
        return WorkState.PROVIDER_READY

    def execute_local(self, task: TaskContext):
        # A local task isn't magically complete without execution.
        if task.accepted_evidence is not None:
            self.completed_tasks.append(task.task_id)

    def _get_account_id(self, provider_id: str) -> str:
        for p in self.providers:
            if p.id == provider_id:
                return p.account_id
        return "default"

    def execute_with_provider(self, task: TaskContext, primary_provider: str):
        if self.breaker.is_open(primary_provider, self._get_account_id(primary_provider), task.required_capability):
            fallback = self.router.find_fallback(primary_provider, task)
            if fallback:
                handoff = self.router.create_compact_handoff(task, primary_provider, fallback)
                self.pending_handoffs.append((fallback.id, task.task_id, handoff))
                # HANDOFF CREATED != TASK COMPLETE.
                # Task is NOT added to completed_tasks until fallback
                # actually executes and produces accepted evidence.
            else:
                pass # WAIT
        else:
            circuit = self.breaker.get_circuit(primary_provider, self._get_account_id(primary_provider), task.required_capability)
            if circuit.state == ProviderState.RECOVERY_PROBE_DUE:
                # Only one bounded recovery probe per episode; the rest wait.
                if not circuit.claim_probe():
                    return
                self.provider_calls.append((primary_provider, task.task_id))
                if self.recovery_probe is not None:
                    ok, code, message = self.recovery_probe()
                    if ok:
                        self.breaker.record_success(primary_provider, self._get_account_id(primary_provider), task.required_capability)
                        # RECOVERY PROBE SUCCESS != TASK COMPLETE.
                        # The probe re-arms the circuit; the task must still
                        # be dispatched on a subsequent wake cycle.
                    else:
                        self.breaker.record_failure(
                            primary_provider, self._get_account_id(primary_provider), task.required_capability, code, message
                        )
                        # Bounded re-arm: ensure reset_time is in the future
                        # to prevent immediate re-probing. A consumed or missing
                        # reset leaves the circuit permanently wedged otherwise.
                        now = datetime.datetime.now(datetime.timezone.utc)
                        rt = CircuitState._as_aware(circuit.reset_time)
                        if rt is None or rt <= now:
                            import random
                            failures = max(1, circuit.consecutive_failures)
                            base_delay = min(60 * (2 ** (failures - 1)), 3600)
                            jitter = random.uniform(0, 0.2 * base_delay)
                            circuit.reset_time = now + datetime.timedelta(seconds=base_delay + jitter)
                    return
                self.breaker.record_success(primary_provider, self._get_account_id(primary_provider), task.required_capability)
                # Probe without a custom probe function re-arms only.
                return
            if hasattr(self, "simulate_error") and self.simulate_error_provider == primary_provider:
                self.provider_calls.append((primary_provider, task.task_id))
                self.breaker.record_failure(
                    primary_provider,
                    self._get_account_id(primary_provider),
                    task.required_capability,
                    self.simulate_error_code,
                    self.simulate_error_message,
                    getattr(self, "simulate_reset_time", None)
                )

                fallback = self.router.find_fallback(primary_provider, task)
                if fallback:
                    handoff = self.router.create_compact_handoff(task, primary_provider, fallback)
                    self.pending_handoffs.append((fallback.id, task.task_id, handoff))
                    # Error+handoff: task is NOT complete until fallback executes.
                return

            self.provider_calls.append((primary_provider, task.task_id))
            self.breaker.record_success(primary_provider, self._get_account_id(primary_provider), task.required_capability)
            # PROVIDER CALL STARTED != DONE. PROVIDER RETURNED != DONE.
            if task.accepted_evidence is not None:
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
            circuits_open = self.breaker.is_open("muse", self._get_account_id("muse"), capability)
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

