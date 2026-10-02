# L14 DUPLICATE RESULT REPLAY

The system already fully protects against duplicate/conflicting result replays in `courier_core/controller.py` by checking `existing.content() == candidate.content()`.

If a result is replayed identically, it returns `200 ACK_DUPLICATE`.
If a result is replayed with the same `result_id` but conflicting content, it returns `409 result_conflict`.
If a result is replayed with a different `result_id`, it records `LATE_RESULT_DISCARDED` and returns `409 stale_dispatch`.

This strictly adheres to the canonical completion semantics established in the Codex bridge. No implementation fixes are required. I have provided a rigorous test suite `tests/test_l14_duplicate_result_replay.py` to pin this behavior permanently.
