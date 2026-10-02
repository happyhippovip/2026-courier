# MUSE9 M4 — Replay Identity aktuell (Sidecar, READ_ONLY_C2)

Fokus: status/worker/attempt/dispatch/artifacts. Kein RUN, keine Revalidierung.

## Reuse zuerst
- `ops/ai/M1_M9/M4_RESULT_REPLAY_IDENTITY.md` (Pfade bereits klassifiziert).
- `server/app.py:352-416,469-520`; `daemon.py:339-354`; `central_state.json` (gelesen).

## Subcases
- M4-S1 Aktuelle Identitaeten (State gelesen): `test-win-002` RECONCILED
  (attempt:1/dispatch-5905…/WINDOWS-01/mit Artifact+sha); `task-replace-001`
  DISPATCHED (attempt:1/dispatch-862d…/NEW-WIN-PC-01/`artifacts: []`).
  VERDIKT: CONFIRMED.
- M4-S2 Exakt-Resend → ACK_DUPLICATE (200), Artifact-Vergleich
  reihenfolge-insensitiv (`app.py:362-367` per Re-Probe; Verify-Refs bei Beruehrung
  neu verifizieren). Follow-up: None-Guard (`arts or []`) neu — Verhalten: None≡[];
  Mechanik unveraendert.
  VERDIKT: CONFIRMED (Code).
- M4-S3 Konflikt → 409 laut: verarbeitet (`:368-369` per Re-Probe), nicht-erwartet
  (`:371-373`), Identitaets-Mismatch via 400 (Contract). Kein stiller Drop.
  VERDIKT: CONFIRMED (Code).
- M4-S4 Daemon-Redelivery terminiert: RESULT_READY bis DELIVERED; 4xx →
  REJECTED → RELEASE_PENDING → Quarantaene (`windows daemon.py:365-380`, Refute-Stand). Kein Wedge.
  VERDIKT: CONFIRMED (Code).
- M4-S5 Live-Replay beobachtet: keins (kein Server/Traffic in diesem Fenster).
  VERDIKT: MISSING_EVIDENCE (nur via RUN schliessbar — nicht hier).
- M4-S6 Grenze: Identitaet schuetzt RESULT, nicht EFFEKT (→ M6).
  VERDIKT: CONFIRMED (methodisch).

## OUTPUT
ROLE=M4
CONFIRMED=M4-S1 (aktuelle Identitaeten); M4-S2/M4-S3/M4-S4 (Mechanik); M4-S6 (Grenze)
DISPROVEN="Stille Doppel-Zaehung"; "Redelivery-Wedge"; "Resume-Replay alter Results" (frische IDs)
MISSING_EVIDENCE=Laufzeit-Beobachtung eines echten Resends/409 (nur RUN-Lane)
OWNER_PACKET=409-Sub-Reason-Codes (3 Formen unterscheidbar) — Mini-Spec liegt in M4-Paket M4.1
CRITICAL_PATH=M4-S5 → M9 RUN1_EVIDENCE (Resend-Fall als Witness); M4-S6 → M6
NEXT_OWNER=Server-Owner (Sub-Reasons); RUN-Lane (Live-Beobachtung)
DO_NOT_REPEAT=Replay-Sturm-Gedankenexperimente ohne Mechanik; ACK-Pfade neu beweisen
STATUS=DONE_STATIC

## FOLLOW_UP (2026-09-28, Selbst-Widerlegung)
ROLE=M4
SURVIVING_CONFIRMED=M4-S1 (stale-Fall unveraendert); M4-S2/S3 (Mechanik, Refs aktualisiert); M4-S4; M4-S6
REMOVED=Nichts (Ref-Auffrischung, kein Befund entfernt)
MINIMUM_NEXT_ACTION=Verify-Block-Refs bei naechster Beruehrung re-verifizieren
MINIMUM_TEST_OR_EVIDENCE=Laufzeit-Resend/409 (RUN-Lane, unveraendert)
NEXT_OWNER=Server-Owner (Sub-Reasons)
STATUS=DONE_STATIC
