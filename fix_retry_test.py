import pathlib
p = pathlib.Path('tests/test_server_integration_contract.py')
t = p.read_text('utf-8')

old = '''        identity = dict(failed)
        identity.pop("result_id", None)
        failed["result_id"] = f"result-{_canonical_hash(identity)}"'''

new = '''        identity = {
            "goal_id": failed["goal_id"],
            "task_id": failed["task_id"],
            "attempt_id": failed["attempt_id"],
            "dispatch_id": failed["dispatch_id"],
            "worker_id": failed["worker_id"],
            "run_id": failed["run_id"],
            "status": failed["status"],
            "artifacts": failed["artifacts"],
        }
        failed["result_id"] = f"result-{_canonical_hash(identity)}"'''

if old in t:
    p.write_text(t.replace(old, new), 'utf-8')
    print('replaced')
else:
    print('not found')
