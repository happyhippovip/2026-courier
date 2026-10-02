# VACATED — WIN-01 was already LIVE (do not use this file)

On 2026-09-26 session 01a0dcbf wrongly claimed WIN-01: the repo-wide
"WIN-0x" content search had hit max_elapsed and returned 0 matches on a
PARTIAL traversal. Exact glob later proved runtime/slots/WIN-01/ (WORKING,
CLAIM + W1 + W2) and WIN-02 (WORKING) already existed.

REAL OWNER: runtime/slots/WIN-01/ (mission WINDOWS_MUSE_15_CONTINUOUS).
This session vacated immediately, touched nothing there, and re-claimed
WIN-03 (free: no WIN-03..15 state.json on disk). Lesson: enumerate slots
with exact state.json globs, never with bounded content search.

This stub stays so the filename can never be mistaken for a live claim.
