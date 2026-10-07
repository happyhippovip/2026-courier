# MUSE-45 T-D — Test-gap static re-verify (read-only)

MISSION=COURIER_LIVE_SHOW_CONTINUE, slot MUSE-45, date 2026-09-26.
Method: static tree evidence only (shell DOWN, no test runs). No file modified
except this packet.

## Existence sweep: 17/17 present

All DLQ-queue/NEXT_WORK-referenced test files exist in tests/:
test_ledger_attestation_trust_root, test_ledger_self_cert_rejection,
test_ledger_freshness_binding_epoch, test_ledger_freshness_rejection,
test_provider_wait_isolation, test_ledger_windows_permission_retry,
test_attestation_cross_defect_crash, test_ledger_false_green_attack,
test_windows_runtime_torture, test_motor_crash_swallow,
test_server_infinite_retry, test_ledger_status_overwrite,
test_windows_daemon_completeness, test_muse_wall_jobs,
test_muse_wall_staged_scaling, test_courier_continue, test_queue_independent.

## G1 — GAP: no regression test for the DLQ-08 8s hang-abandon

Zero references in tests/ to `TIMEOUT_HUNG_TASK` or `abandon`. The
courier_continue.py:528-539 hang-abandon path (verified present in T-C) has no
dedicated regression test observable statically. Both "hung" candidates ruled
out by scope (T-K cross-check): test_attestation_cross_defect_crash imports only
ledger+fixtures (attestation scenarios, no motor drain); test_queue_independent's
"hung" is a daemon-run timeout assertion message. G1 CONFIRMED gap. Owner gap:
add a hung-edge abandon test (needs shell; not writable by me under current
writer rules + no runner).

## G2 — CROSS-FINDING: resolves the T-A provider-flag mismatch

The shipped config tests PIN the safe default and read the real shipped file:
- tests/test_muse_wall_staged_scaling.py:131-135 TestConfigSafety::
  test_shipped_config_has_provider_disabled asserts shipped
  scripts/windows_muse_wall/config.json has provider_launch_enabled is False.
- tests/test_muse_wall_gaps.py:242-247 asserts the same + staged_levels +
  desired_slots==64 + active_limit in [0]+staged.
- active_limit=16 is valid under both (0 or staged level).

Consequence: Google's checkpoint claim "provider_launch_enabled false->true",
applied to the SHIPPED file, would break at least these two tests. The tree
value `false` is the test-compatible state. Resolution: the shipped flag stays
false; any intent to ship provider launch enabled requires a tested config
change first (owner decision). T-A mismatch verdict updated accordingly
(see pointer in the T-A packet). Static reading only; no test run possible here.

## WIN-01 collision peek (read-only)

runtime/slots/WIN-01/state.json: WORKING, mission WINDOWS_MUSE_15_CONTINUOUS,
process null. No scope overlap with my verify/packet lane. Untouched.
