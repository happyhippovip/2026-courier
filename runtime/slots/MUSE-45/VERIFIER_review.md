# VERIFIER REVIEW — vacuous-PASS + artifact path semantics (static)

Files: scripts/courier_verifier.py, scripts/windows_worker/daemon.py:214-243,
scripts/acceptance/prepare_physical_run.py. Read-only.

## V-1 (MEDIUM, acceptance-integrity) Physical-proof verification is vacuous
- Verifier verdict defaults to PASS when a result carries no artifacts and no
  revenue_safety_audit capability (courier_verifier.py:81-88).
- All 10 acceptance tasks (pt-01..pt-10) declare no artifacts/capabilities.
- Therefore every acceptance verification PASSES without checking anything:
  not stdout content, not exit semantics beyond worker-reported status.
- The worker DOES enforce locally (missing declared artifact => FAILED,
  daemon.py:226) and reports stdout/stderr — but nothing on the verify path
  inspects result content for these tasks. Server /tasks/verify guards
  identity/replay/authority (alias 403, contradictory 409 — good) but not
  result correctness.
- Owner decision: (a) accept vacuous verify for echo-tasks (they are
  self-evidencing via status + stdout on record), or (b) add expected_stdout
  matching for acceptance tasks. Either way, NAME it in the proof protocol
  before the run so PASS means something auditable. (Echoes autonomy-rule
  "verifier hypothesis": who sets proof requirements — here, effectively
  nobody for content.)

## V-3 (LOW, latent) Artifact paths are relative + verifier-local
- Worker reports artifacts as RELATIVE paths hashed from worker cwd
  (daemon.py:217-224). Verifier checks the same relative path from VERIFIER
  cwd (verify_artifact). Cross-machine or cross-cwd => "missing" => FAIL.
- No bite today (acceptance has no artifacts; single-machine runs share
  nothing by default either — same-machine runs need identical cwd to pass
  artifact tasks). Owner: absolute-ize or ship bytes, if/when artifact tasks
  enter the proof.

## Corroborated GOOD
- Separate verifier key + verifier_id independence (server rejects
  verifier==worker, alias replays, contradictory replays).
- Revenue path: deterministic script, 60s timeout, FAIL on error/timeout.
- Poll backoff 5s->60s; per-task isolation (one bad task doesn't wedge loop).
- Worker exact-process ownership: CREATE_NEW_PROCESS_GROUP + finally
  taskkill /T on exact PID only (no broad kills).
