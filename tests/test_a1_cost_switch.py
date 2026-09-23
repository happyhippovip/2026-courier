import os
import json
import uuid
import pytest
from pathlib import Path
from scripts.cannon_motor import CannonMotor
from app.cannon.adapters import LiveMuseAdapter

def test_paid_api_disabled_by_default(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    
    task = {
        "task_id": "test-paid",
        "provider": "meta",
        "acceptance": "isolated_nonce_canary_v1",
        "executor_kind": "REAL_MUSE"
    }
    
    # 1. Default should fail
    if 'COURIER_ALLOW_PAID_API' in os.environ:
        del os.environ['COURIER_ALLOW_PAID_API']
        
    with pytest.raises(ValueError, match="PAID_CALLS_DISABLED"):
        LiveMuseAdapter.execute_canary(task, results_dir, lambda x: None)

    # 2. Enabling it should bypass the safety check
    os.environ['COURIER_ALLOW_PAID_API'] = '1'
    try:
        # We don't want it to actually run muse and wait 90 seconds,
        # but if we pass the first check, we can just supply a bad provider to prove it got past.
        bad_task = dict(task, provider="invalid")
        with pytest.raises(ValueError, match="UNSUPPORTED_REAL_PROVIDER"):
            LiveMuseAdapter.execute_canary(bad_task, results_dir, lambda x: None)
    finally:
        del os.environ['COURIER_ALLOW_PAID_API']

