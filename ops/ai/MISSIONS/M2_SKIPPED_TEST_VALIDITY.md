# M2 — SKIPPED_TEST_VALIDITY (Muse 2)

Stand: 2026-09-28. Prep-only: statische Analyse, kein RUN, kein Ledger.

## OBJECTIVE
Jeden SKIP auf Gueltigkeit pruefen: Ist der Skip-Grund belegt, eng begrenzt
und zeitlich befristet — oder versteckt er einen echten Gap?

## ANCHORS (belegt)
- `GATE_STATE_CURRENT.md`: `1_SKIPPED_MAC_ONLY` (darwin-only auf Windows).
- `PRE_CODEX_HANDOFF.md`: `SKIPPED_COUNT=0` (UA-A01) — Widerspruch zu GATE_STATE,
  unterschiedliche Suites, nirgends gekennzeichnet.
- Konvention aus Repo-Historie: nur enge, begruendete Skips sind legitim.

## SCOPE (read-only)
`ops/ai/GATE_STATE_CURRENT.md`, `ops/ai/PRE_CODEX_HANDOFF.md`, `tests/*.py`
(nur Skip-Dekoratoren/Bedingungen lesen, nicht ausfuehren).

## METHOD
Statisch: jeden Skip finden, Grund lesen, bewerten nach
`BEGRUENDET (ja/nein) | ENG (ja/nein) | BEFRISTET (ja/nein)`.
57/1-vs-51/0-Differenz aufklaeren (welche Suites, warum verschieden).

## OUTPUT
Tabelle `TEST | SKIP_GRUND | BEGRUENDET | ENG | BEFRISTET | VERDICT`.
Verdict: `ALL_SKIPS_VALID: YES|NO` + Aufklaerung der 57/1-vs-51/0-Differenz.

## BLOCKED_UNTIL
Echter Collect-Run (fremdes Fenster) fuer die vollstaendige Skip-Liste —
statisch Gefundenes ist `STATIC_SEEN`, Vollstaendigkeit bleibt `UNPROVEN`.

## DONE_WHEN
Jeder statisch sichtbare Skip ist bewertet; die Zaehlen-Differenz ist
erklaert oder als UNDECIDED_STATIC markiert.
