# WQ-1b · Sichere Lease-Rückgewinnung ohne Doppelausführung und ohne Dauer-Stillstand (ENTWURF)
Basis `d5b19f1`. Owner: work_queue / queue_feed (L1/L3). Status: DESIGN_ONLY, nichts implementiert.

## Problem nach WQ-1
WQ-1 verhindert, dass ein zweites Home einen abgelaufenen fremden Lease übernimmt (sonst zweiter Controller-Task). Kommt der ursprüngliche Holder nie zurück, bleibt der Workkey aber dauerhaft `foreign_expired`: `WorkQueue.release` verlangt den aktuellen Holder (`NOT_HOLDER`), einen Mensch- oder Abgleichsweg gibt es nicht (VERIFIED, `courier_core/work_queue.py:152-167`, CLI kennt nur `next/claim/renew/release/spawn`).

## Regel (Vorschlag)
Ein abgelaufener **fremder** Lease darf nur übernommen werden, wenn feststeht, dass dafür nichts mehr läuft. Dafür braucht die gemeinsame Queue zu wissen, *welcher* Controller-Task zum Workkey gehört.

1. **ATTACH (neu, work_queue):** Sobald ein Home die Mission an seinen Controller übergeben hat (Bridge-Mapping `posted: true`), schreibt `feed_once` ein Ereignis `ATTACH {item_id, holder, controller_ref, task_id}` in die *gemeinsame* Queue. Keine Secrets, nur IDs.
2. **Übernahme-Entscheidung** für einen Workkey mit `expired_lease` eines fremden Holders:
   | Lage | Entscheidung |
   |---|---|
   | kein ATTACH (nie gepostet) | Übernahme erlaubt — es lief nichts |
   | ATTACH, Abgleich über `GET <controller>/v1/tasks/<task_id>` = `COMPLETE` + `resolution=verified` | keine Neuausführung; Workkey als erledigt freigeben (Beleg = Journal-Task) |
   | ATTACH, Abgleich = `FAILED` oder `CANCELLED` | Übernahme erlaubt (Endzustand, kein offener Effekt) |
   | ATTACH, Abgleich = `BLOCKED` (unsicherer nicht-idempotenter Effekt) | **keine** Übernahme → Mensch entscheidet im Controller (`resolve`) |
   | ATTACH, Task läuft / Controller nicht erreichbar / Antwort unklar | **keine** Übernahme (`foreign_expired`), fail-closed |
3. **Mensch-Ausweg gegen Dauer-Stillstand (neu):** `work_queue reclaim --item X --actor <name> --reason <text>` schreibt `RECLAIM {item_id, actor, reason, expired_holder}`. Danach ist der Workkey wieder frei. Nur mit Actor und Grund; erscheint in Kolibri als „NEEDS YOU“, sobald ein Workkey länger als N Ticks `foreign_expired` ist.
4. **Nie:** automatische Neuvergabe nur wegen Zeitablauf; Lease-Ablauf ist keine Replay-Erlaubnis (Stufe-2-Regel).

## Negativtests (vor Umsetzung schreiben, rot → grün)
1. Zwei Homes, A postet (ATTACH), Lease läuft ab, Controller meldet RUNNING → B übernimmt nicht, kein zweites ASSIGNED.
2. Wie 1, Controller meldet COMPLETE+verified → Workkey freigegeben, **kein** neuer Controller-Task.
3. Wie 1, Controller meldet FAILED → B übernimmt, genau ein neues ASSIGNED.
4. Wie 1, Controller meldet BLOCKED → keine Übernahme, Status bleibt sichtbar.
5. Controller nicht erreichbar → keine Übernahme.
6. Kein ATTACH (A starb vor dem Posten) → B übernimmt.
7. `reclaim` ohne Actor oder Grund → abgewiesen; mit beiden → frei, Ereignis im Ledger.
8. Ursprünglicher Holder kommt nach `reclaim` zurück → bekommt den Workkey **nicht** stillschweigend zurück (Fencing über Ereignisfolge).

## Abhängigkeiten
- Setzt WQ-1 (`WQ-1_foreign_expired_lease.diff`) voraus.
- Abgleich liest nur (`GET`), schreibt nie in fremde Controller.
- Keine zweite Ledger-Wahrheit: ATTACH/RECLAIM sind Queue-Ereignisse über *wer arbeitet*, die Ausführungswahrheit bleibt das Controller-Journal.
