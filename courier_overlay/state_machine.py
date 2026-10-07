import dataclasses
from typing import Dict, List, Optional
from datetime import datetime
from courier_overlay.event_bus import read_events

@dataclasses.dataclass
class WorkerState:
    agent_id: str
    current_task: Optional[str] = None
    status: str = "IDLE"
    last_summary: str = ""
    last_update: Optional[datetime] = None

class OverlayStateMachine:
    def __init__(self, bus_path: str):
        self.bus_path = bus_path
        self.workers: Dict[str, WorkerState] = {}
        
    def process_event(self, event: dict):
        """Fold an event into the current state."""
        agent = event["agent_id"]
        if agent not in self.workers:
            self.workers[agent] = WorkerState(agent_id=agent)
            
        worker = self.workers[agent]
        worker.last_summary = event["short_summary"]
        worker.last_update = datetime.fromisoformat(event["timestamp"])
        
        evt_type = event["event_type"]
        if evt_type in ("WORKER_CLAIMED", "TASK_ASSIGNED"):
            worker.current_task = event["task_id"]
            worker.status = "ASSIGNED"
        elif evt_type in ("WORKER_STARTED", "WORKER_PROGRESS", "CUSTOMS_ENTER"):
            worker.status = "WORKING"
        elif evt_type in ("TASK_COMPLETE", "RESULT_APPROVED"):
            worker.status = "IDLE"
            worker.current_task = None
        elif evt_type in ("TASK_BLOCKED", "CUSTOMS_REJECTED", "RESULT_REJECTED"):
            worker.status = "BLOCKED"
            
    def sync(self):
        """Read all events from bus and fold."""
        events = read_events(self.bus_path)
        # Assuming replay yields in order
        for e in events:
            self.process_event(e)
            
    def get_snapshot(self) -> List[WorkerState]:
        return list(self.workers.values())
