# COURIER SYMPHONY × GROKBOARD — ORCHESTRATOR INTEGRATION V1

Status: Architekturentwurf + First Implementable Slice (Mock-Adapter, keine Live-Claims).
Basis: `origin/integration/v1`. Code: `courier_orchestrator/`, Tests: `tests/orchestrator/`.

**Grundsatz:** Courier ist die Control Plane. Spezialisierte Courier-Groks sind Worker.
*Many eyes, one pen:* Worker lesen, arbeiten, liefern ein Result. Nur der Hubwriter schreibt.

## Bestandsaufnahme (worauf aufgebaut wird, nichts wird doppelt gebaut)

| Vorhanden | Rolle im Orchestrator |
|---|---|
| `courier_core/controller.py` | Bereits einziger Writer des Journals (hash chain, RESULT_ACCEPTED/REJECTED mit Verifier-Attribution, BLOCKED wartet auf Menschen). **Der Hubwriter ist die Goal-Ebene dieses Prinzips**, in V1-Produktion schreibt er über den Controller, nicht daneben. |
| `courier_core/goal_contract.py` (`GoalContract`) | Menschlich bestätigter Anker: allowed/forbidden scope, acceptance criteria, gates, `validate_task()`. `Goal` im Orchestrator referenziert einen GoalContract-Fingerprint; Tasks werden über `validate_task()` geprüft. |
| `courier_core/work_queue.py` (#296) | Ledger-basierte Queue (READY/CLAIMED/DONE/BLOCKED, claim/renew/release mit TTL). Wird die **Queue** des Hubs. |
| `courier_worker/ledger_tick.py` + `scripts/ledger_v1_bridge.py` | Event-getriebene Fortsetzung: Tick nur bei Leerlauf, einmaliger Bridge-Pass, idempotent. Draft-PR #536 verbindet WorkQueue und LedgerTick. Das ist der **Fortsetzungsmechanismus ohne Polling**. |
| Gates G0–G5 | G0 Daten schützen, G1 Ledger, G2 Motor, G3 Zero-Human A→B, G4 Restart ohne Replay, G5 realer Pilot. Der Orchestrator ist G3-Arbeit und setzt G1/G2 voraus. |

Nicht angefasst: `server/app.py`, Ralph, `.github/workflows`.

## A — Architektur

```
Mensch ──(Goal + Human Gates)──▶ COURIER HUB ◀──── Grokboard (Goal-Ebene)
                                   │  goal_id, project_id, budget, deadline,
                                   │  authorization, queue (WorkQueue), status,
                                   │  worker registry, result registry
              ┌────────────────────┼─────────────────────┐
              ▼                    ▼                     ▼
          ROUTER  ──▶  COST GOVERNOR          COURIER BRAIN (providerneutral,
              │                                exportierbar, nur via Hubwriter)
              ▼
  Worker (Courier Grok, Umsatz, Produkt, Integration, Website, Prüfer,
          Katalog, Tests, Datenrettung, Wand-Aufsicht, Vogel)
              │ Result (read-only gegenüber Hub/Brain)
              ▼
  UNABHÄNGIGER PRÜFER ──▶ HUBWRITER (genau einer) ──▶ Delta ──▶ nächster Task
```

- **Courier Hub**: Zustand pro Goal; Queue = WorkQueue; Registries als Projektion aus dem Journal.
- **Courier Brain**: dauerhafter, providerneutraler Kontext (Markdown/JSON, keine Provider-IDs als Schlüssel). Schreibend nur über Hubwriter-Deltas.
- **Hubwriter**: genau ein kanonischer Writer (SINGLE_WRITER), schreibt nur verifizierte Deltas.
- **Router / Cost Governor**: wählt Worker nach Fähigkeit und Preis, nicht nach Marke.
- **Fortsetzung**: jedes akzeptierte Delta ist das Ereignis, das den nächsten READY-Task freigibt (LedgerTick/Bridge). Kein Polling, keine Leerlauf-Quota.
- **Digitale Souveränität**: Goal, Tasks, Results, Evidence, Brain und Artifacts sind JSONL/JSON/Dateien und vollständig exportierbar (`courier export --goal <id>` als Folgearbeit).

## B — Datenmodelle (`courier_orchestrator/models.py`)

- `Goal`: goal_id, project_id, title, budget_eur, deadline, authorization (vorab freigegebene Gates), status (WORKING/NEEDS_YOU/DONE/FAILED), spent_eur.
- `Task`: task_id, goal_id, capability, scope, expected_output, acceptance_criteria, cost_limit_eur, actions (deklarierte Außenwirkungen), depends_on, status, attempts, assigned_worker.
- `WorkerContract`: siehe C.
- `Result`: task_id, goal_id, attempt, worker_id, output, requested_scope, cost_eur, evidence, self_verdict (nur informativ).
- `Verification`: task_id, attempt, verifier_id, verdict, reasons, cost_eur.
- `Delta`: seq, goal_id, task_id, writer, verifier_id, payload.
- `WorkerProfile` (Registry): capabilities, cost, latency, available, owns_scope, risk, verified/rejected → verification_quality.

## C — Worker Contract

Felder: `task_id, goal_id, worker_role, required_context, allowed_scope, forbidden_actions, expected_output, acceptance_criteria, cost_limit`.
Regeln:
1. Der Contract wird vom Hub ausgestellt und ist unveränderlich (`frozen`).
2. Ein Worker darf seine Rechte nicht selbst erweitern: `requested_scope ⊄ allowed_scope` ⇒ Prüfer FAIL und Hubwriter `SCOPE_ESCALATION` (auch bei gefälschtem PASS).
3. Standard-`forbidden_actions`: deploy, force_push, delete, edit:server/app.py, edit:.github/workflows, self_grant_scope.
4. Worker schreiben weder Hub noch Brain; sie liefern nur ein Result.

## D — Hubwriter Contract

Der Hubwriter schreibt ein Delta genau dann, wenn:
- eine Verification existiert (sonst `RESULT_RECEIVED_NOT_VERIFIED`),
- der Verifier weder der Worker noch der Hubwriter selbst ist (sonst `SELF_PASS_NOT_ACCEPTANCE`),
- Verification und Result sich auf dieselbe task_id/attempt beziehen,
- verdict == PASS,
- der Scope eingehalten ist.
Deltas sind append-only, nummeriert und tragen den verifier_id. In Produktion: Delta = Controller-Event `RESULT_ACCEPTED` (der Controller bleibt einziger Journal-Writer).

## E — Routing Contract

Kandidaten: verfügbar, besitzt die capability, Kosten ≤ cost_limit und ≤ Restbudget.
Sortierung: (1) Kosten — billigste ausreichende Fähigkeit zuerst, (2) Verifikationsqualität, (3) Risiko, (4) Scope Ownership, (5) Latenz. Markennamen sind kein Kriterium; der „Chef“ (Courier Grok) gewinnt nur, wenn er billiger/besser ist. Ein abgelehnter Versuch senkt die Verifikationsqualität. Cost Governor: verbucht jede reale Ausgabe (Worker + Prüfer) und misst `VERIFIED_USEFUL_RESULTS_PER_REAL_EURO`. Budget erschöpft ⇒ fail closed.

## F — Result Contract

Pipeline: `Task → Attempt → Execution → Result → Verification → Accepted → Hubwriter Delta → nächster Task`.
- RESULT_RECEIVED ist nicht VERIFIED; VERIFIED ist nicht ACCEPTED (Accepted erst mit Delta).
- `self_verdict` des Workers zählt nie.
- Jedes Result trägt Evidence; ohne Evidence FAIL.
- Max. 2 Attempts pro Task, dann FAILED oder BLOCKED (Mensch).

## G — Minimale UI-Änderungen (Grokboard)

Nur eine **Goal-Ebene über der bestehenden Worker-Ansicht**, keine neue App:
```
[ GOAL G-DEMO-1 ]  WORKING | NEEDS YOU | DONE
Budget 2,00 € · verbraucht 0,26 € · Workers 2 · Running 0 · Waiting 0
Verified Results 3 · Next Action: none
```
Datenquelle: `hub.board()` (JSON). Klick auf Goal öffnet die vorhandene Worker-Ansicht gefiltert nach goal_id. NEEDS YOU zeigt genau das auslösende Gate.

## H — 7-Tage-MVP-Plan

| Tag | Inhalt |
|---|---|
| 1 | Datenmodelle + Contracts mergen (dieser PR), Review durch Dennis |
| 2 | Hubwriter → Controller-Event `RESULT_ACCEPTED` adaptieren (kein zweiter Writer) |
| 3 | Queue auf WorkQueue (#296) umstellen, Fortsetzung über LedgerTick (#536) |
| 4 | Goal ↔ GoalContract-Fingerprint, `validate_task()` vor Dispatch |
| 5 | Grokboard Goal-Karte (read-only JSON) |
| 6 | Export (Goal, Tasks, Results, Evidence, Brain) + Kostenmessung im Board |
| 7 | End-to-end mit 3 Workern, 1 Goal, Restart ohne Replay (G4); Report |

MVP-Kriterien: ein Goal, 3 Worker, automatische Verteilung, strukturierte Results, unabhängiger Prüfer, Hubwriter-Update, nächster Task automatisch, kein Copy/Paste, Kostenmessung, finaler Goal-Status. Alles mit Mock-Adaptern, keine Fake-Live-Claims.

## I — First Implementable Slice (in diesem PR umgesetzt)

`courier_orchestrator/`: `models.py`, `workers.py` (Registry, 3 Mock-Worker, MockPruefer), `router.py` (Router + CostGovernor), `hub.py` (Hubwriter, Human Gates, Board), `engine.py` (event-getriebene Schleife), `demo.py`; plus `mission.py` (Einstein-Layer-Experiment, siehe `COURIER_EINSTEIN_LAYER.md`).
Lauf: `python3 -m courier_orchestrator.demo` → Goal DONE, 3 verifizierte Results, 0,26 € (Mock), ein abgelehnter Versuch (Website, NOT_VERIFIED) mit automatischem Retry.
Tests (`tests/orchestrator/`): eigenes PASS abgelehnt, RESULT_RECEIVED≠VERIFIED, Human Gate stoppt, unbekannter Effekt gegated, Rechteerweiterung abgelehnt, Router billigst statt Marke, Budget fail-closed, End-to-end.

## J — Risiken und Human Gates

Human Gates (stoppen immer, Goal → NEEDS YOU): payment, purchase, subscription, OAuth, publication, destruktive Aktionen, legal commitment, scope escalation, unbekannter externer Effekt (jede nicht klassifizierte Aktion). Freigabe nur per `Goal.authorization`, vom Menschen gesetzt.

Risiken:
1. **Zweiter Writer**: Hubwriter neben Controller würde SINGLE_WRITER brechen ⇒ Hubwriter muss über Controller schreiben (Tag 2).
2. **Prüfer-Kollusion**: gleicher Provider als Worker und Prüfer ⇒ Verifier-Identität muss Runtime-Identität enthalten.
3. **Kostenmessung nur Mock**: reale Euro erst mit echten Adaptern (G5).
4. **Kontextdrift im Brain** ⇒ Brain-Änderungen nur als verifizierte Deltas.
5. **Quota-Verschwendung** ⇒ nur Ereignis-Fortsetzung, keine Poll-Loops.

COURIER_GROKBOARD_V1_READY_TO_BUILD=YES
FIRST_IMPLEMENTABLE_SLICE=courier_orchestrator (Goal/Task/WorkerContract/Result, Hubwriter nur nach unabhängiger Verifikation, Router+CostGovernor, 3 Mock-Worker, MockPruefer, Demo end-to-end mit Kostenmessung)
FIRST_BLOCKER=Hubwriter muss als Controller-Event RESULT_ACCEPTED schreiben statt eigenem Journal, und PR #536 (WorkQueue↔LedgerTick) muss gemergt sein, damit die Fortsetzung real und nicht nur in-process läuft
