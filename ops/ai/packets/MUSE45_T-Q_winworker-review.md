# MUSE-45 T-Q — windows_worker review on fix-cb1-new (read-only)

Branch fix-cb1-new @ 329abd80. daemon.py read whole (389 lines) + install/
start/stop/status/bootstrap chain. Shell DOWN; static only. No edits.
First MUSE-45 review of this branch's worker (shape differs from old tree).

## Verified strengths (OBSERVED)

- Phase machine mirrors mac: STARTED never replayed (:304-308), REJECTED->
  RELEASE_PENDING persisted-before-release (:356-364), redelivery reuses stored
  payload (:353), corrupt/unknown phases forced STARTED (:298-299).
- Delivery split 4xx-final vs transport/5xx-retryable (:113-135, 5 attempts exp
  backoff); artifact hash chain + dual-OS path safety (:151-160, stronger than
  mac's POSIX-only check); per-artifact persist (:110).
- 600s task timeout + taskkill /F /T tree cleanup (:217-227); single-instance
  msvcrt lock + PID file (:263-275); credential fail-closed
  (MissingCredentialError -> FATAL exit 2, :32-35, :384-389).
- Installer UPGRADED vs old tree: AtStartup + SYSTEM + Highest (:11-13) = true
  boot persistence. T8's F-T8-2 (AtLogon-not-boot) does NOT apply to this
  worker installer. No motor/verifier/server installers exist here
  (worker-only service layer).

## Findings

- Q9 LOW-MEDIUM: bootstrap health handshake BROKEN on this branch (two ways).
  bootstrap.ps1:105 waits for "Registered successfully", which this daemon.py
  NEVER prints (only "HTTP Daemon started" :289 and "FATAL" :388). AND the
  daemon has NO file logging (print only) while start.bat has NO redirect, so
  under the service path nothing lands in logs/worker.log at all (bootstrap
  cleared it at :96, then tails a dead file). Net: bootstrap always 30s-times-
  out into WARNING even on healthy start. Old-tree T8 F-T8-5 "handshake SOUND"
  does not transfer. Owner: worker bootstrap/daemon logging.
- Q1 LOW-MEDIUM: API key at rest in PLAINTEXT config.json (bootstrap :60-65;
  "stored securely" message is misleading — SecureString covers console input
  only, then plaintext to disk, no ACL). Regression vs old-tree keychain model.
- Q2 LOW: DEFAULT_SERVER hardcoded LAN IP http://192.168.178.162:8080 (:10).
  Single-LAN default + internal addressing in tree (T9-family).
- Q4 LOW: lockfile finally-remove (:380-382) races the still-open lock handle
  (fd never closed :272-273) -> likely PermissionError at shutdown on Windows.
  Exit-path-only, masks real errors.
- Q5 LOW: run_task output unbounded (communicate, no cap :217) vs mac 8MB cap.
- O2 extends here: corrupt current_task.json crashes at startup (:296-297
  unguarded json.loads). Same containment story as mac (supervisor/exit).
- Q8 INFO: status.bat lists ALL pythons (tasklist|findstr) — noisy,
  foreign-inclusive; read-only, safe.
- Q3/Q6/Q7 INFO (no defect): Windows run_task = arbitrary PowerShell BY DESIGN
  (:211-213 -EncodedCommand, no allowlist) — asymmetric to mac NATIVE's
  allowlist, but explicit model (no O4-style bypass; trust boundary = task
  authors). Resource governor fail-OPEN on check failure (:258-260) vs mac
  fail-CLOSED (commented tradeoff). F3-successor stop.bat unchanged here.

## Verdict

Worker core solid; bootstrap/daemon logging handshake is the real gap (Q9),
key-at-rest second (Q1). Rest LOW/INFO. No action by me (foreign scope).
