# M4 — RESULT_REPLAY_IDENTITY (Muse 4)

Stand: 2026-09-28. Prep-only: statische Analyse, kein RUN, kein Ledger.

## OBJECTIVE
Beweisen (statisch) oder widerlegen: Kann ein Ergebnis doppelt wirken?
Exakter Resend vs. spaeter/falscher Resend — was antwortet der Server,
und ist das fuer den Nutzer verstaendlich?

## ANCHORS (belegt, eigene Reads)
- Exakter Resend -> `ACK_DUPLICATE` (`server/app.py:364-371`); verarbeiteter
  Task + anderes Ergebnis -> 409 (`:372-373`); nicht-DISPATCHED -> 409 (`:376`).
- Retry erzeugt frische attempt/dispatch-IDs erst beim naechsten Claim
  (`:539-545`); alte Ergebnisse binden danach nicht mehr.
- Worker liefert nur `RESULT_READY` erneut aus, rechnet nie neu
  (`daemon.py:339-358`); 4xx -> `RELEASE_PENDING` + Freigabe (`:345-354`).
- Nutzer-Luecke: Codes ohne Erklaertext (UA-C01).

## SCOPE (read-only)
`server/app.py` (`/tasks/result`, `/tasks/verify`, resume),
`scripts/integration_contract.py`, `scripts/windows_worker/daemon.py`,
`tests/test_p3_server_idempotency.py`, `tests/test_result_identity_binding.py`.

## METHOD
Statisch: alle Resend-Pfade aufzahlen (exakt/spaet/falsch/doppelt-verifiziert),
Server-Antwort je Pfad aus Code ableiten, Doppel-Wirkungs-Frage je Pfad mit
JA/NEIN + Code-Stelle beantworten. Keine Requests senden.

## OUTPUT
Tabelle `RESEND_FALL | SERVER_ANTWORT | DOPPEL_WIRKUNG | BELEG`.
Verdict: `REPLAY_SAFE_STATIC: YES|NO|PARTIAL` + Liste unverstandener Faelle.

## BLOCKED_UNTIL
Physischer Doppel-Send-Test (fremder RUN) fuer Laufzeit-Bestaetigung.

## DONE_WHEN
Alle Resend-Faelle sind tabelliert; kein Pfad ohne Antwort-Zeile.
