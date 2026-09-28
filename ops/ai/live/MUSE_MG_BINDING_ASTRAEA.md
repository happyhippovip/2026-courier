# MUSE MG01–MG06 binding checkpoint (field-astraea, READ_ONLY, no runs/edits)

DATE=2026-09-28. HEAD=ae0030c8 (detached, writer still landing commits — HEAD
drift does NOT affect FINAL binding). Prior MAC01/02/03/05/06/11 checkpoints
cited DURABILITY_PENDING + HEAD bd539f18: those citations are now STALE;
this file records the delta. Their files untouched (foreign).

## MG01 exact reviewed-SHA binding — BOUND (target only, zero execution)
- FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf (rev-parse OK).
- origin/candidate-b-1 == SHA + origin/evidence/pre-codex-final-34b0a42 == SHA
  (fresh ls-remote last turn; canonical path per MAC_EXACT_BINDING Step 2).
- Base 4c1e24cc ancestor (REUSE_EVIDENCE=merge-base proof, codex handoff).
- Scope 4/5 source + docs deviation; 44/44 on exact bytes
  (REUSE_EVIDENCE=gate CHECKLIST_ADJUDICATED_BY line — NOT re-run, revalidation banned).

## MG02 process/port/PGID ownership + cleanup — PREP_HOLDS
- Fresh: `:8081` free (lsof exit 1). Zero signals sent, zero kills.
- Foreign :8080 map REUSE_EVIDENCE=MAC02 (PID 606 + verifier/mac-worker PIDs
  protected; not re-probed). Orphan-record + supervisor.lock rules stand.
- MISSING_EVIDENCE (unchanged): RUN-time staging PGID exists only at boot.

## MG03 fresh RUN_1 isolation — HOLDS
- `server/state/isolated_run1|2/{artifacts,logs,temp}` present, empty;
  run_ids match MAC03 values (75821131… / 9783F60C…). Zero writes by me.

## MG04 RUN_1 evidence capture — LAYOUT_READY
- All 9 contracts + EVIDENCE_LAYOUT + BINDING_TEMPLATE + verify_proof_contracts.py
  present in `scripts/run1_physical/`. Verifier NOT run (execution-time only).

## MG05 RUN_2 restart/no-replay procedure — PROCEDURE_STANDS with pointer
- MAC06 §1–§8 stand (quarantine, fresh-attempt retry, no-A-replay, B criteria).
- POINTER (not defect): MAC06 line refs verified against BASE 4c1e24cc
  (e.g. app.py:416-454, :185-215); FINAL_SHA is 6+ commits descendant —
  re-confirm line numbers at execution boot, no action now.

## MG06 Proof Card/Core Freeze input — TARGET_BOUND, execution UNKNOWN
- Target Candidate SHA: 34b0a42 (durable, two remote refs) — was UNKNOWN in MAC11.
- Execution Date + all 10 assertions + falsifiability hashes: UNKNOWN.
  Final Verdict: NOT_SET (no PASS invented). Template placeholders intact.

STATUS=MG01-MG06-BOUND-READY-FOR-EXECUTOR
NEXT_OWNER=Mac physical executor (boot RUN_1 on READY_FOR_PHYSICAL_RUN + operator auth)
DO_NOT_REPEAT=sha256-muse-mg-binding-34b0a42-01
