# M9 — NEXT_PHASE_CONVERGENCE (Muse 9)

Stand: 2026-09-28. Prep-only: Konvergenz-Spec, kein Phasenwechsel.

## OBJECTIVE
Definieren, wann die naechste Phase beginnen darf: Welche Gates muessen
konvergiert sein, wer stellt den Uebergang fest, und was passiert bei
Dissens zwischen Fenstern/Hosts?

## ANCHORS (belegt)
- Gate-State: `AUTHORITATIVE_READY=YES`, `NEXT: AWAIT_MAC_CANARY`
  (GATE_STATE); Queue: `TRUE_IDLE` (WALL_QUEUE).
- Gate-Maschine: OPEN→REPORTED→DURABILITY_PENDING→VALIDATING→READY→CONSUMED;
  REPORTED ≠ READY (`COST_SAFE_GATE_TRANSITION_POLICY:32-41`); ein
  Validierungs-Owner pro Fingerprint (`:54-60`).
- Kern-Versprechen: "Courier bringt den Nutzer morgen zurueck, wo er
  aufhoerte" (Playbook North Star) — muss VOR Expansion bewiesen sein.
- Tor J: Product Shell bleibt zu bis Pilot-Signal (UA-J01).

## SCOPE (read-only)
Gate-Policy, Gate-State, Wall-Queue, Playbook-Phasen, UA-A01/J01.

## METHOD
Statisch: Uebergangs-Bedingungen als Checkliste formulieren
(Gate-Fingerprint + Evidenz + Owner + Dissens-Regel); pruefen, ob der
aktuelle Stand sie erfuellt (heute: NEIN — Mac-Canary ausstehend);
Dissens-Fall spezifizieren (zwei Fenster, zwei Meinungen — wer gewinnt?).

## OUTPUT
`NEXT_PHASE: NAME + EINTRITTS_CHECKLISTE (abhakbar) + DISSENS_REGEL`.
Verdict: `READY_TO_ADVANCE: YES|NO` + fehlende Punkte nummeriert.

## BLOCKED_UNTIL
Mac-Canary-Evidenz + menschliche Phasen-Entscheidung (vgl. UA-B01).

## DONE_WHEN
Checkliste ist vollstaendig und heute ehrlich mit NO beantwortet;
kein Aktionismus ("trotzdem weiter").
