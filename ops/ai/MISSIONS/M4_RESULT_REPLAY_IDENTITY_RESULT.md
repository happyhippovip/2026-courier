# M4 — RESULT_REPLAY_IDENTITY RESULT

## OUTPUT

| RESEND_FALL | SERVER_ANTWORT | DOPPEL_WIRKUNG | BELEG |
|-------------|----------------|----------------|-------|
| Exakter Resend (gleiche Felder `dispatch_id`, etc.) | `{"status": "ACK_DUPLICATE"}`, 200 | NEIN | `server/app.py:364-368` |
| Spaeter/Falscher Resend (Task verarbeitet, andere Felder) | `{"error": "Conflicting result for already processed task"}`, 409 | NEIN | `server/app.py:369-370` |
| Nicht-DISPATCHED (Task QUEUED, worker_id weicht ab) | `{"error": "Invalid task or worker"}`, 400 | NEIN | `server/app.py:372` & `:413` |
| Nicht-DISPATCHED (Task QUEUED, gleicher worker_id) | `{"error": "Task is not awaiting a result"}`, 409 | NEIN | `server/app.py:372-374` |
| Falscher Worker (worker_id mismatch bei DISPATCHED) | `{"error": "Invalid task or worker"}`, 400 | NEIN | `server/app.py:372` & `:413` |
| Veralteter dispatch_id (Task DISPATCHED, aber alter dispatch_id) | `{"error": "dispatch_id mismatch"}`, 400 | NEIN | `scripts/integration_contract.py:138-140` & `server/app.py:380` |
| Doppelt-verifiziert (exakter Resend `/tasks/verify` auf RECONCILED) | `{"status": "ACK_DUPLICATE"}`, 200 | NEIN | `server/app.py:476-479` |
| Doppelt-verifiziert (anderes verify auf RECONCILED) | `{"error": "Task already reconciled"}`, 409 | NEIN | `server/app.py:476-480` |

Verdict: `REPLAY_SAFE_STATIC: YES`
Kein Pfad ermoeglicht eine doppelte Wirkung. Der Status ist streng idempotent gegenüber Replays (und fängt veraltete Resultate mit 400/409 sicher ab).
