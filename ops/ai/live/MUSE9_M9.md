# MUSE9 M9 — Deduplizierung aller aktuellen Findings (Sidecar, READ_ONLY_C2)

Scope: M1–M8 dieses Sidecar-Laufs + Operator-Evidenz 28/1/1. UA-Kette und
M1-M9-Pakete werden ZITIERT, nicht neu gefiled. Kein RUN, kein Ledger.

## BEFORE_RUN1 (Eintritt physische RUNs)
1. Harness-Reparatur M7.1-8 (M7-Paket; M8-Anteil haengt an BEFORE_RUN2) — Owner: RUN-Lane.
2. M3-Zahlentabelle (M3.1) + M3-2/M3-3-Entscheide — Owner: Gate-/Scope-Owner.
3. Mac-Branch existent + Mac-Operator BENANNT + Env steht — Owner: Mac-Lane.
4. M6: Kill-Tree-Fix ODER Risiko-Akzeptanz VOR retry-lastigen Beweisen — Owner: Daemon-/Gate-Owner.
5. Fail-Name aus 28/1/1-Report sichern (M1-S1) — Owner: Report-Owner. (Nicht blockierend
   fuer Harness-Arbeit; blockierend fuer "Suite sauber"-Aussagen.)
6. Lebender Stale-Fall task-replace-001 als ersten Quarantaene-Zeugen einplanen (M5-S5).
7. NEU (Follow-up): Freeze-Regel — Baum mutiert waehrend Read-Only-Fenstern (`app.py`-Guard,
   `daemon.py`-Rework, +2 Test-Goals im Live-State, Ursache unbekannt). Vor JEDER Evidenz: SHA-Pin +
   `git status` + Test-Isolation vom Live-State (`COURIER_STATE_FILE`). Ungesichtete Deltas
   (Daemon result_id-Schema/Timing) dem Owner vorlegen. — Owner: Gate-Owner + Test-Owner.

## RUN1_EVIDENCE (Checkliste, je Claim × Witness-Paar, M7-S1..S5)
- Genau-einmal-A (attempts/dispatch + Phasenfile); Hash-Match (Server-+Verifier-Re-Hash);
  A-RECONCILED (Task+Verification UND Step-Spiegel, Divergenz=Fund);
  Isolation (STATE_FILE-Env + Port-Protokoll); Null-Relay (braucht erst Actor-Logging —
  Rueckverweis nach BEFORE_RUN1, Item 1).
- M2-Orphan (Mac-E2E) an RUN1 haengen, falls echter Daemon laeuft.

## BEFORE_RUN2
1. M8.1-Reparatur (DB-Namen, JSON-Checker, State-statt-Substring) — Owner: RUN-Lane.
2. Kill-Methoden-Entscheid (dev vs gunicorn) + B-Definition — Owner: RUN-Lane.
3. No-Replay-Witness-Verfahren fixiert (M8-S2) — Owner: RUN-Lane.

## RUN2_EVIDENCE (Checkliste, M8-S1/S2/S5)
- A-Snapshot-Gleichheit + kein neuer attempt/dispatch; kein Zweit-Artefakt;
  B nach M7-S1..S3-Spec; Stale-Result-Fall dokumentiert (welcher Trichotomie-Ast?).

## CORE_FREEZE (Regel-/Code-Entscheide, keine Messungen)
- FINAL_SHA-Push (Mensch, bekannt BLOCKED); Scope-Regel M3-S3; conftest/Env-Doku (M1);
  409-Sub-Reasons (M4.1); Stale-Indikator (M5.1); Kill-Tree (M6.3); Actor-Logging (M7-S5).

## DEFER (ausdruecklich spaeter)
- Voll-Suite-green; Product Shell (LOCKED, UA-J01); HIPG-Definition (Pilot-Tor);
  Ledger (FROZEN); jede Revalidierung; 65-96-Cascade-Prompts (verboten).

## Dedupe-Protokoll
- M3-1/M2-S4: einmal unter BEFORE_RUN1-Item 2 (Zahlentabelle), Rest Verweise.
- M4-S6/M6-S5: einmal als BEFORE_RUN1-Item 4 (Doppel-Effekt), Rest Verweise.
- M7-Luecken/M8-Luecken: je einmal im Owner-Paket, hier nur Zeiger (DO_NOT_REPEAT beachtet).
- Q10-Spiegel-Lag: einmal als Witness-Regel (M7-S3, mit Historien-Caveat), kein eigenes Finding.
- Follow-up: M7-S6 hierher konsolidiert (RUN1_EVIDENCE-Orphan-Zeile); M1-S5→S3, M2-S4→M3-1,
  M3-S5→S1 in Quelldateien gefaltet (keine M9-Aenderung noetig); M6-S4/M8-S3 dort praezisiert.

## OUTPUT
ROLE=M9
CONFIRMED=37 Items einsortiert (7+6+3+4+7+6+4 Dedupe-Zeilen); 0 Duplikate übrig (Verweise statt Kopien)
DISPROVEN="RUN-Eintritt ist nah"; "Ein Bucket reicht"; "M7/M8-Specs muessen auf RUNs warten" (Specs stehen, nur Evidenz fehlt)
MISSING_EVIDENCE=Fail-Name (M1); datierte Reports (M3-2); alle RUN-Evidenzen (faellig erst nach Reparatur)
OWNER_PACKET=Diese Datei IST das Paket: 6 Buckets + Dedupe-Protokoll; Details in MUSE9_M1..M8 + UA/M-Paketen (zitiert)
CRITICAL_PATH=Lengster Pfad: Harness-Reparatur (RUN-Lane) + Mac-Operator-Benennung + M6-Entscheid → RUN1 → RUN2 → CORE_FREEZE-Items
NEXT_OWNER=RUN-Lane (Items BEFORE_RUN1-1, BEFORE_RUN2-1/2); Gate-Owner (Item 2, 4); Mac-Lane (Item 3)
DO_NOT_REPEAT=Findings umsortieren ohne neuen Eingang; Buckets neu erfinden; Ledger anfassen; anything physisch starten
STATUS=DONE

## FOLLOW_UP (2026-09-28, Selbst-Widerlegung)
ROLE=M9
SURVIVING_CONFIRMED=Alle 6 Buckets (37 Items); Dedupe-Protokoll erweitert; Freeze-Regel neu (Item 7)
REMOVED=Nichts (Konsolidierungen in Quelldateien vollzogen)
MINIMUM_NEXT_ACTION=BEFORE_RUN1-7 (Freeze+Pin) als Tor vor jeder Evidenz; Rest unveraendert
MINIMUM_TEST_OR_EVIDENCE=Keine neuen Tests — Entscheide + Pins (Owner)
NEXT_OWNER=Gate-Owner (Freeze); RUN-Lane (Reparatur); Test-Owner (Isolation)
STATUS=DONE
