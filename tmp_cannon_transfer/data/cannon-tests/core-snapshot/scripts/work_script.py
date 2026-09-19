import time

class WorkScript:
    def __init__(self, task_id):
        self.task_id = task_id
        self.dispatch_approved = False
        self.pulse_count = 0

    def approve_dispatch(self):
        """Controls dispatch authorization (Freigabe)."""
        self.dispatch_approved = True
        return {"task": self.task_id, "status": "APPROVED"}

    def visual_pulse(self, cycles=1):
        """Visual pulse animation. 0 calls."""
        for _ in range(cycles):
            self.pulse_count += 1
            # Reine Animation
            time.sleep(0.001)
        return self.pulse_count
