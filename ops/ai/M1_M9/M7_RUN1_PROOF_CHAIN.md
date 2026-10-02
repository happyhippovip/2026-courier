# M7 — RUN1_PROOF_CHAIN (Muse 7)

Stand: 2026-09-28, Quelle: Harness-Reads (KEIN RUN ausgefuehrt — verboten + Shell down)

## USER_PROBLEM (Operator-Sicht)
Was soll RUN1 beweisen — und kann das vorhandene Harness diesen Beweis
ueberhaupt liefern, oder wuerde es auch bei perfektem Code scheitern?

## CURRENT_RUNTIME_TRUTH: Was RUN1 beweisen soll (gelesen)
PROOF_CARD + MAC_CORE_FREEZE_MATRIX + Sheets: genau-einmal A, Hash-Match,
isolierte Umgebung, A RECONCILED, HUMAN_RELAY_COUNT=0.

## CURRENT_RUNTIME_TRUTH: 8 Harness-Luecken (alle lese-verifiziert)
1. `run_1_mac.sh:20`: `--port/--db` werden vom Server IGNORIERT
   (`app.py:566-567`, kein argparse) → KEINE Isolation; RUN1 schriebe auf den
   Live-State (`COURIER_STATE_FILE`-Default).
2. `run_1_mac.sh:27`: "Worker" = `python3 -m scripts.integration_contract` —
   eine Bibliothek ohne `__main__` → sofortiger No-Op-Exit. Sheet Schritt 3
   sucht ihn per `ps aux | grep` (nie zu finden).
3. `run_1_mac.sh:31`: `--target=A` ignoriert (kein argparse; `run_loop` pollt
   ewig im VORDERGRUND → Skript haengt in Zeile 31); Env-Keys setzt niemand.
4. Nirgends wird ein Goal/Task angelegt (kein POST /goals) → Task 'A' existiert
   nie, nichts ist claimbar.
5. Pfad-Bruch: Skript schreibt `logs/*` + CWD-DB; Checker liest `artifacts/run1/*`
   (`verify_run1_evidence.py:9-12`). Sheet Schritt 5 kopiert nur die DB nachtraeglich.
6. Checker erwartet SQLite (`:19-24`), Server schreibt JSON; die DB ist eine per
   `touch` erzeugte 0-Byte-Datei (`run_1:9-10`) → `OperationalError: no such
   table` UNGEFANGEN (Checker crasht statt FAIL zu melden).
7. Log-String-Checks ("Claimed task A", `:30-35`) matchen keine Server-Ausgabe →
   Zaehler 0≠1 → FAIL selbst im Erfolgsfall.
8. Sheet verlangt Branch `coordination/mac-handoff-20260928` — in packed-refs
   NICHT gefunden (nur `.../autofill-task-seed-20260926`); Loose-Ref hier unpruefbar.

## VERDIKT
M7-CLOSED als Harness-Urteil: RUN1-wie-geskriptet kann KEINE Evidenz liefern
(Haenger in Zeile 31, danach FAIL auf jeder Pruefung). Das ist KEIN Code-Urteil
ueber Server/Daemon — nur ueber das Harness. Kein RUN ausgefuehrt.

## ACCEPTANCE_REQUIREMENT (Reparatur-Liste, Owner: RUN-Lane)
M7.1-8: Isolation via `COURIER_STATE_FILE` (statt `--db`); echter Daemon als
Worker; Verifier im Hintergrund + Env-Keys; Goal-Setup-Schritt; Pfade angleichen;
JSON-Checker (statt SQLite); echte Log-/State-Signale (statt erfundener Strings);
Branch-Existenz sichern.

## BLOCKED_UNTIL
- Harness-Reparatur durch RUN-Owner + Mac-Operator-Benennung. Erst dann Re-Entry.

## NEXT
M8 (RUN2-No-Replay) — M7 liefert: gleiche Krankheit, schaerfere Diagnose.
