# MMAC-215 — Lane 4 Hub audit (read-only + /tmp probe)
Base f425d328 unchanged. #256 FULLY GREEN (both runs, windows pytest 9m28s on newer run), MERGEABLE/CLEAN, base integration/v1 -> MERGE_READY for L1. #255 draft (lane owner). New Cursor PRs #260/#261 untouched.

Journey audit of #226 + #255 heads: relay, frontend result mapping, install-status honesty, unrecognised-state handling all SOUND (details in result JSON).

FINDING-226-PROJECTBASE-PARTIAL (LOW-MEDIUM, owner: #226 author): `Hub.project_base_view` swallows mid-iteration `journal.events()` errors (`except Exception: pass`) and returns a complete-looking Project Base with no `truth` field. Reproduced in /tmp/hubprobe/probe_partial.py: DatabaseError after 2 events -> away events_count=2 (partial), next_safe_action IDLE_READY, zero degradation signal. No existing test covers it (0/7). Suggested owner fix: propagate as TruthUnavailable('unreadable') into the existing TRUTH_UNAVAILABLE branch.

NEXT_SAFE_ACTION: Lane 4 continue journey (submit-task path under failure injection) or next distinct free workkey at safe load.
