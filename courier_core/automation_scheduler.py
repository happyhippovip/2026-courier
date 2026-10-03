from dataclasses import dataclass
from typing import List, Callable, Optional
import time

@dataclass
class ScheduledTask:
    task_id: str
    execute_at: float
    action: str
    payload: str

class DurableScheduler:
    """MAC-06: Advance durable scheduling semantics."""
    def __init__(self):
        self._tasks: List[ScheduledTask] = []
        
    def schedule(self, task_id: str, delay_seconds: float, action: str, payload: str) -> None:
        exec_at = time.time() + delay_seconds
        self._tasks.append(ScheduledTask(task_id, exec_at, action, payload))
        
    def get_due_tasks(self, current_time: Optional[float] = None) -> List[ScheduledTask]:
        if current_time is None:
            current_time = time.time()
        due = [t for t in self._tasks if t.execute_at <= current_time]
        self._tasks = [t for t in self._tasks if t.execute_at > current_time]
        return due
