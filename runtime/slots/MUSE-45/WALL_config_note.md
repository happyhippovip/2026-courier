# WALL CONFIG NOTE — dead gates (static, read-only)

File: scripts/windows_muse_wall/config.json. No edits (wall scope owned by
overnight loop; read-only observation).

## C-1 (LOW-MEDIUM) minimum_free_memory_mb is never enforced
- Config sets 2500; all test fixtures copy it; supervisor.admitted_count()
  checks ONLY staged_levels/active_limit/desired_slots. No code path reads
  the memory key (repo-wide search: config + fixtures only).
- The one capacity number meant to protect the machine from 16-64 heavy
  slots is decorative. Staged admission can overcommit RAM with a green
  status. Owner (wall loop): either enforce (psutil.virtual_memory check in
  admitted_count/start_slot) or delete the key so nobody relies on it.

## C-2 (INFO) account_roles all null, never read
- ACCOUNT_A..F bindings are null; only referenced in config + one fixture.
  Future-use placeholder. No action; note so live-show "Account-Rotation:
  none" stays explicit.

## Corroborated GOOD
- provider_launch_enabled=false default-deny (start_slot refuses).
- real_jobs_enabled default-false via .get; run_job requires explicit command.
- staged_levels respected by admitted_count (invalid level raises).
