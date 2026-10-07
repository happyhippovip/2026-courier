# MUSE-45 T-M — muse_supervisor.py static review (read-only)

Branch fix-cb1-new @ 329abd80. Full file read (518 lines) + runtime_state
identity primitives. Shell DOWN; static only. No edits. First MUSE-45 review
of this file (new-tree core).

## Verified strengths (OBSERVED with pins)

- S1 single-supervisor: flock NB (:307-315); second start/supervise/canary
  refused (:318-322, :336-339, :435-438).
- S2 crash-safe spawn: STARTING persisted BEFORE spawn (:294-295); re-entry
  yields PAUSED_ERROR/UNCERTAIN_SPAWN (:273-274) which resume explicitly
  refuses to clear (:405-407). No blind respawn after crash.
- S3 identity-verified lifecycle: process_identity at spawn (:173) = ps tuple
  pid/pgid/lstart/comm (no cmdline/secrets persisted); owned() gates
  terminate (:203-214); PID-reuse mismatch -> PAUSED_ERROR (:276-278);
  cleanup_group revalidates before signaling (runtime_state.py:90-96).
- S4 adopt-don't-duplicate (:287-290), one start per tick (:291, :302),
  governor-gated starts (:291).
- S5 governor fail-closed: 0 capacity without metrics (:119, :138), 120s ramp
  hold (:134), pressure backoff ladder (:124-131).
- S6 STOP authoritative: blocks start (:342-344) and canary (:445-447);
  cleared only by explicit resume-all (:391-396); failed terminate leaves
  CLEANUP_NOT_PROVEN, also resume-refused (:380-381, :405).
- S7 canary discipline: bounded single exec, RESULT_READY never recomputed
  (:453-455), admission re-check (:459-461), env save/restore (:440-442,
  :488-494), no-modification instruction.
- S8 clean shutdown: SIGTERM->KeyboardInterrupt->stop --terminate (:360-361,
  :514-518).

## Findings (all LOW/INFO — no MEDIUM+)

- M1 LOW: shell-string spawn (:168-171, bash -c f-string with quoted paths).
  Quote-injection requires `"` in WALL_DIR/sys.executable/DAEMON (operator-env
  controlled). Direct-argv spawn would remove the class. Note only.
- M2 INFO: is_alive PID-only fallback (:185-195 os.kill 0) reachable only when
  launcher lacks owned() (test doubles); production path prefers owned()
  (:263-265); :276 use (dead-vs-foreign distinguisher) is correct. No defect.
- M3 LOW: main() int(argv[1]) (:501) unguarded — `start abc` traceback-exits
  instead of clean usage error. Cosmetic CLI robustness.
- M4 INFO: missing/unparsable exit_code reads as None (:197-201) and None != 0
  counts toward fast-crash backoff (:245). Fail-closed direction; bash wrapper
  always writes the file in practice. No defect.
- M5 INFO (cross-branch): fcntl/bash/sysctl/memory_pressure = POSIX-only by
  design (mac_worker). Cannot supervise a Windows checkout; the convergent
  Windows supervisor lives on the other branch line. Architecture note only.

## Verdict

Disciplined implementation matching its docstring contract. Nothing above LOW.
No fix proposed (foreign scope + no runner); M1/M3 are optional hardening nits
for the Mac supervisor owner.
