# AUTODRAIN WINDOW — Lane 5 (changed-SHA invalidation)

SEED: session 01a0e78f… → 0x01A0E78F mod 10 = 5. Kein AUTODRAIN-Claim vorhanden
(glob leer) → Familie 5 hiermit belegt. Eigene Datei; fremde Lanes unberührt.
HEAD bei Runden: 34b0a42 (fix-cb1-new). READ_ONLY, kein RUN, kein Ledger.

## Runde 1 (diese)
ROUND_TASK=5.3 Korrektur-eigenes-Fehlurteil + SHA-Triage-Daten sichern
- 5.1 (Doku-Triage per SHA-Strings) NICHT gestartet: W4_STALE_DOC_REPORT.md deckt
  sie ab (P0/P1/P2 + 35 .txt + 16 .md). Eigene Inventur aus Vorrunde (3c2aa51: 18
  Dateien; e5751783: 14; 34b0a42: 17 in ops/ai+docs) als Zweitzaehlung konsistent.
- 5.3: Eigenes Re-Anchor-Fehlurteil ("Sonnet-Muster absent") via Direkt-Read
  :54-92 widerlegt → :62 `expected_paths = set(...)` BESTAETIGT (dritte Lesung
  nach WALL_03/RESUME). Ursache: Suchpattern-Luecke + ungelesenes Intervall.
  Korrektur in OVERNIGHT_MUSE_WINDOWS_03.md (eigene Datei) vollzogen.
- WALL_QUEUE_CURRENT.md selbst gelesen: Langform (68 Zeilen), PRE_CODEX_READY=YES,
  STATE=AWAITING_CODEX — dritte Variante nach Kurzform + RESUME-NO → Churn
  bestaetigt (Gehoert Familie 0/9, hier nur notiert, kein Eingriff).
SUBCASES_GEPROEFT=5 (Triage-Dedupe vs W4; :62-Verifikation; WALL_QUEUE-Read;
Intake-Reichweite aus Vorrunde bestaetigt; Downstream-Check: nur eigene Datei betroffen)
NEXT_SUBCASE=5.2 Zeilenref-Drift-Audit (zitierte Code-Ranges in Live-Docs vs 34b0a42-Baum)
  — nur falls keine Owner-Klaerung (Freeze/Writer) eintrifft; sonst IDLE.
DO_NOT_REPEAT=5.1-Triage (W4-owned); Verifier-Mechanik (WALL_03/RESUME-owned);
e5751783-Linienargumente ohne Re-Read; WALL_QUEUE-Deutung (Familie 0/9).
