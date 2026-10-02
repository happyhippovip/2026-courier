# M8 — RUN2_NO_REPLAY (Muse 8)

Stand: 2026-09-28, Quelle: Harness-Reads (KEIN RUN ausgefuehrt — verboten + Shell down)

## USER_PROBLEM (Operator-Sicht)
Beweist RUN2 "Neustart ohne Replay" — oder wuerde das Harness auch hier an sich
selbst scheitern, bevor es irgendetwas ueber Courier aussagt?

## CURRENT_RUNTIME_TRUTH: Was RUN2 beweisen soll (gelesen)
`verify_run2_evidence.py:41`: A_SURVIVED (A bleibt RECONCILED), B_RECONCILED,
NO_REPLAYS. Methode: `kill -9` Server (`run_2_mac.sh:12`), Neustart "gleiche DB".

## CURRENT_RUNTIME_TRUTH: Luecken (lese-verifiziert)
- Alle M7-Luecken 1-4 vererbt: `--db`-Illusion (`run_2:28`), No-Op-Worker (`:35`),
  Vordergrund-Verifier mit ignoriertem `--target=B` (`:40`, Haenger), kein B-Setup.
- M8-1 DB-Namens-Bruch: `run_2` nutzt `ledger_run1.db`, der Checker verlangt
  `artifacts/run2/ledger_run2.db` (`verify_run2:11`) → immer "missing".
- M8-2 Checker-SQLite (Tasks A UND B, `:22-31`) vs JSON-State; gleiche
  Crash-Anfaelligkeit wie M7-6.
- M8-3 No-Replay-Check via Log-Substring (`:37`: "Claimed task A" darf NICHT
  vorkommen) ist VAKUOS — die Strings kommen nie vor, also "besteht" die
  Pruefung auch bei totalem Stillstand. False-Negativ UND False-Positiv zugleich.
- M8-4 Kill-Annahme: `kill -9 $OLD_PID` + Port-Check passt nur auf Flask-dev aus
  `run_1`; unter Supervisor (gunicorn) gaelten andere PIDs/Prozesse.
- Code-Seite (vgl. M4/M5): No-Replay-Maschinerie EXISTIERT (409er, Quarantaene,
  frische Identitaeten bei Resume) — RUN2-wie-geskriptet kann sie nur nicht
  beobachten.

## VERDIKT
M8-CLOSED als Harness-Urteil: Wie M7 — das Harness kann den Beweis, den es
benennt, nicht liefern (Haenger + Pfad-/Format-Brueche + vakuoser No-Replay-Check).
Kein Code-Urteil, kein RUN ausgefuehrt.

## ACCEPTANCE_REQUIREMENT (Reparatur-Liste, Owner: RUN-Lane)
M8.1: M7.1-8 uebernehmen; zusaetzlich: DB-Namen angleichen ODER JSON-State als
  einzige Wahrheit; No-Replay-Nachweis aus STATE (kein zweiter attempt/dispatch
  fuer A, kein zweiter Effekt-Nachweis) statt aus Log-Substrings; Kill-Prozedur
  an die echte Server-Startart binden (dev vs gunicorn).

## BLOCKED_UNTIL
- Harness-Reparatur (mit M7 gemeinsam) + Festlegung: Welcher Server wird
  neugestartet (dev/gunicorn), welche B-Definition gilt?

## NEXT
M9 (Konvergenz) — M8 liefert: Code bereit zum Beobachten, Harness nicht bereit
zum Hinschauen.
