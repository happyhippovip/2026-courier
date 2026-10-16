# MMAC-216 — Lane 4 submit-task wiring audit (read-only)
Base f425d328 unchanged. #226 CI fully green both runs; #256 still OPEN (L1 merge, not my scope).

hub.js (147 lines, full read) + hub_core decision client: no false-success path found.
Pending/refresh/offline/dedup all sound; frontend tests pin the key behaviors.

No new proven defect. Three owner questions filed in result JSON (stop-message
safe-point grounding, stop-without-confirm, CLI exit-0-on-unknown). Test gap
consistent with FINDING-226-PROJECTBASE-PARTIAL (still with #226 owner).

NEXT_SAFE_ACTION: Lane 4 journey largely covered (open/status/decide/stop/blocked/restart);
remaining: controller /cancel safe-point contract (needs controller-side read) or next free workkey.
