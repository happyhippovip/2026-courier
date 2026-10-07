# UA-A01 — Ein verbindlicher Status: Was macht Courier gerade, ist es aktiv?

Prioritaet: A (aktueller Status / Phase)
Stand: 2026-09-28, Quelle: Repo-Reads (kein RUN, kein Ledger, keine Revalidierung)

## USER_PROBLEM
Als Nutzer sehe ich gleichzeitig: `PRE_CODEX ... GREEN`, `AUTHORITATIVE_READY=YES`,
`TRUE_IDLE`, `PILOT READY (PENDING AUTHORIZATION)`, `Proof Level: SYNTHETIC_PRE_CODEX`,
`Product Shell LOCKED`. Ich kann nicht sagen, ob Courier gerade arbeitet, fertig ist
oder auf etwas wartet — und welche dieser Aussagen gilt.

## CURRENT_RUNTIME_TRUTH (belegt)
- `ops/ai/GATE_STATE_CURRENT.md`: `PRE_CODEX_STATE=VALIDATED_LOCAL_GREEN`,
  `TARGETED_TESTS_RESULT=57_PASSED__1_SKIPPED_MAC_ONLY__0_FAILED`,
  `NEXT_ACTION: AWAIT_MAC_CANARY`, `AUTHORITATIVE_READY=YES`.
- `ops/ai/WALL_QUEUE_CURRENT.md`: `TRUE_IDLE`, wartet auf Mac-Canary.
- `ops/ai/PRE_CODEX_HANDOFF.md`: 51 Assertions GREEN, `SKIPPED_COUNT=0`.
  Widerspruch zu GATE_STATE (57/1): unterschiedliche Suites, nirgends als solche
  gekennzeichnet.
- `ops/ai/SCOPE_CHECK_EVIDENCE.md`: `SCOPE_OK=NO` (Extra-Datei
  `tests/test_integration_contract.py`).
- `ops/ai/PRE_CODEX_HANDOFF.md`: `git diff --check` = FAILED (40x Whitespace).
- `ops/ai/PROOF_CARD.md`: `Proof Level SYNTHETIC_PRE_CODEX`, physischer RUN `[PENDING]`.
- Echter Prozess-/Port-Nachweis liegt nicht vor (kein laufender Server beobachtet).

## ACCEPTANCE_REQUIREMENT
UA-A01.1: Genau EINE Statusdatei (oder EIN Endpoint-Feld) beantwortet:
`PHASE | STATE (WORKING/IDLE/WAITING/BLOCKED) | PROOF_LEVEL | NEXT_OWNER | NEXT_ACTION`.
UA-A01.2: Jede Statusaussage zitiert ihre Evidenz (Datei + SHA + Datum).
UA-A01.3: Widerspruechliche Zaehlen (57/1 vs 51/0) duerfen nicht nebeneinander als
jeweils "GREEN" stehen; die gueltige Suite-Menge ist benannt.
UA-A01.4: `READY`-Woerter sind pro Gate qualifiziert (`PRE_CODEX_LOCAL_READY`
vs `CROSS_HOST_READY` vs `PILOT_READY`), nie nackt.

## MISSING_SYSTEM_SUPPORT
- Kein einzelner Statusgeber: `/status` (`server/app.py:83`) liefert nur Zaehler
  (goals/active/tasks/workers), keine Phase, kein Proof-Level, kein NEXT.
- `scripts/courier_beacon.py` ruft `/system/metrics` + `/system/halt`, die es in
  `server/app.py` nicht gibt (Routenliste geprueft) → Beacon ist heute blind.
- Kein Feld `STATE`/`NEXT_OWNER` in `server/state/central_state.json`.

## PREPARABLE_NOW (ohne RUN, ohne Ledger)
- Dieses Dokument + Status-Schema-Entwurf (Felder, kein Code).
- Manuelle Statuszeile in `ops/ai/WALL_QUEUE_CURRENT.md`-Format pflegen.

## BLOCKED_UNTIL
- Echter Prozess-/Port-Check (Shell/Runner) fuer `STATE=WORKING vs IDLE`.
- Mac-Canary-Entscheidung fuer Phasenwechsel.

## NEXT
UA-B01 (Braucht-dich-Liste) — danach UA-E01 (Beacon-Reparatur-Spec).
