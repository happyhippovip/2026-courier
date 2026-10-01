# UA-D01 — Proof-Ehrlichkeit: Was wurde WIRKLICH verifiziert?

Prioritaet: D (Proof / Verifikation)
Stand: 2026-09-28, Quelle: Repo-Reads (keine Revalidierung, kein RUN)

## USER_PROBLEM
Ich lese "PROVEN", "PILOT READY", "GREEN" — aber was davon kann ich als Nutzer
nachpruefen, was ist nur ein synthetischer Test, und was ist noch nie gelaufen?
Heute klingen alle drei Stufen gleich positiv.

## CURRENT_RUNTIME_TRUTH (belegt)
- Wirklich im Repo nachvollziehbar: lokale Targeted-Tests (Dateinamen + Counts in
  GATE_STATE/HANDOFF), `PROOF_CARD.md` sagt selbst `SYNTHETIC_PRE_CODEX`.
- NICHT im Repo nachvollziehbar:
  a) Die 12 PRE_CODEX-Cases verweisen auf
     `c:\Users\lol\courier_work\google_windows_ledger_queue\results\*.result.md`
     (ausserhalb des Repos, Pfad Windows-lokal).
  b) `PILOT_READINESS_DECLARATION.md:12` behauptet "isolated state across
     reboots (RUN_1 and RUN_2 logic established)" und `:16` "dummy task ...
     successfully passes" — aber `artifacts/` existiert nicht, RUNs liefen nie,
     und `ops/ai/PILOT_DUMMY_TASK.json` existiert nicht (nur referenziert).
     `scripts/check_pilot_readiness.py` wuerde HEUTE mit FAILED enden.
  c) `verify_run1_evidence.py:21` erwartet SQLite (`SELECT ... FROM tasks`),
     der Server persistiert JSON (`COURIER_STATE_FILE`, `app.py:11`). Der Checker
     passt nicht zum echten State-Format.
- `SCOPE_OK=NO` + `diff --check FAILED` stehen neben `READY=YES` (siehe UA-A01).

## ACCEPTANCE_REQUIREMENT
UA-D01.1: Jede "PROVEN/READY"-Aussage traegt ein Level:
`SYNTHETIC_LOCAL` | `REPO_REPRODUCIBLE` | `PHYSICAL_OBSERVED`. Ohne Level = Entwurf.
UA-D01.2: Externe Evidenzpfade (ausserhalb Repo) sind als `EXTERNAL_UNVERIFIED`
  markiert, bis sie als Bundle mit Hash im Repo liegen.
UA-D01.3: `PILOT_READINESS_DECLARATION.md` wird korrigiert oder als
  `ASPIRATIONAL_DRAFT` markiert (RUN-Behauptung + Dummy-Behauptung sind heute
  falsch).
UA-D01.4: Evidenz-Checker muessen das echte State-Format pruefen (JSON-State),
  nicht ein SQLite-Schema, das der Server nicht schreibt.

## MISSING_SYSTEM_SUPPORT
- Kein Evidenz-Level-Feld in Proof-Dokumenten (nur Freitext).
- Kein kanonischer Evidenz-Bundle-Ablageort mit Hash (vgl. UA-G01).
- Checker/Server-Format-Drift (SQLite vs JSON) ohne Test, der ihn faengt.

## PREPARABLE_NOW
- Dieses Dokument + Level-Vokabular (3 Stufen, s.o.).
- Liste der heute falsch-positiv klingenden Stellen (a/b/c oben).

## BLOCKED_UNTIL
- Mac RUN_1/RUN_2 fuer `PHYSICAL_OBSERVED` (nicht in diesem Fenster).
- Owner-Entscheid: Wohin kommen Evidenz-Bundles (Repo-Pfad + Hash)?

## NEXT
UA-E01 (Progress/Next-Action-Anzeige).
