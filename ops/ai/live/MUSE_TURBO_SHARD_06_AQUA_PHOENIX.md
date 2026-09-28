# MUSE TURBO ENDGAME SHARD 06 — TIMEOUT -> FAILED (post-Codex packet, read-only)

OWNER=MUSE aqua-phoenix / HOST=MAC / 2026-09-28
MODE=READ_ONLY_C2, LEDGER=FROZEN, 0 source edits, 0 runs, 0 test-runs,
kein git show, kein PRE_CODEX-Re-Validate, keine 65-96-Schleife,
kein Cascade-/Gate-Re-Proof, kein Canary, keine Full Suite.
MASTER_PROMPT: ops/ai/MUSE_TURBO_ENDGAME_SHARD_MASTER_PROMPT.txt ENOENT →
Inline-Shards verwendet. CODEX_HIGH_RESULT_CURRENT.md absent → CODEX NOCH
NICHT DA → nur Post-Codex-Paket (keine Execution).
CLAIM: Shard 06 (TIMEOUT->FAILED), TURBO-Namespace unbelegt (keine
TURBO-Shard-Files in live/wall_claims/wall_results; AUTONOMY_xx und
marathon-16 sind fremde Namespaces, SHARD-10 done). 4 Subcases (max 6).

## Subcases (Source-Truth Worktree, bounded reads)

- S1 CONTRACT-GATE: scripts/integration_contract.py:25
  RESULT_STATES={"SUCCESS","FAILED"}; :148 validate_durable_result rejectet
  explizites TIMEOUT mit "invalid result status" (400). workers DUERFEN kein
  TIMEOUT senden — Daemon-seitiges FAILED-Mapping ist Pflicht, kein Contract-
  Fallback. (G06-Kompatibilitaet zitiert, nicht neu erklaert.)
- S2 WIN-KILL-REAP OK: scripts/windows_worker/daemon.py:200-251 —
  communicate(timeout=600); TimeoutExpired → taskkill /F /T (:241-244) +
  process.kill() + process.communicate() (:246-249, Reap) + status FAILED
  (:250-251). Generischer except-Zweig spiegelt dasselbe (:252-261).
  Kill+Reap+FAILED vorhanden, fail-closed.
- S3 MAC-RUN_AGY-LEAK (neu, zeilengebunden): scripts/mac_worker/daemon.py:291
  run_agy — Popen + communicate(timeout=300) (:303-304); TimeoutExpired faellt
  in generisches `except Exception as e` (:322) → FAILED, ABER KEIN kill/reap:
  das `agy -p ... --dangerously-skip-permissions`-Child laeuft nach Timeout
  verwaist weiter. G06 fixte gemini-Adapter/Win-Daemon/github-Adapter (fremde
  Lane, zitiert); run_agy ist dort nicht abgedeckt. Residual-Leak, kein Fix
  von hier (read-only).
- S4 SCOPE-LUECKE: FINAL_SHA-Delta = 4 Source-Files (courier_verifier,
  integration_contract, app.py, test_artifact_upload_flow; CODEX_HANDOFF-
  Doc :14-17, zitiert). Daemon-Files NICHT im Delta → S2/S3-Status ist
  Worktree-Truth, muss post-Codex auf exakten SHA-Bytes bestaetigt werden
  (keine Re-Validation durch mich; Codex/Owner-Scope).

## OUTPUT

SHARD=06 TIMEOUT->FAILED
FILES=scripts/integration_contract.py:25,148; scripts/windows_worker/daemon.py:200-261; scripts/mac_worker/daemon.py:291-323
CAUSAL_RISK=mac run_agy verwaist Timeout-Child (kein kill/reap) → CPU/Prozess-Leck ueber 300s-Fenster hinaus; Server-Dedup faengt spaete Results, aber Host-Last bleibt. Win-Seite sauber (kill+reap+FAILED). Contract laesst kein TIMEOUT durch (400).
MIN_FIX=mac run_agy TimeoutExpired-Zweig mit kill()+communicate() nach Win-Vorbild (:241-249) ergaenzen (2-4 Zeilen, Writer-Lane, kein Architektur-Change).
MIN_TEST=1 Unit-Test (Fake-Popen mit TimeoutExpired → assert killed+reaped + status FAILED) + Nachbar mac-Worker-Tests gruen.
EVIDENCE=S1-S4 oben (Worktree-Reads 2026-09-28); G06-Fingerprints fremd (DUPLICATE_SKIP, nicht re-analysiert).
OWNER=CENTRAL_WRITER (S3-Fix) + CODEX_HIGH (S4-Byte-Bestaetigung post-Review).
BEFORE_RUN1=YES (RUN_1 nutzt mac/agy-Pfad; Leak vor physischem RUN schliessen oder als bekanntes Restrisiko ins RUN_1-Paket schreiben).
DO_NOT_REPEAT=sha256-muse-turbo-shard06-aqua-01; G06-Fingerprints (fremd); sha256-muse-direct-65-96-aqua-02.
STATUS=SHARD_DONE_POST_CODEX_PACKET (kein zweiter Shard).
