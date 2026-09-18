# HISTORICAL SNAPSHOT — canonical test routing is `ops/ai/TEST_MAP.yaml`

# Test Map (Verified 2026-09-18)

BEHAVIOR: Duplicate result & AMBIGUOUS_CRASH
TARGETED TEST: `tests/test_windows_runtime_torture.py`
BROADER TEST: Manual cluster observation
EXPECTED RESULT: Recovery unlinks marker; server transitions task to QUEUED/FAILED safely; no duplicate external effects.

BEHAVIOR: Stale worker SHA rejection
TARGETED TEST: N/A (Inspected natively in `server/app.py` `register_worker`)
EXPECTED RESULT: Server responds with `{"error": "wrong SHA rejected..."}` and `426 Upgrade Required`.
