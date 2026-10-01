# MUSE-45 T-T — Mac remainder: wrapper, handler parity, convergence pins (read-only)

Branch fix-cb1-new @ 329abd80. Static only. No edits but this packet.

## O7 LOW: limit_wrapper.sh is niceness, not containment

scripts/mac_worker/limit_wrapper.sh (23 lines): backgrounds the command,
renice 10 + taskpolicy -b, waits. No CPU/mem/time limits, no sandbox-exec,
no filesystem containment — despite the name and despite run_agy launching
with --dangerously-skip-permissions behind it. The daemon's own timeout
(300s agy / 3600s muse) is the only bound. Rename-or-harden note for owner.

## O8 LOW: NATIVE allowlist advertises 6 actions, implements 2

daemon.py:256 allowlists create_file, read_file_metadata, git_status,
run_known_test, hash_file, echo — but only echo (:274-275) and git_status
(:276-277) have handlers; the other 4 return "allowed but handler is not
implemented yet" FAILED (:279). run_known_test/hash_file sound load-bearing
for a test/artifact worker. Parity gap (docs-or-code) for owner. (Unrelated
to O4's echo sink, which stays the MEDIUM.)

## Convergence suite: safety properties PINNED (27 tests)

tests/test_muse_convergence.py names lettered properties covering my verified
strengths: missing/unsafe metrics no-spawn, STOP authority (spawn + canary),
duplicate-start prevention, no-blind-restart after spawn crash, PID-reuse
never authorizes kill, orphan blocks claim, TERM-then-KILL owned-group only,
canary exactly-once + ambiguous-never-replayed, legacy-unbound-noexec,
result/checkpoint persistence failure semantics, corrupt-state fail-closed,
plus a live test_real_owned_process_group_cleanup. This is the test backbone
behind T-M/T-O/T-P verdicts. Deliberately NOT covered (my unpinned LOWs
stand): spawn-string quoting (M1), CLI-arg robustness (M3), echo sink (O4),
agy perms/caps (O5/O6), win-side Q9/Q1.

## Absence note (INFO)

scripts/mac_worker/health_check.py does NOT exist on this branch (my T-F
portability note listed it from the OLD tree). No correction needed to T-L2
(14-file list stands); recorded so old/new sets aren't conflated.

## Verdict

Mac worker-path audit now COMPLETE end-to-end (supervisor/adapter/daemon/
runtime/tests/prompt/wrapper). New items O7/O8 are LOW. No MEDIUM+ beyond O4.
