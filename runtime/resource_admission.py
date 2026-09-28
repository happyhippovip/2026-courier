"""
Deliverable: Resource Admission
"""
from dataclasses import dataclass
from typing import Dict

@dataclass
class ResourceQuotas:
    max_cpu_percent: float = 80.0
    max_ram_mb: int = 4096
    max_swap_mb: int = 1024
    max_disk_mb: int = 10240
    max_heavy_jobs: int = 1

class ResourceAdmissionController:
    """
    Handles resource admission for CPU, RAM, swap, disk, 
    and limits heavy jobs.
    """
    def __init__(self, quotas: ResourceQuotas = None):
        self.quotas = quotas or ResourceQuotas()
        self.active_heavy_jobs = 0

    def admit_job(self, requested_ram_mb: int, requested_cpu: float, is_heavy: bool = False) -> Dict[str, bool]:
        """
        Evaluate if the requested job can be admitted based on current resource quotas.
        """
        decision = {
            "admitted": True,
            "reason": ""
        }

        if is_heavy and self.active_heavy_jobs >= self.quotas.max_heavy_jobs:
            decision["admitted"] = False
            decision["reason"] = "MAX_HEAVY_JOBS limit reached."
            return decision

        if requested_ram_mb > self.quotas.max_ram_mb:
            decision["admitted"] = False
            decision["reason"] = f"Requested RAM ({requested_ram_mb} MB) exceeds limit ({self.quotas.max_ram_mb} MB)."
            return decision
            
        if requested_cpu > self.quotas.max_cpu_percent:
            decision["admitted"] = False
            decision["reason"] = f"Requested CPU ({requested_cpu}%) exceeds limit ({self.quotas.max_cpu_percent}%)."
            return decision

        # Mark job as admitted
        if is_heavy:
            self.active_heavy_jobs += 1

        return decision

    def release_job(self, is_heavy: bool = False) -> None:
        """Release resources after a job completes."""
        if is_heavy and self.active_heavy_jobs > 0:
            self.active_heavy_jobs -= 1
