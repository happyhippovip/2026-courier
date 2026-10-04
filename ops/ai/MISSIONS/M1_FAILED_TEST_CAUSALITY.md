# M1 — FAILED_TEST_CAUSALITY (Muse 1)

Stand: 2026-09-28. Prep-only: statische Analyse, kein RUN, kein Ledger.

## OBJECTIVE
Fuer jeden als FAILED berichteten Test die Kausalkette bestimmen:
`FAILURE -> direkte Ursache (Code/Test/Umgebung) -> Belegstelle`.
Kein FAILED ohne benannte Ursache stehen lassen.

## ANCHORS (belegt)
- `GATE_STATE_CURRENT.md`: `0_FAILED` behauptet (Targeted-Suites).
- `SCOPE_CHECK_EVIDENCE.md`: `SCOPE_OK=NO` (UA-A01) — Scope-Fail neben READY.
- `diff --check` = FAILED, 40x Whitespace (UA-A01).

## SCOPE (read-only)
`ops/ai/GATE_STATE_CURRENT.md`, `ops/ai/PRE_CODEX_HANDOFF.md`,
`ops/ai/SCOPE_CHECK_EVIDENCE.md`, `tests/*.py` (nur lesen).

## METHOD
Statisch: Behauptungen gegen Dateien pruefen, jeden FAIL/NO-Flag auf genau
eine Ursache zurueckfuehren (Code-Fehler vs. Test-Fehler vs. Scope-Drift vs.
Umgebung). Keine Tests ausfuehren.

## OUTPUT
Tabelle `FLAG | ORT | URSACHE | BELEG | FOLGE (blockt was?)`.
Verdict: `ALL_FAILURES_EXPLAINED: YES|NO`.

## BLOCKED_UNTIL
Echter Test-Run (fremdes Fenster) fuer alles, was statisch nicht entscheidbar
ist — als `UNDECIDED_STATIC` markieren, nicht raten.

## DONE_WHEN
Jedes NO/FAILED-Flag hat eine Ursachen-Zeile oder ist als UNDECIDED_STATIC
markiert. Kein neues FAILED erfunden, keines wegdefiniert.
