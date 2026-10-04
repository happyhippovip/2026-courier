import pathlib
p = pathlib.Path('tests/test_artifact_upload_flow.py')
t = p.read_text('utf-8')
old = '''def result_for(task, refs):
    return {**{f: task[f] for f in IDS}, "run_id": "r1", "result_id": "result-1", "status": "SUCCESS",
            "artifacts": refs}'''
new = '''def result_for(task, refs):
    import time
    from scripts.integration_contract import _canonical_hash
    base = {**{f: task[f] for f in IDS}, "run_id": "r1", "status": "SUCCESS", "artifacts": refs}
    return {**base, "result_id": f"result-{_canonical_hash(base)}", "execution_start_at": time.time(), "execution_end_at": time.time()}'''
if old in t:
    p.write_text(t.replace(old, new), 'utf-8')
    print('replaced')
else:
    print('not found')
