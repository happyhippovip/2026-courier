# M4 — RESULT_REPLAY_IDENTITY (Muse 4)

Stand: 2026-09-28, Quelle: Code-Reads (`server/app.py`, `daemon.py`, Contract)

## USER_PROBLEM (Operator-Sicht)
Wenn ein Result zweimal ankommt (Netz-Wackler, Neustart, Retry): Wird es doppelt
gezaehlt, doppelt verifiziert — oder erkennt Courier das Duplikat?

## CURRENT_RUNTIME_TRUTH (belegt)
- Exakter Resend → `ACK_DUPLICATE` (200): Identitaet = goal/task/attempt/dispatch/
  worker/run/result/status + Artifact-Vergleich (reihenfolge-insensitiv),
  `app.py:364-371`.
- Abweichendes Result auf verarbeitetem Task → 409 (`:372-373`); Result auf
  nicht-DISPATCHED Task → 409 (`:376-377`). Konflikte sind LAUT, nie still.
- Verify-Seite: gleiches `result_id` auf RECONCILED → `ACK_DUPLICATE` (`:479-483`).
- Daemon: RESULT_READY wird bis DELIVERED wiederholt; 4xx → REJECTED →
  RELEASE_PENDING → Server-Quarantaene statt Endlos-Schleife (`daemon.py:339-354`).
- `resume retry` mintet frische attempt/dispatch-IDs; alte Results binden danach
  nicht mehr (`app.py:539-550` + Claim `:327-347`).
- Effekt-Seite: Identitaet schuetzt vor Doppel-RESULT, nicht vor Doppel-EFFEKT
  (zwei lebende PowerShells, siehe M6).

## VERDIKT
M4-CLOSED (Code-Seite): Replay-sicher per Konstruktion fuer exakte Resends;
Konflikte failen laut (409). Kein stiller Doppel-Zaehler in den gelesenen Pfaden
gefunden. Physisches Replay-Sturm-Verhalten unbeobachtet (braucht RUN, verboten).

## ACCEPTANCE_REQUIREMENT
M4.1: Die drei 409-Unterfaelle (bereits-verarbeitet / nicht-erwartet /
  Identitaets-Mismatch via 400) sind im Support-Bundle unterscheidbar
  (Sub-Reason statt nur "409").
M4.2: Jedes `ACK_DUPLICATE` ist im Log/State als Duplikat erkennbar (kein
  Verwechseln mit Erst-Ack).

## MISSING_SYSTEM_SUPPORT
- Keine 409-Sub-Reason-Codes; Duplikat-Acks nicht separat gezaehlt.

## PREPARABLE_NOW
- Dieses Paket + Entscheidungsbaum Resend-vs-Konflikt (aus Code, statisch).

## BLOCKED_UNTIL
- Sub-Reason-Owner (kleine Code-Aenderung, fremd). Kein RUN noetig fuer M4.1-Spec.

## NEXT
M5 (Heartbeat/Restart) — M4 liefert: Transport-Duplikate sind abgedeckt.
