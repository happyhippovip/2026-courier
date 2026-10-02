# M3 — LOCAL_DIFF_FALSE_GREEN (Muse 3)

Stand: 2026-09-28. Prep-only: statische Analyse, kein RUN, kein Ledger.

## OBJECTIVE
Klaeren, ob "GREEN"-Aussagen auf ungeprueftem lokalem Diff stehen:
Was ist seit BASE_SHA lokal veraendert, ist das Diff sauber, und ist der
Kandidat ueberhaupt durable referenzierbar?

## ANCHORS (belegt)
- `BASE_SHA=4c1e24cc`, `CANDIDATE=3c2aa516` (GATE_STATE).
- `GIT_DIFF_CHECK=WHITESPACE_ONLY (40 trailing whitespace lines)` (GATE_STATE).
- `SCOPE_OK=NO`: Extra-Datei `tests/test_integration_contract.py` (UA-A01).
- Gate-Policy: SHA nur lokal sichtbar = `DURABILITY_PENDING`
  (`COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md:43-52`).
- Eigener Checkout: `fix-cb1-new @ e575178` — WEICHT vom Kandidaten ab.

## SCOPE (read-only)
Gate-Docs, `tests/test_integration_contract.py` (Existenz + Grund lesen),
`.git`-Refs lesend (kein fetch/checkout/pull).

## METHOD
Statisch: Scope-Verletzung bewerten (gehoert die Datei zum Kandidaten?);
Whitespace-Diff einschaetzen (harmlos vs. Review-Hindernis);
Durability-Status des Kandidaten bestimmen (Remote-Ref/Bundle nachgewiesen?);
eigenen Checkout-SHA als divergierend protokollieren, NICHT angleichen.

## OUTPUT
`DIFF_CLEAN: YES|NO` + `SCOPE_MATCH: YES|NO` + `DURABILITY: READY|PENDING`
+ Divergenz-Notiz (eigener SHA vs. Kandidat). Kein Checkout, kein Fetch.

## BLOCKED_UNTIL
Netz/Git-Zugriff (fremdes Fenster) fuer Remote-Ref-Nachweis.

## DONE_WHEN
Alle drei Flags sind gesetzt und belegt; keine Git-Schreibaktion erfolgt.
