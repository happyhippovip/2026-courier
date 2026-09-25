import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.worker_contract import WorkerContract

def test_worker_contract_init():
    w = WorkerContract("worker-1", ["read", "write"], "FREE", "linux")
    assert w.worker_id == "worker-1"
    assert w.capability_set == ["read", "write"]
    assert w.cost_class == "FREE"
    assert w.runtime_type == "linux"

def test_worker_contract_methods(capsys):
    w = WorkerContract("worker-2", [], "CHEAP", "mac")
    w.register()
    captured = capsys.readouterr()
    assert "worker-2 registering" in captured.out
    
    w.claim("task-99")
    captured = capsys.readouterr()
    assert "worker-2 claiming task task-99" in captured.out
    
    w.execute("exec-ref-1")
    captured = capsys.readouterr()
    assert "Executing exec-ref-1" in captured.out
    
    w.result()
    captured = capsys.readouterr()
    assert "structured outcome" in captured.out
    
    w.cleanup()
    captured = capsys.readouterr()
    assert "Cleaning exact task processes" in captured.out

