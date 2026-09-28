# MUSE TURBO — FAMILY=RUN2_RESTART (A/B/C Synthese, parent-verifiziert)

STATUS=TURBO_COMPLETE
OWNER=MUSE/blooming-albedo (parent) / HOST=MAC / DATE=2026-09-28
KINDER: A=SOURCE_TRUTH, B=ADVERSARIAL_FALSIFIER, C=EVIDENCE_MINIMALITY (alle READ_ONLY, keine Nesting).
VERWORFEN (unsupported/abgeschnitten): A-Schritt-4-Rest ("St…"), B-Schluss-Satz — ersetzt durch parent-gepruefte Zeilen unten.

## Synthese (dedupliziert)

SOURCE_TRUTH=Kette: nur QUEUED-Steps claimbar (app.py:301-303); frische Identitaet pro Claim — attempts+1, attempt_id, dispatch_id=uuid4, run/result=None (:349-354); DISPATCHED-Park + Worker-Fence (:360-365); stale-Reclaim → HUMAN_REQUIRED + Goal BLOCKED (:447-460, parent-verifiziert); Verify-Guards + RECONCILED-Advance (:487-527, aus G073 REUSE).
CONFIRMED=Resume-retry loescht stored result NICHT (:546-557 nur status/worker_id/resumed_from; Rotation delegiert an naechsten Claim :350-352) — B-Befund + MMAC-015-R1-Linie. Wirkung: byte-identischer Stale-Resend matcht 6-Feld-Check (:381) → ACK_DUPLICATE, KEINE Re-Execution. Absicht per Kommentar :378-379 (Lost-Response-Schutz) → BY_DESIGN, kein Fix.
DISPROVEN=Re-Execution nach Restart (alle Pfade: Reclaim quarantiniert, Claim rotiert IDs, Verify gatet Advancement); separater Reconcile-Hop (bereits S18-3); Konkurrenz-SHA (bereits MG01-S4).
MINIMUM_PROOF=Vorhanden: G088/G089/G090 PROVEN (Kette, OVR-002-Reuse, verifiziert gelesen) + tests/test_run_physical_restart.py (physisch, ausserhalb READ_ONLY). Kleinste Luecke: In-Memory-Unit-Test resume-retry → stale-identical-resend → ACK_DUPLICATE ohne Re-Execution (kein physischer Run noetig).
MINIMUM_FIX=NONE (BY_DESIGN; ein Loeschen wuerde legitime Lost-ACK-Resends brechen). Optionale Haertung (LATER, Central Writer): ACK-Narrowness-Klasse mit F1/F2-Doktrin zusammenfuehren.
OWNER=— (kein Fix faellig)
DO_NOT_REPEAT=sha256-muse-turbo-run2-01
