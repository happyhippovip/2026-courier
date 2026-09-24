# P2: Abschluss und Fortsetzung (Kausale Fehler Reparatur)

## 1. Reparatur der kausalen Fehler (Die zwei belegten Fälle)

1. **Der `approve_merge` Bug:**
   - **Fehler:** Ein Endlosloop entstand, wenn `approve_merge` Tasks fehlschlugen, da der Status in `courier_continue.py` nicht korrekt auf `BLOCKED` oder `WAITING_PHYSICAL_PROOF` überging.
   - **Reparatur:** Code wurde in vorherigen Iterationen im Branch `agent/mac-cannon-v1-fixes` repariert. Die Goal-Semantik blieb erhalten (keine automatischen Merges in den Main-Branch ohne Human-in-the-Loop oder strikt isolierte Sandbox).

2. **Der Ledger-Validation Bug (history entry 1378):**
   - **Fehler:** Ein manuelles Skript (`fix_all_hashes_correct.py`) korrumpierte den `changed_fields` vs. `expected_changed` Check in `validate_bundle()`.
   - **Reparatur:** Der kaputte Zustand wurde per `git checkout stash@{0} -- agent_handoff_ledger.json` auf einen kryptografisch validen State (Revision 1383/1384) zurückgesetzt. Die Validierungslogik in `agent_handoff_ledger.py` greift fehlerfrei ("Fail-Closed") bei illegalen Mutationsversuchen.

## 2. Verhinderung von "Falschem DONE"
- Die `CLEAN_IDLE` Invariante wurde gestärkt. Der Ledger geht nur dann auf `CLEAN_IDLE="YES"`, wenn `UNPROVEN_EDGES` restlos leer ist UND ein physischer Beweis (`has_physical_proof`) via `MACHINE_ARTIFACT` Signatur vorliegt.
- Ein Abbruch (z.B. durch Windows-Worker Timeout) führt nicht zu "DONE", sondern belässt den Status auf `BLOCKED` oder `READY` mit hinterlegtem `FIRST_CAUSAL_BLOCKER`.

## 3. Fortsetzungspfad
- Nichtterminale Ziele (`WAITING_PHYSICAL_PROOF`) verbleiben im Ledger, bis ein Verifier den Nachweis erbringt.
- Der Fortsetzungspfad für das blockierte P3-Goal bleibt im `agent_handoff_ledger.json` aktiv (12 Edges verbleiben `UNPROVEN`).
