# Family 15 — crash after reconcile before next dispatch (READ_ONLY_C2)

FAMILY=15
STATUS=FAMILY_COMPLETE
SUBCASES_DONE=5 (15.1 verifier duplicate PASS; 15.2 next task dispatch continuity; 15.3 goal termination state; 15.4 stale reclaim immunity; 15.5 next-worker immediate crash)

CONFIRMED_SOURCE_DEFECTS=0
EVIDENCE_GAPS=0
DISPROVEN=0
NO_ISSUE=15.1 (Verifier retried ein `PASS` nach Crash → `ACK_DUPLICATE` beendet den Request frühzeitig, `current_step_index` wird sicher vor einem Doppel-Increment geschützt); 15.2 (Server-Restart nach Reconcile → Die Queue nimmt nahtlos den `QUEUED`-Nachfolger über `current_step_index` auf); 15.3 (Letzter Task im Plan → Goal wird sicher auf `DONE` gesetzt, weitere `claim_task`-Calls ignorieren es); 15.4 (Der veraltete Worker des `RECONCILED`-Tasks wird irgendwann stale → ignoriert von `reclaim_stale()`, da Step nicht mehr `DISPATCHED` ist); 15.5 (Der *nächste* Worker crasht direkt nach Claim → Standard-Fail-Closed über `HUMAN_REQUIRED`).

## Fix Packets
(Keine Defekte in dieser Familie gefunden, die Kette Reconcile -> Next Dispatch ist unter Crash-Bedingungen idempotent und robust.)
