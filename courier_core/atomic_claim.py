"""Atomic Task Claim & Compare-and-Swap Coordination Architecture (CP-08 / P08).

Ensures that when multiple free, qualified workers concurrently race to claim pending
tasks, exactly one worker is awarded the lease, while competing losers are rejected
without mutating the winner's lease, attempt count, or dispatch identity.

Invariants (CP-08 Acceptance):
1. Exactly one claim wins per queued task.
2. The loser alters neither the attempt count nor the lease of the winner.
3. Test fixture and execution require zero model calls (100% deterministic local concurrency).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ClaimRaceResult:
    worker_id: str
    task: Optional[dict]
    acquired: bool
    timestamp: float


class AtomicClaimRacer:
    """Barrier-synchronized race harness for testing concurrent claim mechanics."""

    def __init__(self, claim_callables: Dict[str, Callable[[], Optional[dict]]]):
        """Args:

        claim_callables: Mapping of worker_id -> zero-arg callable executing the claim.
        """
        self.callables = claim_callables
        self.count = len(claim_callables)
        self.barrier = threading.Barrier(self.count)
        self.results: list[ClaimRaceResult] = []
        self._lock = threading.Lock()

    def run_race(self, timeout_s: float = 5.0) -> list[ClaimRaceResult]:
        """Execute all claim callables simultaneously after a barrier synchronization."""
        threads = []
        results: list[ClaimRaceResult] = []

        def _worker_fn(wid: str, fn: Callable[[], Optional[dict]]) -> None:
            import time
            try:
                self.barrier.wait(timeout=timeout_s)
            except threading.BrokenBarrierError:
                pass
            res = fn()
            t = time.time()
            with self._lock:
                results.append(
                    ClaimRaceResult(
                        worker_id=wid,
                        task=res,
                        acquired=res is not None and (res.get("task") is not None if isinstance(res, dict) and "task" in res else True),
                        timestamp=t,
                    )
                )

        for wid, fn in self.callables.items():
            t = threading.Thread(target=_worker_fn, args=(wid, fn), name=f"ClaimRacer-{wid}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=timeout_s)

        return results

    @staticmethod
    def verify_single_winner_invariants(results: list[ClaimRaceResult], expected_task_id: str) -> Tuple[ClaimRaceResult, list[ClaimRaceResult]]:
        """Assert CP-08 acceptance: Exactly one winner, losers received nothing."""
        winners = [r for r in results if r.acquired and _extract_task_id(r.task) == expected_task_id]
        losers = [r for r in results if not r.acquired or _extract_task_id(r.task) is None]

        if len(winners) != 1:
            raise AssertionError(f"Expected exactly 1 winner, found {len(winners)}: {winners}")
        if len(losers) != len(results) - 1:
            raise AssertionError(f"Expected {len(results) - 1} losers, found {len(losers)}: {losers}")

        return winners[0], losers


def _extract_task_id(res: Optional[dict]) -> Optional[str]:
    if not res or not isinstance(res, dict):
        return None
    if "task" in res:
        task_data = res["task"]
        return task_data.get("task_id") if isinstance(task_data, dict) else None
    return res.get("task_id")
