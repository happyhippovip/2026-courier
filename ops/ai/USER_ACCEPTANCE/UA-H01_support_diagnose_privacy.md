# UA-H01 — Support / Diagnose / Privacy: Was schicke ich, was nicht?

Prioritaet: H (Support / Diagnose / Privacy)
Stand: 2026-09-28, Quelle: Repo-Reads (kein RUN, kein Ledger)

## USER_PROBLEM
Etwas klemmt, ich soll "mal Logs schicken" — aber welche Dateien, und was muss
ich vorher schwaerzen? Heute gibt es kein Diagnose-Paket und keine
Schwaerzungsregel. Keys stehen im Klartext in Reichweite (`config.json`).

## CURRENT_RUNTIME_TRUTH (belegt)
- Diagnose-Quellen (gelesen, vorhanden): `server/state/central_state.json`
  (Goals/Tasks/Worker + Result-/Verification-Bloecke), Worker
  `current_task.json` / `rejected_result_*.json` (Phasen!) — in diesem Checkout
  abwesend = selbst eine Diagnose-Aussage — , `logs/courier_*.log` (nur wenn
  Supervisor lief), Slot `job.json`/`state.json`, Artifact-Records.
- Sensibel: `COURIER_API_KEY`, `COURIER_VERIFIER_API_KEY` (Env/`config.json`),
  `stdout`/`stderr` in Result-Payloads (kann Pfade/Namen enthalten),
  absolute User-Pfade (`C:\Users\...`), Worker-IDs mit Rechnernamen.
- Kein Redaktions-Werkzeug, keine Bundle-Anleitung im Repo gefunden.
- Shell ist in manchen Fenstern down (diese Session): Anleitungen duerfen nicht
  nur aus Shell-Befehlen bestehen (Datei-Kopien muessen reichen).

## ACCEPTANCE_REQUIREMENT
UA-H01.1: Support-Bundle-Manifest: `DATEI | WOFUER | PFLICHT/OPTIONAL`.
  Pflicht: State-Auszug (betroffenes Goal), Worker-Phase, Verifier-Verdict,
  Versionen (Branch/SHA laut `.git/HEAD` + loser Ref).
UA-H01.2: Schwaerzungsregeln VOR dem Senden: Keys → `[REDACTED]`, User-Pfade →
  `<HOME>`-relativ, stdout/stderr nur den betroffenen Task. Eine
  5-Zeilen-Checkliste, kein Tool-Zwang.
UA-H01.3: Der Empfaengerweg ist benannt (wohin schicken: Issue/Pfad/Person —
  heute fehlt das). Keine Zahlungsdaten noetig (Spend-Limit 0,00 EUR).
UA-H01.4: Diagnose ohne Shell ist moeglich (Dateien kopieren + lesen genuegt).

## MISSING_SYSTEM_SUPPORT
- Kein Bundle-Skript, keine Redaktions-Spec, kein Empfaengerweg.
- Kein `privacy.txt`/Datenkarte im Repo.

## PREPARABLE_NOW
- Dieses Dokument + Manifest + Checkliste (Entwurf, sofort nutzbar).
- Negativ-Liste: was NIE ins Bundle darf (Keys, Voll-Logs fremder Goals).

## BLOCKED_UNTIL
- Owner-Entscheid: Bundle-Werkzeug ja/nein + Empfaengerweg.
- Freigabe der Datenkarte (wer sieht Bundles, wie lange gespeichert?).

## NEXT
UA-I01 (Pilot-Feedback als zaehlendes Signal).
