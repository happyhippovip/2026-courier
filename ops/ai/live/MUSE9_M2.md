# MUSE9 M2 — SKIPPED-Test vs Handoff-Gueltigkeit (Sidecar, READ_ONLY_C2)

Lokale Evidence: 1 skipped (in 28/1/1). Kein RUN, keine Revalidierung.

## Reuse zuerst
- `ops/ai/M1_M9/M2_SKIPPED_TEST_VALIDITY.md` (Orphan-Fund M2-ORPHAN-1).
- `tests/test_artifact_upload_flow.py:462-466` (einziger Skip, dediziert gesucht).

## Subcases
- M2-S1 Skip-Ehrlichkeit: einziger Skip im Baum, Plattform-Gate (win32 →
  "Mac daemon requires fcntl"), Grund im Code genannt.
  VERDIKT: CONFIRMED. Follow-up: Voll-Read des Files (alle 515 Zeilen) bestaetigt
  null weitere Skips — nicht mehr nur Search-verifiziert.
- M2-S2 Skip-Zaehler stabil: 57/1/0 und 28/1/1 zeigen je genau 1 Skip → kein
  neu eingefuehrter Skip (Zaehler-Ebene; Boundary ggf. verschieden).
  VERDIKT: CONFIRMED (Zaehler), Rest MISSING (Boundary-Bestaetigung).
- M2-S3 Handoff-Frage: Der Skip INVALIDIERT den Handoff NICHT — er verlagert die
  Mac-E2E-Abdeckung auf die Mac-Seite. Ungueltig waere der Handoff erst durch
  FEHLENDE Mac-Abdeckung — und die fehlt (kein Mac-Daemon im RUN-Harness, M7).
  VERDIKT: DISPROVEN ("Skip macht Handoff ungueltig"); MISSING_EVIDENCE (Mac-Abdeckung);
  BLOCKED_OTHER_OWNER (Mac-Runner / RUN-Lane).
*M2-S4 entfernt (Follow-up): Duplikat von M3-1 — siehe dort.*

## OUTPUT
ROLE=M2
CONFIRMED=M2-S1 (ehrlicher Plattform-Skip); M2-S2 (Zaehler stabil); M2-S4 (Differenz bekannt)
DISPROVEN="Der Skip invalidiert den erforderlichen Handoff"
MISSING_EVIDENCE=Mac-seitige E2E-Abdeckung (irgendeine: Mac-pytest ODER RUN1 mit echtem Daemon)
OWNER_PACKET=Mac-Lane: 1 Zeile — wo laeuft `test_mac_worker_uploads_and_verifier_reconciles` gruen? (Runner-Name/Run-ID)
CRITICAL_PATH=M2-S3 → M9 RUN1_EVIDENCE (Orphan an RUN1 haengen, falls Daemon dort laeuft)
NEXT_OWNER=Mac-Runner-Owner / RUN-Harness-Owner
DO_NOT_REPEAT=Skip entfernen/umgehen; M3-Zahlen-Debatte; Handoff-Neu-Zertifizierung
STATUS=DONE_STATIC

## FOLLOW_UP (2026-09-28, Selbst-Widerlegung)
ROLE=M2
SURVIVING_CONFIRMED=M2-S1 (jetzt Voll-Read-verifiziert); M2-S2; M2-S3
REMOVED=M2-S4 (Duplikat M3-1)
MINIMUM_NEXT_ACTION=Mac-Abdeckungs-Ort benennen (unveraendert)
MINIMUM_TEST_OR_EVIDENCE=1 Zeile: Runner/Run-ID des Mac-E2E-Laufs
NEXT_OWNER=Mac-Runner-Owner
STATUS=DONE_STATIC
