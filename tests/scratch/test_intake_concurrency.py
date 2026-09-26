import textwrap

with open("tests/test_queue_processor.py", "r") as f:
    text = f.read()

new_test = textwrap.dedent("""
def test_dispatch_intake_concurrency_execution_ref_isolation(tmp_path):
    # Tests NT2: verifying execution_ref isolation when multiple intakes are queued concurrently.
    # The dispatcher avoids binding `gh run list --limit=1` and defers to worker exact binding.
    
    state_file = tmp_path / "central_state.json"
    
    intake1 = tmp_path / "i1.json"
    intake1.write_text('{"customer_reference": "cust_A", "target_owner": "a", "target_repo": "a", "target_sha": "a"}')
    
    intake2 = tmp_path / "i2.json"
    intake2.write_text('{"customer_reference": "cust_B", "target_owner": "b", "target_repo": "b", "target_sha": "b"}')
    
    with mock.patch("scripts.intake_dispatcher.os.path.exists", side_effect=lambda x: x == "central_state.json" and state_file.exists()):
        def mock_open_file(*args, **kwargs):
            if args[0] == "central_state.json":
                return open(state_file, args[1])
            return open(*args, **kwargs)
        with mock.patch("builtins.open", side_effect=mock_open_file):
            with mock.patch("scripts.intake_dispatcher.subprocess.run"):
                from scripts.intake_dispatcher import dispatch_intake
                dispatch_intake(str(intake1))
                dispatch_intake(str(intake2))
                
    import json
    state = json.loads(state_file.read_text())
    
    tasks = state.get("tasks", {})
    assert "task-revenue-cust_A" in tasks
    assert "task-revenue-cust_B" in tasks
    
    # Verify execution_ref deferred isolation
    assert tasks["task-revenue-cust_A"]["execution_ref"] == "DISPATCHED_PENDING_EXACT_BINDING"
    assert tasks["task-revenue-cust_B"]["execution_ref"] == "DISPATCHED_PENDING_EXACT_BINDING"
""")

with open("tests/test_queue_processor.py", "a") as f:
    f.write(new_test)
