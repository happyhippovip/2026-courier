import datetime
import enum
import json
from pathlib import Path
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from scripts.provider_circuit import ProviderCircuitBreaker, ProviderState
from scripts.automation_wake_coalescing import AutomationContext, AutoState, Wakeup
from scripts.provider_hibernation import (ContinuationCheckpoint, LaneHibernator,
                                         LaneState, save_continuation, should_hibernate)

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
    fingerprint: str = ""
    authority_scope: str = ""

@dataclass
class Provider:
    id: str
    is_authorized: bool = False
    capabilities: List[str] = None
    family: str = ""
    authority_scopes: Tuple[str, ...] = ()

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        self.family = self.family or self.id

class LocalReadyPlanner:
    def get_local_ready_work(self, tasks: List[TaskContext]) -> List[TaskContext]:
        return [t for t in tasks if t.is_deterministic]

class AuthorizedProviderRouter:
    def __init__(self, breaker: ProviderCircuitBreaker, get_providers):
        self.breaker = breaker
        self.get_providers = get_providers

    def find_fallback(self, failed_provider_id: str, task: TaskContext) -> Optional[Provider]:
        if task.effect_uncertain or task.requires_human_gate:
            return None # Effect unknown, cannot blindly retry
        primary = next((p for p in self.get_providers() if p.id == failed_provider_id), None)
        for provider in self.get_providers():
            if provider.id == failed_provider_id:
                continue
            if not provider.is_authorized:
                continue
            # Fallback is a different authorized provider, never account rotation.
            if primary is not None and provider.family == primary.family:
                continue
            if task.required_capability not in provider.capabilities:
                continue
            if task.authority_scope and task.authority_scope not in provider.authority_scopes:
                continue
            if self.breaker.is_open(provider.id, task.required_capability):
                continue
            if self.breaker.get_circuit(provider.id, task.required_capability).state not in (
                    ProviderState.AVAILABLE, ProviderState.DEGRADED):
                continue  # A half-open connection needs its own bounded probe first.
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
    def __init__(self, *, primary_provider="muse", providers=None, state_path=None,
                 probe_provider=None, refresh_repository=None, reconcile_ownership=None,
                 authority_check=None, execute_provider=None, execute_local=None):
        """One bounded wake, not a timer or provider launcher.

        Durable mode requires explicitly connected providers and trusted hooks.
        refresh_repository must FETCH current repository truth. reconcile_ownership
        returns a context manager holding/fencing the existing mutable-scope lease
        throughout dispatch, and yields a freshly authorized next-unit plan.
        Execution hooks must use the connector/capability/grant contract and return
        DONE only with accepted evidence. Missing hooks fail closed. No credentials,
        account discovery, credit purchases, window creation or timers live here.
        probe_provider(connection, capability, timeout_s) must enforce its supplied
        I/O deadline using the existing bounded connector/worker runtime.
        """
        if primary_provider == "codex" and state_path is None:
            raise ValueError("Codex continuity requires durable state_path")
        self.primary_provider = primary_provider
        self.state_path = Path(state_path) if state_path is not None else None
        self.breaker = ProviderCircuitBreaker(isolated=self.state_path is not None)
        self.providers = providers if providers is not None else [
            Provider(id="muse", is_authorized=True, capabilities=["completion"]),
            Provider(id="gemini", is_authorized=True, capabilities=["completion"]),
            Provider(id="codex", is_authorized=False, capabilities=["completion"]),
        ]
        if self.state_path is not None and providers is None:
            self.providers = [Provider(id=p.id, capabilities=p.capabilities) for p in self.providers]
        self.probe_provider = probe_provider
        self.refresh_repository = refresh_repository
        self.reconcile_ownership = reconcile_ownership
        self.authority_check = authority_check
        self.execute_provider_hook = execute_provider
        self.execute_local_hook = execute_local
        self.lane = LaneHibernator()
        self.started = []
        self.saved_tasks = {}
        self.stop_reason = "IDLE"
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
        if self.state_path is not None:
            return self._durable_wake(tasks, checkpoint, hibernator)
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
                    self.execute_with_provider(task, self.primary_provider)
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
        if task.effect_uncertain:
            return WorkState.EFFECT_UNKNOWN
        if task.is_deterministic:
            return WorkState.LOCAL_READY
            
        if self.breaker.is_open(self.primary_provider, task.required_capability):
            fallback = self.router.find_fallback(self.primary_provider, task)
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
            circuits_open = self.breaker.is_open(self.primary_provider, capability)
        else:
            circuits_open = False
        fallback_available = any(
            self.router.find_fallback(self.primary_provider, t) is not None for t in provider_tasks
        )
        if should_hibernate(
            [t.task_id for t in local_tasks],
            [t.task_id for t in provider_tasks],
            circuits_open,
            fallback_available,
        ):
            return hibernator.hibernate(checkpoint)
        return None

    # Durable provider continuity extends this scheduler; no second scheduler.
    def _load(self, checkpoint=None, hibernator=None):
        if hibernator is not None:
            self.lane = hibernator
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if data["schema"] != 1 or data["primary_provider"] != self.primary_provider:
                raise ValueError("incompatible provider continuation")
            restored = LaneHibernator.from_dict(data["lane"])
            if checkpoint and checkpoint.workkey != restored.checkpoint.workkey:
                raise ValueError("checkpoint belongs to another workkey")
            # Callables never come from disk. Keep explicitly registered hooks.
            self.lane.state = restored.state
            self.lane.checkpoint = restored.checkpoint
            self.lane.release_report = restored.release_report
            self.lane.resources.update(restored.resources)
            self.completed_tasks = data["completed_tasks"]
            self.started = data["started"]
            self.saved_tasks = data.get("tasks", {})
            self.breaker.restore(data["circuits"])
        elif checkpoint is not None:
            self.lane.checkpoint = ContinuationCheckpoint.from_dict(checkpoint.to_dict())
        if self.lane.checkpoint is None or not self.lane.checkpoint.workkey:
            raise ValueError("a durable workkey/checkpoint is required")
        if self.lane.checkpoint.provider_connection_id not in ("", self.primary_provider):
            raise ValueError("checkpoint connection mismatch")
        self.lane.checkpoint.provider_connection_id = self.primary_provider

    def _save(self):
        save_continuation(self.state_path, {
            "schema": 1, "primary_provider": self.primary_provider,
            "lane": self.lane.to_dict(), "circuits": self.breaker.to_dict(),
            "completed_tasks": self.completed_tasks, "started": self.started,
            "tasks": self.saved_tasks,
            "stop_reason": self.stop_reason,
        })

    def record_provider_failure(self, checkpoint, error_code, message, *,
                                capability="completion", reset_time=None, retry_after=None,
                                expected_checkpoint=None):
        """Accept trusted connector metadata and compare-and-swap progress updates.

        When progress changed, expected_checkpoint is the last observed checkpoint
        dictionary. Compare under the owner lock; never silently discard new work
        or let a delayed event overwrite a newer continuation.
        """
        from courier_worker.host import acquire_home_lock, release_home_lock
        if self.state_path is None:
            raise ValueError("durable state is required")
        lock = acquire_home_lock(str(self.state_path) + ".owner")
        try:
            self._load(checkpoint)
            current = self.lane.checkpoint.to_dict()
            incoming = checkpoint.to_dict()
            incoming["provider_connection_id"] = incoming["provider_connection_id"] or self.primary_provider
            if expected_checkpoint is not None:
                if expected_checkpoint != current:
                    raise ValueError("stale expected_checkpoint; reload current continuation")
                for key in ("workkey", "project", "mutable_scope", "provider_connection_id", "authority_boundary"):
                    if incoming[key] != current[key]:
                        raise ValueError(f"checkpoint cannot retarget {key}")
                # Accepted evidence is monotonic, even if the producer sent only
                # its latest accepted unit. Started/uncertain records stay intact.
                for key in ("completed_fingerprints", "source_refs"):
                    incoming[key] = list(dict.fromkeys(current[key] + incoming[key]))
                self.lane.checkpoint = ContinuationCheckpoint.from_dict(incoming)
            else:
                # Failure metadata is replaced below, not a progress update.
                progress = lambda value: {k: v for k, v in value.items()
                                          if k not in ("provider_failure_class", "provider_reset_time")}
                if progress(incoming) != progress(current):
                    raise ValueError("changed progress requires expected_checkpoint")
            if retry_after is not None:
                if not isinstance(retry_after, (int, float)) or not 0 <= retry_after < float("inf"):
                    raise ValueError("invalid trusted retry_after")
                reset_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=retry_after)
            self.breaker.record_failure(self.primary_provider, capability, error_code, message, reset_time)
            self._checkpoint_failure(capability)
            self._hibernate()
        finally:
            release_home_lock(lock)

    def _checkpoint_failure(self, capability):
        circuit = self.breaker.get_circuit(self.primary_provider, capability)
        cp = self.lane.checkpoint
        cp.provider_failure_class = circuit.state.value
        cp.provider_reset_time = circuit.reset_time.isoformat() if circuit.reset_time else None
        self.stop_reason = "WAITING_PROVIDER"
        self._save()

    def _hibernate(self):
        self.lane.hibernate(self.lane.checkpoint, persist=self._save)
        if self.lane.release_report.get("failed"):
            self.stop_reason = "RESOURCE_RELEASE_FAILED"
            self._save()

    def next_wake_at(self):
        """One boundary for the EXISTING wake source; None means remain parked.

        No timer is installed. A consumed/in-flight probe cannot schedule itself.
        Call after handle_wake/record_provider_failure has loaded durable state.
        """
        resets = [c.reset_time for c in self.breaker.circuits.values()
                  if c.reset_time and not c.probe_in_flight and c.state in (
                      ProviderState.QUOTA_EXHAUSTED, ProviderState.RATE_LIMITED,
                      ProviderState.PROVIDER_UNAVAILABLE)]
        return min(resets) if resets else None

    def _permitted(self, provider, task):
        return bool(provider and provider.is_authorized
                    and task.required_capability in provider.capabilities
                    and (not task.authority_scope or task.authority_scope in provider.authority_scopes)
                    and self.authority_check is not None
                    and self.authority_check(provider, task, self.lane.checkpoint) is True)

    def _durable_wake(self, tasks, checkpoint, hibernator):
        from courier_worker.host import acquire_home_lock, release_home_lock, HostBusy
        try:
            lock = acquire_home_lock(str(self.state_path) + ".owner")
        except HostBusy:
            return "COALESCED"  # no parallel state writer or provider call
        try:
            self._load(checkpoint, hibernator)
            cp = self.lane.checkpoint
            for task in tasks:
                previous = self.saved_tasks.get(task.task_id)
                if previous is not None and previous != asdict(task):
                    raise ValueError("task identity changed; reconcile explicitly")
                self.saved_tasks[task.task_id] = asdict(task)
            self._save()
            tasks = [TaskContext(**value) for value in self.saved_tasks.values()]
            pending = [t for t in tasks if t.task_id not in self.completed_tasks
                       and (t.fingerprint or t.task_id) not in cp.completed_fingerprints]
            pending = [t for t in pending if t.task_id not in self.started
                       and not t.effect_uncertain and not t.requires_human_gate]
            if not pending:
                self.stop_reason = ("EFFECT_UNKNOWN" if self.started or any(t.effect_uncertain for t in tasks)
                                    else "IDLE_NO_NEW_WORK")
                self._save()
                return self.stop_reason
            primary = next((p for p in self.providers if p.id == self.primary_provider), None)
            runnable = []
            for task in pending:
                if task.is_deterministic:
                    if self.execute_local_hook is not None:
                        runnable.append((task, None))
                    continue
                if not self._permitted(primary, task):
                    continue
                circuit = self.breaker.get_circuit(self.primary_provider, task.required_capability)
                circuit.check_circuit()
                if circuit.state == ProviderState.RECOVERY_PROBE_DUE:
                    if self.probe_provider is not None and circuit.claim_probe():
                        self._save()  # crash after this point MUST NOT send a second probe
                        self.provider_calls.append((self.primary_provider, "RECOVERY_PROBE"))
                        try:
                            ok, code, message = self.probe_provider(self.primary_provider, task.required_capability, 5.0)
                        except Exception:
                            ok, code, message = False, 503, "probe failed"
                        if ok is True:
                            circuit.record_success()
                            self._save()  # availability is not task completion
                        else:
                            circuit.record_failure(code, message)
                            if circuit.state == ProviderState.DEGRADED:
                                circuit.state = ProviderState.PROVIDER_UNAVAILABLE
                            self._checkpoint_failure(task.required_capability)
                if circuit.state in (ProviderState.AVAILABLE, ProviderState.DEGRADED):
                    runnable.append((task, primary))
                else:
                    fallback = self.router.find_fallback(self.primary_provider, task)
                    if self._permitted(fallback, task):
                        runnable.append((task, fallback))
            if not runnable:
                self.stop_reason = "WAITING_PROVIDER"
                self._hibernate()
                return self.stop_reason
            if self.refresh_repository is None or self.reconcile_ownership is None:
                self.stop_reason = "WAITING_RECONCILIATION"
                self._save()
                return self.stop_reason
            # Fetch precedes ownership reconciliation and every execution callback.
            truth = self.refresh_repository(cp)
            if not truth or not truth.get("repo_sha") or not truth.get("branch"):
                raise ValueError("fresh repository truth required")
            guard = self.reconcile_ownership(cp, truth)
            if guard is None:
                self.stop_reason = "WAITING_OWNERSHIP"
                self._save()
                return self.stop_reason
            with guard as plan:
                if (not plan or plan.get("workkey") != cp.workkey
                        or plan.get("mutable_scope") != cp.mutable_scope):
                    self.stop_reason = "WAITING_OWNERSHIP"
                    self._save()
                    return self.stop_reason
                cp.repo_sha, cp.branch, cp.pr = truth["repo_sha"], truth["branch"], truth.get("pr", "")
                cp.next_units = list(plan.get("next_units", []))  # never trust stale NEXT
                cp.next_action = plan.get("next_action", "")
                self._save()
                for task, provider in runnable:
                    if task.task_id not in cp.next_units:
                        continue
                    if provider is not None:
                        if not self._permitted(provider, task) or self.execute_provider_hook is None:
                            continue
                        # Another task in this wake may just have exhausted it.
                        if self.breaker.is_open(provider.id, task.required_capability):
                            continue
                        if self.lane.state == LaneState.HIBERNATED:
                            if any(r.released and name not in self.lane.reacquire_hooks
                                   for name, r in self.lane.resources.items()):
                                self.stop_reason = "WAITING_RESOURCE_CONNECTOR"
                                self._save()
                                return self.stop_reason
                            self.lane.resume()
                    self.started.append(task.task_id)
                    self._save()  # execution uncertainty survives process/provider failure
                    if provider is None:
                        result = self.execute_local_hook(task, cp)
                    else:
                        self.provider_calls.append((provider.id, task.task_id))
                        result = self.execute_provider_hook(provider, task, cp)
                    evidence = result.get("evidence")
                    if (result.get("status") == "DONE" and isinstance(evidence, list)
                            and evidence and all(isinstance(ref, str) and ref for ref in evidence)):
                        self.completed_tasks.append(task.task_id)
                        cp.completed_fingerprints.append(task.fingerprint or task.task_id)
                        cp.source_refs.extend(result["evidence"])
                        self.started.remove(task.task_id)
                    elif result.get("status") in ("QUOTA_EXHAUSTED", "RATE_LIMITED") and provider:
                        self.breaker.record_failure(provider.id, task.required_capability, 429,
                                                    result["status"], result.get("reset_time"))
                        if result.get("no_effect") is True:
                            self.started.remove(task.task_id)
                        if provider.id == self.primary_provider:
                            self._checkpoint_failure(task.required_capability)
                    self._save()
            self.stop_reason = "EFFECT_UNKNOWN" if self.started else "CHECKPOINTED"
            if any(self.breaker.is_open(self.primary_provider, t.required_capability)
                   for t in pending if not t.is_deterministic and t.task_id not in self.completed_tasks):
                self.stop_reason = "WAITING_PROVIDER"
                self._hibernate()
            self._save()
            return self.stop_reason
        finally:
            release_home_lock(lock)
