# Architecture Choice Record (ENTWURF) — eine Workkey-Claim-Wahrheit
**Status:** PROPOSAL_ONLY · nicht aktiviert · Entscheidung: Dennis / L1 · Basis `integration/v1` `d5b19f1df` · Autor: Claude Opus (Autor von #830 — Interessenkonflikt offen benannt)

## Kontext
Ausführungs- und FINAL-Wahrheit ist das Controller-Journal (`courier_core/controller.py`, Zustandsmaschine im Append, `RESULT_ACCEPTED` nur vom Verifier). Davor gibt es heute vier unabhängige Speicher, die *Workkeys* beanspruchen.

## Ist-Stand (VERIFIED im Code, aktive Aufrufer ohne Tests/Doku)
| Speicher | Aktive Aufrufer | Schreibweg / Lock | Bezug zum Journal | Doppel-Claim-Risiko |
|---|---|---|---|---|
| **`courier_core/work_queue.py`** („Canonical ledger-backed work queue“, PR #296) | `courier_worker/queue_feed.py` ← `courier_worker/ledger_tick.py` ← `courier_worker/service.py` (Worker-Dienst) | JSONL-Ledger, Append unter `_lock()` (fcntl/msvcrt), Leases mit Ablauf | **angebunden:** `feed_once` vergibt Mission an Bridge → Controller; Freigabe nur bei Bridge-`FINAL_DONE`, das nur nach verifiziertem `RESULT_ACCEPTED` gestempelt wird | **WQ-1 (VERIFIED):** gleicher Holder nach Ablauf → sicher; **zwei Homes mit gemeinsamer Queue → zweiter Holder übernimmt den abgelaufenen Workkey und weist die Mission in seiner Koordinationsdatei erneut zu** → neuer Bridge-Schlüssel `ledger:<claim_event_id>` → zweiter Controller-Task. `_effective` löscht den alten Holder beim Ablauf. Fix-Vorschlag `WQ-1_foreign_expired_lease.diff` |
| **Kirby** `courier_runtime/continuity.py` (`kirby.json`) | `courier_runtime/host_loop.py` (CLI), `provider_events.py`, `visual_language.py`; **kein produktiver Runner** (C48-Treiber nicht gebaut); PR #830 `ledger_engine.py` | JSON-Datei, kein Lock (#830 ergänzt Lock nur für Engine-Zugriffe) | **nicht angebunden:** DONE auf Provider-Zuruf (F-K1); #830 bindet DONE an Journalbeweis | hoch ohne #830-Lock (F-K2, reproduziert) |
| `scripts/verified_continuation.py` („Verified Continuation Engine“, Google) | keine Code-Aufrufer außerhalb von Tests | O_EXCL-Claim-Dateien | eigener CLAIM→…→NEXT-Zyklus, kein Journal | **Sicherheitsgate:** übernimmt eine abgelaufene Claim-Datei ohne Effekt-Abgleich → mögliche Doppelausführung |
| `scripts/local_swarm_claim.py` (`.courier_swarm/claims`) | `scripts/coordination_ledger.py` (Doku-Verweis) | Dateien, eigener Taskbank-JSON | keiner | Legacy, unklar |

## Entscheidung (Vorschlag)
1. **Eine Workkey-Claim-Wahrheit = `courier_core/work_queue.py`.** Begründung: bereits als kanonisch angelegt, mit Lock und Leases, und als einziger Speicher produktiv an Bridge→Controller angebunden; Freigabe nur nach verifiziertem FINAL.
2. **Kirby = nur Provider-Sitzungsfortsetzung** (Wake-Koaleszenz, Rotation, Recovery-Fence) **ohne eigene Claim-Autorität.** Seine `workkey`-Zuordnung wird aus dem `work_queue`-Holder abgeleitet (Projektion), nicht unabhängig vergeben.
3. **`verified_continuation.py` und `local_swarm_claim.py`: einfrieren** (keine neuen Funktionen, kein autonomer Einsatz). `verified_continuation` bleibt bis zur Behebung des Ablauf-Übernahme-Fehlers **BLOCKED** für autonome Läufe.
4. **Kostensperre zentral im Controller** (F-C1-Patch, `cost_blocked` vor `TASK_CREATED`) — gilt für jeden Pfad, auch Bridge und `queue_feed`.

## Folgen
| Bereich | Folge |
|---|---|
| **PR #830 (eigene Arbeit)** | Baut auf Kirby als Claim-Speicher → widerspricht Punkt 2. Empfehlung: **#830 nicht als Dispatcher mergen.** Seine Kostensperre wird durch F-C1 zentral ersetzt; der beweisgebundene Abschluss existiert auf dem kanonischen Pfad bereits (Freigabe nur bei `FINAL_DONE`). Verwertbar bleiben das Lock-Muster und der Fremd-Task-Check als Härtung für Kirby-Projektion oder `queue_feed` — als kleiner Folge-PR, nicht als zweiter Motor. #830 bleibt Draft bis zur Entscheidung. |
| F-K1/F-K2-Vorschlag (Host-Loop) | weiterhin richtig (Provider-DONE ist kein Beweis); setzt aber nicht mehr #830 voraus, wenn Kirby keine Claim-Autorität hat — DONE wird dann nur noch aus dem `work_queue`-Freigabezustand gespiegelt. |
| Migration | keine Datenmigration nötig: `work_queue` ist bereits führend; Kirby-Zustand ist ersetzbar (Projektion). Bestehende Tests von `verified_continuation`/`local_swarm_claim` bleiben, Code wird nur eingefroren. |
| Lease-Ablauf (geklärt, WQ-1) | Vor Stufe 2 / Cross-Host-Queue: Fix `WQ-1_foreign_expired_lease.diff` anwenden — `_effective` behält `expired_lease`, `feed_once` übernimmt keinen fremden abgelaufenen Lease (meldet `foreign_expired`), der ursprüngliche Holder kann fortsetzen. Rot→grün belegt, 82 Queue/Feed/LedgerTick-Tests inkl. `test_gate2_two_workkeys` grün. Owner: work_queue/queue_feed (L1/L3). |

## Nicht Teil dieses Entwurfs
Keine Aktivierung, keine Queue-Migration, kein Merge, keine Änderung an fremden Dateien.
