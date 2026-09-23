import time
import pytest
from scripts.work_queue import load
from scripts.cannon_motor import CannonMotor
from scripts.mac_adapter import MacAdapter
from pathlib import Path

def test_heartbeat_updates_claim_time(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake")
    motor = adapter.motor
    
    motor._wq("claim", "--worker", "test_worker")
    
    class Args:
        pass
    
    args = Args()
    args.state_dir = str(tmp_path)
    data1 = load(args)
    t1 = data1["leases"]["t1"]["claimed_at"]
    
    time.sleep(0.01)
    # Send heartbeat
    motor._wq("heartbeat", "t1", "--worker", "test_worker")
    
    data2 = load(args)
    t2 = data2["leases"]["t1"]["claimed_at"]
    
    assert t2 > t1
