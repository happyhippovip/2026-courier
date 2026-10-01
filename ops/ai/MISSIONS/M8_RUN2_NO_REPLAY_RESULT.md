# M8 — RUN2_NO_REPLAY RESULT

## OUTPUT

### NO_REPLAY_PROVEN_STATIC: YES

Der Wiederanlauf (RUN_2) garantiert, dass eine bereits im State befindliche Task A nicht erneut an einen Worker dispatchet wird, unabhängig vom genauen Crash-Zeitpunkt:

1. **A ist bereits RECONCILED (regulärer RUN_1 Abschluss):** 
   - `server/app.py:277-280` (`claim_task`) holt den nächsten Task über `goal["current_step_index"]`. Bei RECONCILED wurde dieser Index inkrementiert. Task A wird gar nicht erst geprüft.
2. **Crash vor `task_result` (A ist DISPATCHED):**
   - Worker verliert State / meldet sich neu an -> Task wird auf `HUMAN_REQUIRED` gesetzt (`app.py:200`).
   - Timeout (Stale Worker) -> `reclaim_stale` setzt Task auf `HUMAN_REQUIRED` (`app.py:437`).
   - In keinem Fall erfolgt ein automatisches Replay (Amnesie-Schutz greift).
3. **Crash vor `verify_task_result` (A ist RESULT_RECEIVED):**
   - `claim_task` ignoriert Tasks, die nicht `QUEUED` sind (`app.py:282`).
   - Verifier liest `/tasks/pending_verification` neu und verifiziert das vorhandene Result erneut. Kein Worker-Redispatch.
4. **Crash während `claim_task` (A ist QUEUED vs DISPATCHED):**
   - `save_state` nutzt `os.replace` mit vorherigem `os.fsync`. Wenn der Server vor der HTTP-Antwort crasht, weiß der Worker nichts vom Task, aber der Server sieht ihn als `DISPATCHED` -> Stale Worker -> `HUMAN_REQUIRED`.

### Negativ-Beweis-Würdigung
**SCHWACH**.
Das Sheet (`MAC_RUN_2_COMMAND_SHEET.md:17`) und `run_2_mac.sh` fordern, dass in den Logs geprüft wird, ob A *nicht* erneut dispatched wurde (z. B. via Grep auf `logs/server_run2.log`). Die reine Abwesenheit eines Log-Eintrags ist ein schwacher Beweis. Ein starker Beweis wäre ein Query auf die `ledger_run1.db` nach RUN_2, der zeigt: `SELECT attempts FROM tasks WHERE task_id='A'` == 1.

### Race-Tabelle (Crash während der Phasen)

| Phase | Server State | Verhalten nach Restart | Redispatch? |
|-------|--------------|------------------------|-------------|
| Während Claim | QUEUED | Worker hat keinen Task, Server State ist `QUEUED`. | Ja (war aber effektiv nie bei einem Worker gestartet) |
| Nach Claim, vor Result | DISPATCHED | Amnesie / Stale -> `HUMAN_REQUIRED`. | **Nein** |
| Nach Result, vor Verify | RESULT_RECEIVED | Verifier holt Task erneut; Worker ignoriert ihn. | **Nein** |
| Nach Verify | RECONCILED | Index zeigt auf Task B. | **Nein** |
