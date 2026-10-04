# UA-G01 — Update / Rollback / Last Known Good: Wie komme ich zurueck?

Prioritaet: G (Update / Rollback / Last Known Good)
Stand: 2026-09-28, Quelle: Repo-Reads (kein RUN, kein Ledger)

## USER_PROBLEM
Nach einem Update oder Fehler will ich zurueck zum letzten guten Stand — ohne
zu raten, was "gut" hiess, und ohne verifizierte Arbeit zu verlieren. Heute gibt
es dafuer weder Knopf noch Verfahren.

## CURRENT_RUNTIME_TRUTH (belegt)
- `ops/ai/CRITICAL_PATH_SYNTHESIS.md:26-27`: `FINAL_SHA` = Last-Known-Good-
  Baseline; `state/`-Snapshots = Rollback-Paket. Aber: `FINAL_SHA`-Push auf
  `main` steht auf BLOCKED (`:17-18`) — es gibt heute KEINEN LKG.
- Verarbeitetes ist unveraenderlich: exakter Resend → `ACK_DUPLICATE`,
  abweichendes Result → 409 (`app.py:364-373`); `force_success` refused (400);
  Artifact-Records sind write-once (`scripts/artifact_store.py`).
- Restart ist per Design kein Replay: `register(current_task=None)` →
  Quarantaene `HUMAN_REQUIRED` (`app.py:195-208`); Daemon-Crash in STARTED →
  Release, nie Re-Execute (`daemon.py:293-302`).
- Keine Rollback-Route, kein Snapshot-Werkzeug, keine LKG-Zeigerdatei im Repo.
- `unregister` ist sticky: nur explizites Re-Register bringt Worker zurueck
  (`app.py:225-239`).

## ACCEPTANCE_REQUIREMENT
UA-G01.1: LKG ist benannt: `FINAL_SHA + State-Snapshot-Hash + Artifact-Dir-Hash
+ Datum + Wer`. Kein Name = kein LKG (ehrlich anzeigen).
UA-G01.2: Rollback-Verfahren (Doku, kein Automatismus noetig): stoppen →
  Snapshot zurueckspielen → Worker re-registrieren (Amnesia→Quarantaene wird
  akzeptiert, kein Replay erwartet) → `/walls` pruefen → gezielt `resume retry`.
UA-G01.3: Rollback veraendert nie RECONCILED-Historie: verifizierte Tasks bleiben
  verifiziert; was danach neu laeuft, bekommt neue attempt/dispatch-Identitaet.
UA-G01.4: Update-Pfad nennt Vorher/Nachher-SHA + Migrationshinweis fuer State-
  Format (heute JSON via `COURIER_STATE_FILE`).

## MISSING_SYSTEM_SUPPORT
- Kein LKG-Zeiger, kein Snapshot-/Restore-Werkzeug, kein dokumentiertes Verfahren.
- `FINAL_SHA` selbst steht noch aus (BLOCKED, fremde Lane).

## PREPARABLE_NOW
- Dieses Dokument + LKG-Zeiger-Schema + Rollback-Schrittfolge (Entwurf).
- Warnung: Heute existiert KEIN wiederherstellbarer LKG — Updates sind Einbahn.

## BLOCKED_UNTIL
- `FINAL_SHA`-Entscheid + Push (fremde Lane, HUMAN-DEPENDENT).
- Snapshot-Owner (wer baut/pflegt das Werkzeug?).

## NEXT
UA-H01 (Support/Diagnose/Privacy).
