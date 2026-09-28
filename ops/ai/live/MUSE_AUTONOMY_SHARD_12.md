# MUSE Autonomy Shard 12 — Session Budget Ledger

SHARD=12
STATUS=SHARD_COMPLETE
OWNER=MUSE/blooming-albedo / HOST=MAC / DATE=2026-09-28
MODE=READ_ONLY_C2. 0 source edits, 0 runs, 0 ledger touches, 0 PRE_CODEX-Re-Validierung.
REUSED: E17 cost-routing-Finding (zitiert, nicht re-validiert: teure Claims koennen null routen).

## Subcases (4, alle Source-gegroundet)

- S12-1 Kein Reservierungs-Ledger vorhanden → DISPROVEN (Race-Klasse). Bounded search: kein SESSION_BUDGET/COST_LEDGER/reserve-Primitiv in scripts/server/app; CostGate.evaluate_spend_request (scripts/resource_policy.py:102-146) ist reine stateless Funktion ohne Mutation — keine atomare Reservation, also keine Crash-/Retry-/Concurrency-Fenster auf dieser Schicht.
- S12-2 CostGate deny-by-default ohne Aufrufer → CONFIRMED_SOURCE_DEFECT (dead gate). Policy: estimated_cost>0 oder upgrade/purchase → allowed=False + requires_human_gate=True (resource_policy.py:132-139). Aber exakt 0 Aufrufer in scripts/server/app (bounded search nur Def-Zeile :103). Ausgaben-/Human-Gate-Policy wird zur Laufzeit nirgends erzwungen; unauthorized_resources/spend_allowed=False (:61-63) gleiche Klasse. FIX_PACKET unten.
- S12-3 cost_class-Routing ist zustandslose Praeferenz → DISPROVEN (stale-Reservation). claim_task recomputet pro Claim (server/app.py:314-344): teurer Worker wird abgelehnt wenn billigerer qualifizierter + verfuegbarer + lebendiger (300s, :324) Worker existiert; Default cost_class="high" (:240,:317 — unbekannt zahlt teuer = fail-closed-Richtung). Kein Reservierungszustand → kein Crash-Fenster.
- S12-4 Iterations-Budget existiert als Count-Cap → Fakt + MISSING_EVIDENCE. max_autonomous_iterations_per_task=1 (resource_policy.py:72, Getter :84-90), uebernommen in run_autonomous_loop.py:105 (max_iterations). MISSING_EVIDENCE exakt: Anrechnung von max_iterations ueber Prozess-Restarts hinweg (Instanz-lokal?) — ein Subcase-Read in run_autonomous_loop Restart-Pfad.

## Fix-Packet (aus S12-2)

FILES=scripts/resource_policy.py; server/app.py (claim_task/dispatch call site)
CAUSAL_BUG=CostGate.evaluate_spend_request definiert aber 0 Aufrufer — Spend-/Human-Gate-Policy ohne Enforcement-Pfad.
MIN_FIX=Gate-Call in claim_task/dispatch (deny bei allowed=False) ODER Gate loeschen + Nicht-Enforcement dokumentieren.
TARGETED_TEST=neu: Claim mit estimated_cost>0 → declined; Nachbar: cost-routing-Tests.
OWNER=CENTRAL_WRITER (resource lane)
LATER (kein Spend-Mechanismus in Source auffindbar; reine Defense-Härtung; RUN_1/mac-Pfad unberuehrt)

SUBCASES_DONE=4
CONFIRMED_SOURCE_DEFECTS=1 (S12-2 dead cost gate)
EVIDENCE_GAPS=1 (S12-4 restart-Anrechnung)
DISPROVEN=2 (S12-1 reservation races; S12-3 stale routing reservation)
FIX_PACKETS=1 (S12-2, LATER)
NEXT_OWNER=CENTRAL_WRITER
DO_NOT_REPEAT=sha256-muse-shard-12-budget-01
