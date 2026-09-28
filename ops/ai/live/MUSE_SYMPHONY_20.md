# Family 20 — provider failure isolation (READ_ONLY_C2)

FAMILY=20
STATUS=FAMILY_COMPLETE
SUBCASES_DONE=4 (20.1 instant retry burnout; 20.3 attempt_id isolation; 20.4 terminal limit; 20.5 human resume retry limit)

CONFIRMED_SOURCE_DEFECTS=1 (20.1 Instant Retry Burnout / Missing Bounded Backoff)
EVIDENCE_GAPS=0
DISPROVEN=0
NO_ISSUE=20.3 (Ein verzögertes Resultat eines alten Worker-Threads wird von `validate_durable_result` über `attempt_id` und `dispatch_id` sicher abgewiesen → ContractError 400); 20.4 (Hartes Limit von 3 Attempts funktioniert strukturell); 20.5 (Ein manueller Resume aus `FAILED_TERMINAL` inkrementiert die `attempts` auf 4, was bedeutet, dass ein erneuter Fehler sofort wieder in `FAILED_TERMINAL` endet und nicht noch 3 weitere Auto-Retries auslöst → sicheres Design).

## Fix Packets

**FIX_PACKET 20.1 (Instant Retry Burnout):**
FILES=server/app.py (task_result, claim_task)
BUG=Wenn ein Provider-Fehler auftritt (z.B. Rate Limit, `status != "SUCCESS"`), setzt der Server den Task sofort auf `QUEUED` ohne Delay. Da `claim_task` keine Backoff-Sperre hat, wird der Task im selben Bruchteil einer Sekunde wieder geclaimt und verbrennt sofort alle 3 Attempts am selben transienten Rate-Limit-Fehler.
MIN_FIX=Einführung eines `DELAYED` Status oder eines `retry_after` Timestamps auf dem Task. `claim_task` darf Tasks nur dann ausliefern, wenn `time.time() >= retry_after`.
MIN_TEST=Task-Result mit Error senden → Assert: Task kann in den nächsten X Sekunden nicht durch `/tasks/claim` abgerufen werden.
OWNER=WINDOWS_CENTRAL_WRITER
BEFORE_FREEZE (Autonomie im Dauerbetrieb andernfalls extrem instabil bei API-Latenzen).
