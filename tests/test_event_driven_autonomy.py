from dataclasses import dataclass
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.run_live_production_goal as runtime
from scripts.live_worker_registry import AvailabilityClass, LiveWorkerRegistry, WorkerState
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.opportunity_queue import Opportunity, OpportunityQueue


@dataclass
class FakeOpportunity:
    opportunity_id: str
    status: str = "READY"
    description: str = "real task"
    allowed_actions: tuple[str, ...] = ("VALIDATE",)


class FakeQueue:
    def __init__(self, opportunities=()):
        self.opportunities = {opp.opportunity_id: opp for opp in opportunities}
        self.add_calls = 0

    def get_opportunity(self, task_id):
        return self.opportunities.get(task_id)

    def list_opportunities(self):
        return list(self.opportunities.values())

    def add_opportunity(self, _opportunity):
        self.add_calls += 1


def dispatch_recording(recommendations, opportunities=()):
    calls = []
    active, count = runtime.dispatch_recommendations(
        recommendations,
        FakeQueue(opportunities),
        "root goal",
        set(),
        dispatch_fn=lambda *args: calls.append(args),
    )
    return active, count, calls


def test_identical_idle_planning_uses_bounded_backoff_not_a_tight_loop():
    recommendations = {"CODEX": {"recommended_action": "STANDBY_SAFE_IDLE"}}
    assert runtime.recommendation_fingerprint(recommendations) == runtime.recommendation_fingerprint(recommendations)
    delays = [runtime.idle_backoff_seconds(cycle) for cycle in range(1, 10)]
    assert delays == sorted(delays)
    assert delays[0] > 0
    assert delays[-1] == runtime.MAX_IDLE_BACKOFF_SECONDS


def test_idle_backoff_can_never_become_a_3600_second_dormant_wait():
    assert runtime.idle_backoff_seconds(1000) == runtime.MAX_IDLE_BACKOFF_SECONDS
    assert runtime.MAX_IDLE_BACKOFF_SECONDS <= 15


def test_codex_unavailable_does_not_block_independent_windows_work(tmp_path):
    registry = LiveWorkerRegistry(repo_dir=tmp_path)
    codex = registry.register_worker(
        "CODEX", "CODING", "CODEX", AvailabilityClass.PRIMARY_BUILDER
    )
    codex.state = WorkerState.PROVIDER_ERROR.value
    registry._save_worker_record(codex)
    windows = registry.register_worker(
        "WINDOWS", "WINDOWS_NATIVE", "WINDOWS", AvailabilityClass.PERSISTENT_HOST
    )
    windows.state = WorkerState.AVAILABLE.value
    registry._save_worker_record(windows)

    queue = OpportunityQueue(repo_dir=tmp_path)
    queue.add_opportunity(
        Opportunity(
            opportunity_id="codex-pending-task",
            source="TEST",
            objective_id="root",
            project="Courier",
            description="Codex task remains pending",
            target_agent="CODEX",
            allowed_scope=["codex-safe-scope"],
        )
    )
    windows_task = Opportunity(
        opportunity_id="windows-real-task",
        source="TEST",
        objective_id="root",
        project="Courier",
        description="Independent Windows task",
        target_agent="WINDOWS",
        allowed_scope=["windows-safe-scope"],
    )
    queue.add_opportunity(windows_task)

    recommendations = NextSafeWorkRouter(repo_dir=tmp_path).evaluate_next_safe_work()["recommendations"]
    calls = []
    active, count = runtime.dispatch_recommendations(
        recommendations,
        queue,
        "root goal",
        set(),
        dispatch_fn=lambda *args: calls.append(args),
    )
    assert active is True
    assert count == 1
    assert [call[1] for call in calls] == ["WINDOWS"]


def test_empty_queue_is_wakeable_and_does_not_generate_health_check_work():
    queue = FakeQueue()
    assert runtime.quiescence_state(queue.list_opportunities()) == "QUIESCENT_WAKEABLE"
    assert queue.add_calls == 0
    source = runtime.Path(runtime.__file__).read_text(encoding="utf-8")
    assert "plan-goal-eval-" not in source
    assert 'allowed_actions=["HEALTH_CHECK"]' not in source


def test_real_next_work_is_routed_immediately_when_available():
    task = FakeOpportunity("real-next-task")
    active, count, calls = dispatch_recording(
        {
            "CODEX": {
                "available": True,
                "recommended_action": "DISPATCH_TASK_real-next-task",
                "task_fingerprint": "fp-real",
                "scope": ["scripts/real.py"],
            }
        },
        [task],
    )
    assert active is True
    assert count == 1
    assert calls[0] == (
        "real-next-task",
        "CODEX",
        "VALIDATE",
        "real task",
        ["scripts/real.py"],
        "fp-real",
    )
