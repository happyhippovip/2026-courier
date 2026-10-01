# M5 — WORKER_HEARTBEAT_RESTART RESULT

## OUTPUT

| FALL | SERVER_URTEIL | NUTZER_SIEHT | ZEIT_BIS_SICHTBAR |
|------|---------------|--------------|-------------------|
| Gesund | Task bleibt DISPATCHED, Worker verfügbar (oder busy) | ACTIVE / DISPATCHED | Sofort (0s) |
| Still (Freeze >300s) | Watchdog greift: Task -> HUMAN_REQUIRED | HUMAN_REQUIRED (STALE_WORKER_EFFECT_AMBIGUOUS) | ~300-360s |
| Crash-vor-persist | Watchdog greift nach Ablauf Timeout | HUMAN_REQUIRED (STALE_WORKER_EFFECT_AMBIGUOUS) | ~300-360s |
| Restart mit Amnesie (abweichender `current_task`) | Server erkennt Mismatch, setzt auf HUMAN_REQUIRED | HUMAN_REQUIRED (WORKER_RESTARTED_AND_LOST_STATE) | Sofort bei Re-Register |
| Restart ohne Feld (kein `current_task` im Payload) | Server behält Zuweisung (`current_task = server_task`), Worker heartbeatet leer weiter | ACTIVE / DISPATCHED (Task haengt unendlich) | Nie (Worker aktualisiert `last_seen` kontinuierlich, Watchdog feuert nie) |

Verdict: `RESTART_SEMANTICS_CLEAR: NO`

**Schmerzhafteste Lücke:** Fall "Restart ohne Feld" ist kritisch. Wenn ein Worker ohne `current_task` im Payload heartbeats sendet, übernimmt der Server den alten `server_task`. Der Worker bleibt für den Server "busy" mit dem Task, aber der Worker selbst hat den Task verloren und holt ihn nicht neu ab. Weil Heartbeats gesendet werden, wird `last_seen` laufend aktualisiert und der Watchdog greift nie (300s Timeout wird nie erreicht). Der Task bleibt für immer als "ACTIVE" für den Nutzer hängen (Liveness Hang).
