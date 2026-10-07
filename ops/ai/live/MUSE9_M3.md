# MUSE9 M3 — Lokale Aenderungen: False-Green-Risiko (Sidecar, READ_ONLY_C2)

Kein RUN, keine Revalidierung, kein Ledger (FROZEN).

## Reuse zuerst
- `ops/ai/M1_M9/M3_LOCAL_DIFF_FALSE_GREEN.md` (M3-1..M3-5-Inventar).
- `.git/HEAD` (fix-cb1-new) + loser Ref `e5751783` (gelesen).

## Subcases
- M3-S1 Baum ≠ Kandidat: HEAD `e5751783...` vs FINAL `3c2aa516...` vs BASE
  `4c1e24cc...` — drei verschiedene Strings (CONFIRMED gelesen; Abstammung ohne
  Shell unpruefbar). Lokale 28/1/1 uebertragen NICHTS auf Kandidaten-Aussagen.
  VERDIKT: CONFIRMED (methodisch: kein Transfer in beide Richtungen).
  Follow-up VERSTAERKT: Live-Mutation beobachtet — `app.py` (None-Guard + Nettoverkuerzung),
  `daemon.py` (result_id-Schema + Timing-Rework), State (+2 Test-Goals `goal-51043ae8`/
  `goal-5409572b`, "test-worker"). Ursache unbekannt (keine Shell). Evidenz braucht SHA-/File-Pin.
- M3-S2 `git diff --check`: HANDOFF=PASSED vs GATE=40-Whitespace-Zeilen — weiter
  ungeloest (kein Datum, keine neue Messung erlaubt).
  VERDIKT: MISSING_EVIDENCE (braucht datierte Primaer-Reports, fremde Lane).
- M3-S3 Scope-Extra-Datei: `tests/test_integration_contract.py` existiert im Baum
  (Suchtreffer `:60`) → SCOPE_OK=NO-Basis weiter gegenwaertig.
  VERDIKT: CONFIRMED (Existenz); Regel-Entscheid BLOCKED_OTHER_OWNER.
- M3-S4 Eigene Docs (UA-E..J, M1-M9-Pakete, diese Sidecars): nur `.md` unter
  `ops/ai/`, null Source-Touches → null Code-False-Green-Risiko.
  VERDIKT: CONFIRMED (Schreibliste geprueft).
*M3-S5 entfernt (Follow-up): in S1 gefaltet (gleiche Methodik-Aussage).*

## OUTPUT
ROLE=M3
CONFIRMED=M3-S1 (kein Transfer lokal↔Kandidat); M3-S3 (Extra-Datei da); M3-S4 (eigene Docs harmlos); M3-S5 (Delta nicht vergleichbar)
DISPROVEN="Lokaler Fail widerlegt Kandidaten-Green"; "Lokale Docs verfaelschen Code-Aussagen"
MISSING_EVIDENCE=Datierte Primaer-Reports (M3-S2); Scope-Regel-Entscheid
OWNER_PACKET=Scope-Owner: 1 Satz — ist `test_integration_contract.py` Scope (dann SCOPE_OK=YES revidieren) oder nicht (dann aus Changed-Files streichen)?
CRITICAL_PATH=M3-S2/S3 → M9 CORE_FREEZE (Regel-Entscheide, keine Messungen)
NEXT_OWNER=Scope-Owner (Central Writer / Gate-Owner)
DO_NOT_REPEAT=diff --check selbst laufen lassen; Fingerprints ohne Ausfuehrung behaupten; 65-96-Cascade-Prompts
STATUS=DONE_STATIC

## FOLLOW_UP (2026-09-28, Selbst-Widerlegung)
ROLE=M3
SURVIVING_CONFIRMED=M3-S1 (verstaerkt: Mutation beobachtet); M3-S2; M3-S3; M3-S4
REMOVED=M3-S5 (in S1 gefaltet)
MINIMUM_NEXT_ACTION=SHA-Pin + Freeze-Regel vor jeder Evidenz (neu, → M9-7); Scope-Satz einholen
MINIMUM_TEST_OR_EVIDENCE=Datierte Primaer-Reports; `git status` durch Shell-faehiges Fenster
NEXT_OWNER=Scope-/Gate-Owner
STATUS=DONE_STATIC
