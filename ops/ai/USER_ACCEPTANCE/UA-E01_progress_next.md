# UA-E01 — Progress / Next: Was passiert als Naechstes, wie weit bin ich?

Prioritaet: E (Progress / Next Action)
Stand: 2026-09-28, Quelle: Repo-Reads (kein RUN, kein Ledger)

## USER_PROBLEM
Als Nutzer frage ich: Wie weit ist mein Auftrag, was ist der naechste Schritt,
und wann ist es fertig? Heute gibt es dafuer keine Antwort — nur Zaehler
(`/status`) und ein `TRUE_IDLE` aus der Wall-Queue, das nichts ueber MEINEN
Auftrag sagt.

## CURRENT_RUNTIME_TRUTH (belegt)
- `server/app.py:277-347`: NEXT ist deterministisch ableitbar — pro ACTIVE-Goal
  genau ein Head (`current_step_index`), Claim nur bei `QUEUED` + Faehigkeits-
  Match; danach `DISPATCHED` mit frischer attempt/dispatch-Identitaet.
- `server/app.py:296-325`: Cost-Deferral ist STUMM (`matched=False`, kein Log,
  keine Kennzahl). Ein Task kann liegenbleiben, ohne dass jemand sieht warum.
- `server/app.py:83-92`: `/status` liefert nur Zaehler
  (goals/active/tasks/workers) — kein NEXT, kein Grund, keine Reihenfolge.
- `server/state/central_state.json`: Q12 steht auf Step 0 `DISPATCHED` mit
  `artifacts: []`; Q10 ist DONE/RECONCILED. Fortschritt = Index/Länge +
  Step-Status, mehr gibt der State nicht her.
- `docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md` + Pocket-Ledger: keine
  erfundenen Prozente/ETAs — alles aus echtem State oder gar nicht.

## ACCEPTANCE_REQUIREMENT
UA-E01.1: NEXT-Anzeige = `Goal | Step i/n | Step-Status | Inhaber (Worker/niemand)
| naechster Systemschritt (claim/liefern/verifizieren/warten) | Warte-Grund`.
UA-E01.2: Keine Prozentbalken, keine ETA-Minuten — ausser aus gemessener Historie
mit Quelle. Erlaubt: `i/n verifizierte Schritte`.
UA-E01.3: Nicht-gestartete Arbeit bekommt einen Grund aus fester Liste
(`BLOCKED | WARTE_AUF_VERIFIKATION | KEIN_PASSENDER_WORKER | KOSTEN_DEFERRED |
NIEMAND_ZUSTAENDIG`), nie nur Schweigen.
UA-E01.4: Cost-Deferral wird sichtbar (welcher billigere Worker wurde erwartet,
Freshness-Fenster 300 s).

## MISSING_SYSTEM_SUPPORT
- Kein NEXT-/Grund-Feld in State oder `/status`.
- Deferral ohne Log/Metrik; keine Reason-Codes im Claim-Pfad.
- Kein Head-Fortschritt-Endpoint (i/n pro Goal ausser via `/goals/<id>`-Lesen).

## PREPARABLE_NOW
- Dieses Dokument + NEXT-Ableitungsregeln (rein aus State lesbar, s. o.).
- Grund-Vokabular (UA-E01.3) als Entwurf.

## BLOCKED_UNTIL
- Owner-Entscheid: Reason-Codes in Claim aufnehmen (Code-Aenderung, nicht hier).
- Laufzeit-Beobachtung fuer Deferral-Sichtbarkeit (kein synthetischer Ersatz).

## NEXT
UA-F01 (Onboarding/Permissions-Manifest).
