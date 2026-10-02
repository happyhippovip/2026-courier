# UA-B01 — "Braucht dich": Was wartet konkret auf mich?

Prioritaet: B (Braucht dich)
Stand: 2026-09-28, Quelle: Repo-Reads (kein RUN, kein Ledger)

## USER_PROBLEM
Mehrere Dokumente sagen implizit "Mensch muss ...": Pilot-Autorisierung
(`PILOT_READINESS_DECLARATION.md`), Mac-Canary (`GATE_STATE_CURRENT.md`),
`FINAL_SHA`-Push (`MAC_CORE_FREEZE_MATRIX.md`: HUMAN-DEPENDENT). Es gibt aber keine
Liste: Was genau wartet auf MICH, was auf eine Maschine, was ist optional?

## CURRENT_RUNTIME_TRUTH (belegt)
- `PILOT_READINESS_DECLARATION.md:19`: "A human operator ... MUST authorize the
  actual start of the Pilot phase."
- `MAC_CORE_FREEZE_MATRIX.md:19-20`: HUMAN-DEPENDENT = `FINAL_SHA`-Push auf `main`,
  Mac-Setup/Auth-Umgebung.
- `GATE_STATE_CURRENT.md:20`: `NEXT_ACTION: AWAIT_MAC_CANARY / PHYSICAL_PROOF_RUNNER`
  (Maschinen-, kein Menschen-Wait — steht aber nirgends explizit).
- `server/app.py` `/walls`-Route existiert (`:171`), Inhalt/Format ungeprueft;
  `central_state.json` enthaelt kein Needs-You-Feld.
- Kein `NEEDS_YOU.md` / keine Warteschlange mit Owner-Spalte im Repo gefunden.

## ACCEPTANCE_REQUIREMENT
UA-B01.1: Eine Datei `ops/ai/NEEDS_YOU.md` (Entwurf, Prep-only) listet jeden
Menschen-Wait als Zeile: `ITEM | OWNER (USER/MAC_OP/CHIEF) | BLOCKS_PHASE |
WIE_ENTSCHEIDEN (1 Satz) | DEFAULT_BEI_NICHTANTWORT (warten, nie raten)`.
UA-B01.2: Maschinen-Waits (Mac-Canary) stehen getrennt unter `WAITING_ON_MACHINE`,
nie vermischt mit Menschen-Waits.
UA-B01.3: Jeder Eintrag nennt sein Freigabe-Signal (z.B. Datei-Lock wie
`PILOT_SIGNAL_POSITIVE.lock` oder explizites Operator-Wort), kein implizites
"Weitermachen ok".

## MISSING_SYSTEM_SUPPORT
- `/walls` liefert unbekanntes Format; kein dokumentiertes Needs-You-Schema.
- Kein Runtime-Feld `waiting_on: USER|MACHINE|NONE` in Zielen/Tasks.
- `check_pilot_readiness.py` prueft nur Datei-Existenz, keine Autorisierung.

## PREPARABLE_NOW
- Dieses Dokument + `NEEDS_YOU.md`-Schema (3 Sektionen: JETZT / SPAETER / MASCHINE).
- Inventar der heute bekannten Waits (s. Runtime-Truth).

## BLOCKED_UNTIL
- Klare Owner-Ansage: Wer ist Mac-Canary-Operator? (Name/Rolle, nicht "irgendwer".)
- Pilot-Go/NoGo-Kriterien sind entschieden (siehe UA-I01).

## NEXT
UA-C01 (Failure/Retry/Restart-Ehrlichkeit).
