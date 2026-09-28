# TURBO SHARD 12 — RUN_1 failure-stickiness (Post-Codex-Paket, READ_ONLY)

SHARD=12 (RUN_1 failure-stickiness) · SESSION=cloud-octans · 2026-09-28
MODE=prep-only (kein Codex-Resultat → Paket vorbereitet, nichts ausgeführt)
REFS=worktree server/app.py (HEAD bd539f18), read-only. 0 edits, 0 runs.

## Subcases (5, source-grounded)
1. Intake non-SUCCESS: attempts<3 → QUEUED + worker=None (:411-413, auto-retry
max 2 Wiederholungen); else FAILED_TERMINAL + goal BLOCKED (:415-416, :426-427).
Auto-Anteil endet nach 3 Versuchen — danach klebt der Failure.
2. FAILED_VERIFICATION: kein Auto-Pfad zurück; einziger Exit resume-retry
(:557 erlaubt FAILED_VERIFICATION) mit frischer attempt/dispatch. Verify-Fail
klebt bis explizitem Retry.
3. FAILED_TERMINAL ist per :557 resumable — Label vs. Semantik: "TERMINAL"
bedeutet hier "kein Auto-Fortschritt", nicht "unwiederbringlich". Evidence-
Präzisionsnotiz (kein Defekt): Cards dürfen TERMINAL nicht als end-versus-
menschlich lesen; Resume bleibt möglich, aber nie automatisch.
4. force_success→400 + unknown-action→400 (bekannt, zitiert): kein manueller
Override klebt umgehbar — Stickiness gegen Operator-Abkürzung intakt.
5. Post-verify-FAIL: Task FAILED_VERIFICATION + goal BLOCKED; erneutes verify
rejected (nicht RESULT_RECEIVED → 409, :495). Verify-Fehlschlag klebt doppelt
(Task + Goal), löst sich nur via resume-retry.

FILES=server/app.py (:391, :407-427, :495, :557-558)
CAUSAL_RISK=Kein Defekt gefunden: alle Failure-Pfade kleben (auto nur ≤2 Retries,
danach expliziter Retry mit frischer Identität; kein Auto-Resume, kein Override).
Restrisiko: implizite Annahme, dass ein Operator resume je aufruft — Stall ohne
Timeout; Reclaim greift nur bei stale-Worker, nicht bei BLOCKED-Goals (by design:
HUMAN_REQUIRED braucht Mensch). Für Autonomy-Marathon: BLOCKED-Goals ohne
menschlichen Resume bleiben stehen — dokumentierte Grenze, kein Bug.
MIN_FIX=— (keiner nötig)
MIN_TEST=Bestand (resent-failed-after-requeue, force-success-400, conflicting-409)
EVIDENCE=Dieses Paket + cited Zeilen; physischer Nachweis erst post-Codex an
Real-Instance (FAILED-Run → Stickiness → expliziter Retry → frische Identity).
OWNER=RUN_1-Witness-Lane (post-Codex); Stall-Timeout-Policy ggf. Operator-Entscheid
BEFORE_RUN1=NEIN (Paket selbst) | Nachweis fällig IN RUN_1 (Failure-Case einplanen)
DO_NOT_REPEAT=turbo-12-failure-stickiness-packet
STATUS=COMPLETE (Paket; Ausführung erst bei Codex-GREEN + RUN_1)
