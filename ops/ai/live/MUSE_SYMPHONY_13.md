# Family 13 — crash after result before verify (READ_ONLY_C2)

FAMILY=13
STATUS=FAMILY_COMPLETE
SUBCASES_DONE=5 (13.1 worker duplicate post; 13.2 verifier delay + worker stall; 13.3 verifier stateless crash; 13.4 server atomicity; 13.6 verifier negative idempotency drop)

CONFIRMED_SOURCE_DEFECTS=2 (13.2 Split-Brain Reclaim, 13.6 Negative Idempotency)
EVIDENCE_GAPS=0
DISPROVEN=0
NO_ISSUE=13.1 (Worker sendet Resultat doppelt nach Crash → `ACK_DUPLICATE` Guard in `task_result` funktioniert); 13.3 (Verifier crasht vor POST → task bleibt `RESULT_RECEIVED`, da Verifier stateless pollt, wird er nach Neustart korrekt neu abgeholt); 13.4 (Server-Crash beim Speichern → `tmp+fsync+replace` in `save_state` garantiert Atomizität).

## Fix Packets

**FIX_PACKET 13.2 (Split-Brain Reclaim von fertiggestellten Tasks):**
FILES=server/app.py (task_result)
BUG=`task_result()` aktualisiert bei SUCCESS zwar `task["status"]` auf `RESULT_RECEIVED`, vergisst aber die Synchronisation von `step["status"]` im Goal-Plan (bleibt `DISPATCHED`). Wenn der Verifier verzögert reagiert (> 5 Min) und der ursprüngliche Worker stale wird, greift `reclaim_stale()` auf das veraltete `DISPATCHED` im Step zu und überschreibt den erfolgreich abgelieferten Task mit `HUMAN_REQUIRED`. Das Resultat ist effektiv vernichtet.
MIN_FIX=Am Ende von `task_result()` zwingend `_, step = _find_workflow_step(state, task_id)` aufrufen und `if step: step["status"] = task["status"]` setzen (wie es der Verifier bereits tut).
MIN_TEST=Submit Result → Setze Worker `last_seen` > 300s → Call `reclaim_stale()` → Assert Task ist immer noch `RESULT_RECEIVED` und nicht `HUMAN_REQUIRED`.
OWNER=WINDOWS_CENTRAL_WRITER
BEFORE_RUN1 (Korrumpierte Zustandsmaschine)

**FIX_PACKET 13.6 (Negative Idempotency Break im Verifier):**
FILES=server/app.py (verify_task_result)
BUG=Wenn der Verifier ein `FAIL`-Urteil abgibt und die HTTP-Response verloren geht, wiederholt der Verifier den POST. Der Duplicate-Guard deckt jedoch nur `RECONCILED` ab. Bei `FAILED_VERIFICATION` triggert der nächste Check `task["status"] != "RESULT_RECEIVED"` und wirft einen fehlerhaften `409 Conflict`. Der Verifier verfängt sich in einer Konflikt-Schleife.
MIN_FIX=Den Duplicate-Guard erweitern: `if task.get("status") in ("RECONCILED", "FAILED_VERIFICATION"): ... if verification.get("result_id") == data.get("result_id"): return ACK_DUPLICATE`.
MIN_TEST=Sende `FAIL` Verification → Sende exakt gleiche `FAIL` Verification erneut → Erwarte `ACK_DUPLICATE` (200 OK) statt 409.
OWNER=WINDOWS_CENTRAL_WRITER
BEFORE_RUN1 (Korrumpierter Proof Contract)
