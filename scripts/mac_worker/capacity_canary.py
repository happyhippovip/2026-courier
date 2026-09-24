#!/usr/bin/env python3
import subprocess
import time
import re

class CapacityGovernor:
    def __init__(self, desired_capacity=73, start_capacity=4):
        self.desired_capacity = desired_capacity
        self.admitted_capacity = start_capacity
        self.state = "RAMPING"
        self.last_metrics = None
        
    def get_real_metrics(self):
        try:
            # Swap usage string example: "vm.swapusage: total = 3072.00M  used = 1543.20M  free = 1528.79M  (encrypted)"
            swap_out = subprocess.check_output(["sysctl", "vm.swapusage"]).decode()
            match = re.search(r'used = ([\d\.]+)M', swap_out)
            swap_used_mb = float(match.group(1)) if match else 0.0
            
            # Load average
            load_out = subprocess.check_output(["sysctl", "vm.loadavg"]).decode()
            # Example: "vm.loadavg: { 1.55 1.70 1.95 }"
            load_1m = float(re.findall(r'[\d\.]+', load_out)[0])
            
            return {"swap_mb": swap_used_mb, "load_1m": load_1m}
        except Exception as e:
            return {"swap_mb": 0.0, "load_1m": 0.0}
            
    def evaluate(self, current_metrics=None):
        if not current_metrics:
            current_metrics = self.get_real_metrics()
            
        print(f"[METRICS] Swap: {current_metrics['swap_mb']}MB | Load: {current_metrics['load_1m']}")
            
        if self.last_metrics:
            swap_delta = current_metrics["swap_mb"] - self.last_metrics["swap_mb"]
            load = current_metrics["load_1m"]
            
            # Simulated thresholds for the canary
            if swap_delta > 500 or load > 10.0:
                self.state = "BACKOFF"
                self.admitted_capacity = max(4, self.admitted_capacity - 4)
                print(">>> WARNING: Resources critical! BACKOFF triggered. Lowering capacity.")
            elif swap_delta > 100 or load > 5.0:
                self.state = "HOLD"
                print(">>> NOTICE: Resources stressed. HOLD triggered. Pausing scale up.")
            else:
                self.state = "RAMPING"
                if self.admitted_capacity < self.desired_capacity:
                    self.admitted_capacity = min(self.desired_capacity, self.admitted_capacity * 2)
                    print(">>> STABLE: RAMPING triggered. Increasing capacity.")
        else:
            print(">>> INITIALIZING: Baseline established.")
            
        self.last_metrics = current_metrics
        print(f"[GOVERNOR] State: {self.state} | Admitted Capacity: {self.admitted_capacity}/{self.desired_capacity}\n")
        return self.admitted_capacity

def run_canary_simulation():
    print("=== ADAPTIVE CAPACITY GOVERNOR CANARY ===")
    gov = CapacityGovernor(desired_capacity=64, start_capacity=4)
    
    # Baseline
    print("-- Step 1: Baseline --")
    gov.evaluate({"swap_mb": 1000.0, "load_1m": 1.0})
    
    # Stable scale up
    print("-- Step 2: Stable, Scaling up --")
    gov.evaluate({"swap_mb": 1010.0, "load_1m": 1.5})
    
    # Stable scale up
    print("-- Step 3: Stable, Scaling up --")
    gov.evaluate({"swap_mb": 1020.0, "load_1m": 2.0})
    
    # Minor stress -> HOLD
    print("-- Step 4: Stressed, HOLD --")
    gov.evaluate({"swap_mb": 1150.0, "load_1m": 5.5})
    
    # Major stress -> BACKOFF
    print("-- Step 5: Critical, BACKOFF --")
    gov.evaluate({"swap_mb": 2000.0, "load_1m": 12.0})

if __name__ == "__main__":
    run_canary_simulation()
