import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import task_routing

def test_route_task_local():
    req = {"can_run_local": True}
    assert task_routing.route_task(req) == "LOCAL_WINDOWS"

def test_route_task_hosted():
    req = {"can_run_local": False, "needs_hosted": True}
    assert task_routing.route_task(req) == "GITHUB_HOSTED"

def test_route_task_expensive_ai():
    req = {"can_run_local": False, "needs_hosted": False, "complexity": "high"}
    assert task_routing.route_task(req) == "EXPENSIVE_AI_PROVIDER"

def test_route_task_cheap_ai():
    req = {"can_run_local": False, "needs_hosted": False, "complexity": "low"}
    assert task_routing.route_task(req) == "CHEAP_AI_PROVIDER"
    
def test_route_task_default():
    # If nothing is passed, can_run_local defaults to True according to the implementation dict.get('can_run_local', True)
    assert task_routing.route_task({}) == "LOCAL_WINDOWS"

