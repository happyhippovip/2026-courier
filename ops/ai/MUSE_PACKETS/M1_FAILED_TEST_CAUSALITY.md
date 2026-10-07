# M1 — FAILED_TEST_CAUSALITY (Muse 1)

Stand: 2026-09-28. Statische Ursachenanalyse aus Repo-Reads.
NICHT-Scope: keine Test-Re-Runs, keine Gate-Revalidierung, kein RUN, kein Ledger.
Ein Re-Run aendert kein Urteil — nur Ursachen belegen.

## Befund-Tabelle (jede Zeile: Symptom → Ursache → Klasse)

F1. `git diff --check` FAILED (40x trailing whitespace + 1 blank line at EOF,
`PRE_CODEX_HANDOFF.md:35-38`)
→ Ursache: Whitespace in den geaenderten Dateien, kein Test-Code-Fehler.
→ Klasse: FORMAL (Gate-Item 7 verlangt clean) — kein kausaler P0
(Handoff selbst: 0 offene kausale P0).

F2. `SCOPE_OK=NO` (`SCOPE_CHECK_EVIDENCE.md:24`)
→ Ursache: Ist-Delta enthaelt `tests/test_integration_contract.py`, Soll-Liste
(`GOOGLE_PRE_CODEX_GATE_2026-09-27.md:15-20`) kennt nur 5 Dateien.
→ Klasse: SCOPE_DRIFT (Liste vs. Delta), kein Laufzeitfehler.

F3. Zaehlen-Drift 57 vs 51 (`GATE_STATE_CURRENT.md:10` vs `PRE_CODEX_HANDOFF.md:30`)
→ Ursache: unterschiedliche Suite-Mengen. GATE summiert 4 Dateien
(14+29+11+3=57, `test_result_identity_binding.py` inklusive). Die
51-Zusammensetzung des Handoffs ist aus Reads nicht rekonstruierbar — OFFEN.
→ Klasse: REPORTING (zwei Quellen, eine Wahrheit fehlt).

F4. `check_pilot_readiness.py` wuerde HEUTE mit FAILED enden
→ Ursache: `ops/ai/PILOT_DUMMY_TASK.json` existiert nicht (nur referenziert in
`PILOT_READINESS_DECLARATION.md:16`, dort als "passes verification" behauptet).
→ Klasse: OVERCLAIM (Deklaration vs. Dateisystem).

F5. Beacon wirkungslos (`scripts/courier_beacon.py` vs `server/app.py`-Routen)
→ Ursache: ruft `/system/metrics` + `/system/halt`, die der Server nicht anbietet.
→ Klasse: DRIFT (Client/Server auseinander).

## Kausal-Regel (fuer alle Fenster)
Jeder rote Befund bekommt: `SYMPTOM | URSACHE (Datei:Zeile) |
KLASSE (FORMAL/SCOPE_DRIFT/REPORTING/OVERCLAIM/DRIFT/CAUSAL_P0)`.
Nur `CAUSAL_P0` blockiert kausal; der Rest blockiert formal bzw. per Regel —
beides sichtbar, aber getrennt.

## ACCEPTANCE / REQUIREMENT
- M1.1: F1–F5 sind die VOLLSTAENDIGE statische Fail-Liste dieses Fensters;
  neue Funde ergaenzen die Tabelle, ersetzen sie nicht.
- M1.2: F3-OFFEN (51-Komposition) wird genau EINEM Owner zur Klaerung gegeben
  (Lesen der genannten Result-Dateien — kein Re-Run).
- M1.3: Kein Fenster darf F1/F2/F4/F5 durch Re-Runs "heilen"; Heilung = Datei fixen
  (Whitespace/Scope/Dummy/Doku) bzw. Spec-Entscheid.

## BLOCKED_UNTIL
- F3-Komposition: bis ein Owner die Handoff-Quelldateien nennt.
- Echte Kausal-P0-Suche: bis physische RUN-Evidenz existiert (nicht hier).

## NEXT
M2 (Skipped-Gueltigkeit) → M3 (False-Green-Muster).
