# T11 RESULT — Stale-assumptions sweep, code level (static, read-only)

DELTA NOTE (dedupe): pre-existing T11_stale_assumptions.md (coordination-SHA
bindings, TEST_MAP phantom test, DLQ line-pin drift, checkpoint contradiction,
RC UNKNOWN evidence) is CANONICAL for docs-vs-code. This file covers code-level
staleness (phantom modules, dead entry point, version drift, test pinning);
overlap ~none, complementary.

MODE: shell-less LIGHT. Shared-memory staleness already in TESTGAP §4 (S-1..S-6);
this sweep covers code/docs/dashboard/test assumptions. OBSERVED unless marked.

S11-1 (MEDIUM) DASHBOARD GREEN FOR PHANTOM COMPONENTS.
dashboard/server.py:100,102 hardcodes "snitch_operational_truth" and
"live_worker_registry" as "VERIFIED_REAL". scripts/snitch_observer.py and
scripts/live_worker_registry.py DO NOT EXIST (82-file inventory + repo search).
README:54,104 + docs/INTERNAL_ARCHITECTURE:54,104 + PKG-INFO:71,121 cite both
files plus tests/test_snitch_observer.py — also absent (actual file is
tests/test_snitch_watchdog.py). Owner must downgrade or implement.

S11-2 (HIGH) DEAD ENTRY POINT, UNGUARDED PHANTOM IMPORT.
scripts/start_opportunity_daemon.py:6-8 imports scripts.opportunity_os.* at top
level with no guard; no scripts/opportunity_os.py nor scripts/opportunity_os/
exists (inventory + glob empty). Any import/run raises ModuleNotFoundError
(INFERRED from Python semantics; absence OBSERVED; not executed — no shell).

S11-3 (MEDIUM, reconfirms LONGRUN-T7) VERSION/SCHEMA DRIFT STILL OPEN.
docs/RELEASE_CANDIDATE: VERSION=1.0.0-rc.1 + SCHEMA_VERSION=v4, but
pyproject.toml:7 = 0.1.0 and live code uses state schema 2 (server/app.py:453-471,
migration 1->2, fail-closed >2), ledger SCHEMA_VERSION=2
(agent_handoff_ledger.py:25, accepts 1..2), memory/chief "2.0" strings. No v4
anywhere in searched code paths. Owner decision required, not made here.

S11-4 (LOW) DEAD OPTIONAL IMPORT. inbound_response_observer.py:19 imports
scripts.money_machine_pipeline (try/except pass); module absent AND the names
MoneyMachinePipeline/OpportunityState unused repo-wide (only that file matches).
Harmless; owner cleanup.

S11-5 (INFO) PHANTOM MODULES GRACEFULLY STUBBED — SAFE. resource_intelligence:
fallback stub class (run_snitch_watchdog.py:33), None-guards
(run_chief_commander.py:61,228; run_visual_studio_server.py:56-58,488-490).
snitch_observer: None-guard + conditional use
(run_visual_studio_server.py:719-729). Dead-defensive, no defect.

S11-6 (LOW) NO DEBT MARKERS IN LIVE CODE. Zero TODO/FIXME/XXX in scripts/ +
server/ (searched). Debt is either zero or entirely untracked.

S11-7 (MEDIUM) THOUGHT TESTS MAC-PINNED, WINDOWS-UNRUNNABLE.
test_thought_ingestion.py:17 + test_thought_memory_mesh.py:16 hardcode
/Users/user/Downloads/2026-project-memory and shell out to git
(subprocess rev-parse). Any non-Mac-user checkout fails. Extends T9.

S11-8 (LOW) BOUNDARY RUNNER FRAGILE. tests/boundaries/run_boundaries.py:
create_finding writes tests/boundaries/findings/ with no makedirs (dir
empty-or-missing — ambiguous without shell; crash risk on first finding);
POSIX-only venv/bin/python3 fallback (line 43); hardcoded key. Mitigating:
all 4 asserted routes exist in server/app.py (/goals, /tasks/claim,
/workers/register, /tasks/result) — no API drift on those. Manual runner only.

S11-9 (LOW) DISABLED + ZERO-TEST FILES. test_DLQ02_freshness_bound.py.bak
disabled (reason UNKNOWN); soak_test.py pytest-collectable with 0 test
functions; "python3" literal + relative courierctl path (Windows-fragile).

## Disposition
Read-only: NO FIXES APPLIED. S11-1/S11-2/S11-3 need writer-owner decisions.
No files outside runtime/slots/MUSE-45 touched.
