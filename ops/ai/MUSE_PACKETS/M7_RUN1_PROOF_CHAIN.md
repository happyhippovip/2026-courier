# M7 — RUN1_PROOF_CHAIN (Muse 7)

Stand: 2026-09-28. Statischer Ketten-Check: Skript → Prozesse → Logs → Checker.
Kein RUN (verboten), nur Lesart: WUERDE die Kette schliessen?

## Befund: Kette schliesst statisch NICHT (6 Brueche, alle belegt)
B1. `--port/--db` wirkungslos: `run_1_mac.sh:20` uebergibt Flags, die
    `server/app.py:569-570` ignoriert (fix 8080, State = `COURIER_STATE_FILE`).
    Keine RUN-Isolation; wuerde auf Live-State zeigen.
B2. Worker ist ein No-Op: `run_1_mac.sh:27` startet `scripts.integration_contract`
    als Modul — Datei hat KEIN `__main__` (Vollsuche). Prozess endet sofort,
    claimt nie. Der echte Daemon (`mac_worker/daemon.py`) wird NICHT gestartet.
B3. Verifier-Flags wirkungslos + Blockade: `--target=A` wird nirgends geparst
    (`courier_verifier.py:181-182`: `__main__` → `run_loop()` ohne argv);
    Zeile 31 laeuft im VORDERGRUND (kein `&`) und pollt endlos (`time.sleep(5)`
    in Schleife, `:179`) → "RUN_1 initiated" (`:33-34`) wird nie erreicht.
B4. Checker vs State-Format: `verify_run1_evidence.py:21` erwartet SQLite
    (`SELECT ... FROM tasks`), Server persistiert JSON (`save_state`, `app.py:65-72`).
B5. Checker vs Log-Strings: erwartet `count("Claimed task A")==1` und
    `count("Result for task A")==1` (`:30-35`); Server loggt diese Strings
    NIRGENDS (Vollsuche in `app.py`: keine Treffer).
B6. `touch ledger_run1.db` (`run_1_mac.sh:9-10`) erzeugt eine Datei, die kein
    Prozess je oeffnet (Server nutzt JSON-State).

Was HALT: Port-Check (`lsof`, `:13-16`) und PID-Datei (`:22`) sind sinnvoll.

## Urteil
RUN_1 in heutiger Form beweist nichts: Worker claimt nicht, Verifier blockiert
das Skript, Checker prueft Artefakte, die die Prozesse nicht erzeugen. Jeder
"RUN_1 gruene" aus dieser Kette waere False-Green (vgl. M3).

## ACCEPTANCE / REQUIREMENT (Prep, kein RUN)
- M7.1: Skript startet den ECHTEN Daemon (statt `integration_contract`-No-Op),
  Verifier im Hintergrund, State-Isolation via `COURIER_STATE_FILE` in ein
  RUN-Verzeichnis (Skript-Text als Entwurf, kein Live-Lauf).
- M7.2: Checker prueft JSON-State (Status + IDs) und Server-seitige Fakten
  (Tasks-Tabelle/Dispatch-Zaehlung), keine erfundenen Log-Strings.
  Entweder Server loggt kanonische Claim/Result-Zeilen (Owner-Entscheid) ODER
  der Checker liest State/API.
- M7.3: Dry-Checkliste (lesend, ohne Start): jede Kettenglied-Datei existiert,
  jeder Befehl parst (`--help`/Import), jeder Checker-Erwartung steht eine
  Erzeuger-Zeile gegenueber. Diese Liste liegt VOR dem ersten echten RUN vor.

## BLOCKED_UNTIL
- Owner-Umbau M7.1/M7.2 + M7.3-Dry-Check. Echter RUN erst danach (Mac-Fenster).

## NEXT
M8 (RUN2-No-Replay — Restart-Seite derselben Kette).
