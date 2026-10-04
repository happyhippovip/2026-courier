# User Acceptance A — Status / Phase (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Proof references below are static reads from this window (shell down, no live process/port evidence).

## USER_PROBLEM

Als normaler Nutzer sehe ich nicht:
was macht Courier gerade, in welcher Phase ist es, ist es aktiv oder idle,
und für welchen Candidate gilt das alles?

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- `ops/ai/GATE_STATE_CURRENT.md`: PRE_CODEX_STATE=VALIDATED_LOCAL_GREEN,
  CURRENT_CANDIDATE_SHA=3c2aa516..., LOCAL_VERIFICATION_STATUS=PASS
  (57 passed, 1 skipped mac-only, 0 failed), NEXT_ACTION=AWAIT_MAC_CANARY.
- `ops/ai/WALL_QUEUE_CURRENT.md`: TRUE_IDLE, 100% exhausted / verified green,
  awaiting Mac physical canary.
- `server/app.py` `/status` liefert nur Zähler
  (goals / active_goals / tasks / workers) — keine Phase, kein Fortschritt,
  kein Next, kein Candidate-Bezug.
- `server/app.py` `/health` liefert nur `healthy` + Zeitstempel.
- `server/state/central_state.json` (live store, Platte) enthält u. a.
  DONE-Goal `goal-fc9e8d59` und ACTIVE-Goal `goal-7751ca47` mit DISPATCHED-Step.
- Liveness (läuft Server/Worker auf :8080 hier und jetzt?) ist aus diesem
  Fenster UNPROVEN (kein Shell-Zugriff, keine Prozess-/Port-Evidenz).
- Befund: `ops/ai/GATE_STATE_CURRENT.md` ist per Standard-UTF-8-Read nicht
  lesbar (read schlug fehl, Inhalt nur via Text-Suche extrahierbar) —
  maschinell schwer konsumierbar, z. B. für Status-Tooling.

## ACCEPTANCE_REQUIREMENT

- A1: Genau eine Statuszeile ist jederzeit ablesbar:
  PHASE + STATE + CANDIDATE_SHA(kurz) + NEXT. Kein zweiter Statuskanal
  darf widersprechen.
- A2: Festes Phasen-Vokabular (aus Run-Prep/Pilot-Docs abgeleitet):
  PREP / AWAIT_MAC_CANARY / RUN_1 / RUN_2 / PILOT / IDLE / BLOCKED.
  Freitext-Phasen sind unzulässig.
- A3: STATE ∈ {ACTIVE, IDLE, BLOCKED, UNKNOWN} wird aus belegter
  Evidenz abgeleitet, nicht aus Annahmen. Ohne Liveness-Evidenz heißt
  der Zustand UNKNOWN, nicht IDLE.
- A4: Jede Statusanzeige nennt den Candidate-SHA, für den sie gilt.
  Status ohne SHA-Bindung ist ungültig.
- A5: Der Gate-Status liegt zusätzlich maschinenlesbar als UTF-8-JSON vor
  (Schema siehe unten), damit Tooling ihn ohne Raten parsen kann.

## MISSING_SYSTEM_SUPPORT

- Kein Runtime-Status-Aggregator (Phase + State + Next aus State + Gate-Files).
- Kein UTF-8 maschinenlesbares Gate-State-File (aktuell nur Markdown,
  dazu encodierungsauffällig).
- Keine aus diesem Fenster abrufbare Liveness-Evidenz (Prozess/Port/Heartbeat).

## PREPARABLE_NOW (ohne Shell-Freischaltung, ohne Product Shell)

- Dieses Dokument (Vokabular + Regeln A1–A5).
- Vorgeschlagenes Schema `ops/ai/USER_STATUS_SCHEMA.json` (später anlegen):
  Felder: phase, state, candidate_sha, active_goal_id, active_task_id,
  worker_count, last_progress_evidence_ref, next_action, observed_at,
  observer (host/user), proof_level.
- Regel: Status-JSON wird nur aus gelesener Evidenz erzeugt; fehlende
  Felder heißen explizit UNKNOWN, nie leer oder geraten.

## BLOCKED_UNTIL

- Liveness-Regel (A3) braucht einen physischen Runner, der Prozess/Port/
  Heartbeat belegen kann (Mac-Canary-Umgebung).
- Kein Bau einer Status-UI / Product Shell vor positivem Pilot-Signal.

## NEXT

B (Braucht-dich): was wartet auf den Nutzer — explizite Needs-You-Liste.
