import pytest
import json
import os
from scripts.courier_motor_precheck import has_dispatchable_work, DISPATCHER_ID

def test_has_dispatchable_work_worker_busy():
    state = {
        "workers": {
            DISPATCHER_ID: {
                "current_task": "some_task"
            }
        },
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "QUEUED", "target_agent": "github"}]
            }
        }
    }
    assert not has_dispatchable_work(state)

def test_has_dispatchable_work_no_work():
    state = {
        "workers": {
            DISPATCHER_ID: {}
        },
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "COMPLETED", "target_agent": "github"}]
            },
            "g2": {
                "status": "BLOCKED",
                "workflow_plan": [{"status": "QUEUED", "target_agent": "github"}]
            }
        }
    }
    assert not has_dispatchable_work(state)

def test_has_dispatchable_work_has_work():
    state = {
        "workers": {},
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "QUEUED", "target_agent": "github"}]
            }
        }
    }
    assert has_dispatchable_work(state)
    
def test_has_dispatchable_work_different_agent():
    state = {
        "workers": {},
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "QUEUED", "target_agent": "windows"}]
            }
        }
    }
    assert not has_dispatchable_work(state)

def test_has_dispatchable_work_current_step_index():
    state = {
        "workers": {},
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "current_step_index": 1,
                "workflow_plan": [
                    {"status": "COMPLETED", "target_agent": "github"},
                    {"status": "QUEUED", "target_agent": "github"}
                ]
            }
        }
    }
    assert has_dispatchable_work(state)

