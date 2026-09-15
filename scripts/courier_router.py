from dataclasses import dataclass
from typing import List, Optional
from courier_admission_control import TaskPacket

@dataclass
class WorkerTarget:
    target_id: str
    platform: str
    capabilities: List[str]
    cost_per_minute: float
    active_slots: int
    max_slots: int

class CapabilityCostRouter:
    def route(self, packet: TaskPacket, targets: List[WorkerTarget]) -> Optional[WorkerTarget]:
        eligible_targets = []
        
        req_plat = packet.required_platform.lower()
        if req_plat == "mac":
            req_plat = "darwin"
        elif req_plat == "windows":
            req_plat = "win32"
            
        for target in targets:
            # Platform check
            tgt_plat = target.platform.lower()
            if tgt_plat == "mac": tgt_plat = "darwin"
            if tgt_plat == "windows": tgt_plat = "win32"
            
            if req_plat != "any" and tgt_plat != req_plat:
                continue
                
            # Capability check
            if packet.required_capability != "any" and packet.required_capability not in target.capabilities:
                continue
                
            # Capacity check
            if target.active_slots >= target.max_slots:
                continue
                
            # Cost vs Budget check (assuming at least 1 minute)
            if target.cost_per_minute > packet.budget:
                continue
                
            eligible_targets.append(target)
            
        if not eligible_targets:
            return None
            
        # Route to the cheapest available target
        eligible_targets.sort(key=lambda t: t.cost_per_minute)
        return eligible_targets[0]
