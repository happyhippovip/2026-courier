# Courier Symphony — Release-Train-Marathon V1

> **NEUE DRITTE SPUR — DUAL-DISPATCHER HOT STANDBY V2 (23.10.):** Neben Safety Track A und Product Track B existiert ein streng abgegrenzter **Read-only Architektur-/Test-Track C** für [gemeinsame Master-Epoch, atomare Übergabe und serverseitiges Fencing](./COURIER_DUAL_DISPATCHER_HOT_STANDBY_V2_2026-10-23.md). Windows bleibt bis zur technischen Durchsetzung **STANDBY_READ_ONLY**; noch kein echter Failover, keine automatische zweite Master-Instanz. Diese dritte Spur verursacht **keine** zusätzliche Produkt-Writer-Lane.
**Öffentliche Strategie und koordinierte Umsetzung · 23.10.2026 · Happy Hippo VIP 👑🥊👊😎🚀**

> **STATUS: VORSCHLAG / DOKUMENTATION, KEINE AUSFÜHRUNG.** Dieser Plan startet keine Agenten, registriert keine Workkeys, aktiviert keinen Timer, verteilt keine Leases und autorisiert keinen Merge. Ein offenes Goal ist nicht mit einem dauerhaften Hintergrundprozess gleichzusetzen. Alle Livezustände vor der Ausführung neu prüfen.

## 0. Tatsächliche Grundlage (GitHub-Snapshot vom 23.10.2026)

- Produkt: [2026-courier](https://github.com/happyhippovip/2026-courier); Zielbranch `integration/v1` zuletzt auf `81bbf224b0aeeca4a2b92db29dfc7220b707043a`.
- [PR #835](https://github.com/happyhippovip/2026-courier/pull/835) **gemergt** auf diesen Integrationsstand. [PR #836](https://github.com/happyhippovip/2026-courier/pull/836) (Provider DONE), [#837](https://github.com/happyhippovip/2026-courier/pull/837) (ABC-Journal), [#838](https://github.com/happyhippovip/2026-courier/pull/838) (Einmal-Wakeup), [#842](https://github.com/happyhippovip/2026-courier/pull/842) (Windows-Tests) waren offen. Die Dokumentations-PRs #839 und #841 sind separat.
- [Courier v1 CI #40008119253](https://github.com/happyhippovip/2026-courier/actions/runs/40008119253) ist **rot** (Windows-pytest); [Customer-Reality Gate #40008119364](https://github.com/happyhippovip/2026-courier/actions/runs/40008119364) ist **grün**. Kein Gesamt-Release-PASS.
- Unabhängig durch Windows-Joblog nachgewiesen: `tests/test_windows_worker_contract.py::test_success_without_any_artifact_evidence_is_reported_failed`. Beim Post eines `FAILED`-Results ohne Artefakte bleibt der Task `DISPATCHED`; der Test erwartet `QUEUED`. **Die exakte Root Cause ist UNPROVEN.** Den Test nicht abschwächen, Status nicht als erledigt etikettieren.
- Bestehende Cursor A→B-Worker-Lane hatte laut Agentenbericht **QUIESCENT**, keinen READY-Workkey und keine Writer-Lease. Das ist kein Fehler des Modellkontingents.
- Google Antigravity Mac meldete ein bereits aktives Goal und genau einen 30-Minuten-Wakeup; tatsächlicher UI-Scheduler- und Ablaufstatus ist außerhalb der Sitzung hier nicht direkt beobachtet. Der Cursor-Project-Koordinator hat einen anderen Runtime-/Subscription-Kontext.

## 1. Neuer Arbeitsmodus — zwei Spuren, fünf Gates

**Spur A — Sicherheits- und Release-Kette:** der reproduzierte Windows-CI-Blocker, danach unabhängige Verifikation der geänderten Eigenschaften, dann L1-Integration mit erneuter Gesamt-CI. **Spur B — echter Produktwert:** bestehende Offline-Demo, Desktop-Hub-Readiness, Installer-/Nutzerpfad und nachvollziehbare Kundenfunktion auf isolierten, konfliktfreien Aufgaben. B darf parallel weitergehen, auch wenn A wartet; B darf keinen roten Release-Gate übergehen.

| Phase | Bestehende Rolle | Erlaubte Arbeit | Abschluss-Gate für den nächsten Schritt |
| --- | --- | --- | --- |
| **1. MISSION CONTROL** | Bestehender Grok-Hauptkoordinator (falls tatsächlich autorisiert und mit Zugriff) | HEAD, aktive Owner, Leases und Workkeys einmalig prüfen, Duplikate entfernen, zwei Spuren planen | Eine autoritative Zuordnung mit konkreten, getrennten bereits erlaubten Aufträgen, **keine erfundenen READY-Keys** |
| **2. RED → GREEN** | **Windows-Worker-Owner** mit gültiger Dateiscope-Lease; ggf. separater L2-Controller-Owner | Minimalen roten Negativfall reproduzieren; Worker → Result → Server-Statusübergang untersuchen; kleinsten korrekten Patch auf eigenem Scope vorbereiten | Gezielt reproduzierbarer Rot-Beweis → Fix-Kandidat → derselbe Test grün; unveränderter Akzeptanzvertrag |
| **3. ADVERSARIAL ACCEPTANCE** | Unabhängige Google-/Sindbad-/Codex-Prüfer, unterschiedliche bestätigte Read-only-Scopes | Geänderte PR-HEADs und neuen Fix unabhängig prüfen; #836 DONE≠FINAL, #837 eigene Task-/Attempt-/Journal-Belege, fehlende Artefakt-Bytes und Stale-Replay | Prüfergebnis mit exaktem SHA, reproduzierbarer Negativtest-Evidenz und verbleibenden P0s; keine Selbstabnahme |
| **4. INTEGRATION TRAIN** | **L1**, bestehende einzige Merge-Instanz | Nach formaler Freigabe Korrektur/PRs in tatsächlicher Abhängigkeitsreihenfolge integrieren, Trunk-CI erneut prüfen | Vereinheitlichter HEAD, die **für ihn** wirklich abgeschlossenen CI-/Acceptance-Gates, keine offenen ungelösten P0-Freigaben |
| **5. NEXT PRODUCT SLICE** | Cursor Project-Koordinator und explizit autorisierte Produkt-Owner | Aus freigegebenem Backlog den nächsten abgegrenzten Demo-/Produktnutzen definieren, read-only prüfen, anschließend erforderliche Writer-Owner autorisieren lassen | Zwei **verschiedene** nachweislich übergebene/abgenommene Aufträge, ein doppeltes Event erzeugt **keine** Doppelarbeit; nächste echte Produktfähigkeit dokumentiert |

**Phasen sind Gate-Abhängigkeiten, keine Pflicht, fünf Prompts sofort hintereinander zu versenden.** Phase 1 kann B sofort vorbereiten. Phase 3 kann bereits existierende, noch nicht abgenommene PR-Belege prüfen; die finale Windows-Fix-Abnahme wartet auf den tatsächlichen Kandidaten. Phase 4 bleibt bei L1.

## 2. Zuständigkeitsmatrix — ein Repo, mehrere Programme

| App / Fenster | Rolle | Darf nicht |
| --- | --- | --- |
| GrokBot Ultra | Bestehender Koordinator, Owner-/Lease-/Task-Konflikte vermeiden, Ergebnisse zusammenführen | Schattenledger, erfundene Leases, ohne native Verbindung Agentenstarts behaupten |
| Cursor Windows | Eigener bestehender Windows-Worker-/L6-Scope, minimaler CI-Fix bei gültiger Lease | Controller-/L2-Fremdscope ändern oder ohne L1-Freigabe mergen |
| Google Antigravity Windows | Unabhängige Windows-Gegenprüfungen im eigenen Scope | Zweiten Produktwriter bilden; identische Tests ohne neues Delta wiederholen |
| Grok Sindbad / Codex | Unabhängige Receipt-/FINAL- und Kosten-Red-Teams | Selbstabnahme, fremde Dateien oder unautorisierte Provider-Aufrufe |
| L1 | Integrationsreihenfolge, akzeptierte Belege, CI und Merge-Promotion | Rotes CI als grün deklarieren oder offene Human-Gates übergehen |
| Cursor Ultra Mac **Project-Koordinator** | Native Project-Aufgaben, Cloud-Delegation und Abonnement-Ziele verifizieren, Produktspur B koordinieren | Den beendeten A→B-Worker mit CONTINUE-Fluten wiederbeleben |
| Cursor Ultra Mac **Cloud Worker** | Genau einen gültig zugewiesenen Scope bearbeiten | Aus `/goal` selbst eine Writer-Lease ableiten |
| Google Antigravity Mac | Schon vorhandenes `/goal`/ein Timer; unabhängige lokale Mac-Integrationstests | Cursors Project-Listening oder zusätzliche Google-Scheduler als dasselbe behandeln |
| Claude/Opus, Muse, andere bestehende Owner | Ihre tatsächlich besessenen Aufgaben | Fremde Leases beanspruchen, Ressourcenstopp missachten |

## 3. Präzise Ereignissteuerung statt Dauerloop

Ein neuer Turn ist nur sinnvoll, wenn ein **nachweisbar neuer Input** vorliegt:

- Ein relevanter Pull-Request-HEAD, Review-/Merge-Status oder CI-Ausgang ändert sich.
- Eine autoritative Writer-Lease / ein READY-Workkey wird dem richtigen Owner zugeteilt.
- Ein unabhängiger neuer Fix-Kandidat / Ergebnisbeleg liegt vor.
- Ein freigegebener Produktmeilenstein startet mit eindeutiger Annahmebedingung.

Empfohlener **Dedupe-Schlüssel**: `application|project|event_id|pr|head_sha|workkey|acceptance_question`. Gleicher Schlüssel mit unverändertem State: **KEINE** Tests, Queue-Neuanlage, Agentenstarts oder Status-Spam. Bei mehreren Events während `RUNNING` coalescen zu einem `RECHECK_NEEDED`, kein Stapel von identischen Wachrufen. Siehe [Wake-Coalescing-Vertrag](../v1/AUTOMATION_WAKE_COALESCING_CONTRACT.md).

Prüfe **in der tatsächlich betroffenen Anwendung**, ob Goal, Timer, Subscription oder Hook aktiv ist und welches Fenster/Agent sie adressieren. Ein fertiggestellter Goal-Lauf kann eine aktive Subscription besitzen, aber ohne neues Ereignis ist `QUIESCENT` korrekt. **Kein zweiter Scheduler, kein rekursiver Stop-Hook, kein blinder `/loop`, kein 65×-Prompt-Stack.** Eine öffentliche Datei allein aktiviert nichts.

## 4. Qualitäts- und Kosten-Gates

```text
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
```

- Bestehende tatsächlich verifizierte **inkludierte Abokapazität** darf für freigegebene Arbeit genutzt werden, jedoch **keine** PAYG-/On-Demand-/Overage-Nutzung, kein Kauf, keine Rotation zwischen Konten zum Umgehen von Grenzen. Prozentanzeigen auf `used` vs. `remaining` prüfen.
- Bis zu **zwei** unterschiedliche leichte Read-only-Cloud-Prüfungen als vorsichtiger Einstieg nur nach bestätigter Deckung; spätere Skalierung aufgrund zweier **verifizierter Ergebnisse**, gesunder Ressourcen und freiem Scope. Werbeversprechen über 129 oder mehr Agenten sind kein garantierter Kontoumfang.
- Keine parallelen schweren Tests am selben betroffenen Host. Mac-RAM/Swap/EMFILE und RESOURCE_PAUSE sind Stop-Gates.
- `synthetic PASS` ≠ `cross-host VERIFIED` ≠ `real-provider VERIFIED` ≠ `production release`.
- Ein Issue/PR/Fix kann nur durch aktuellen überprüften Befund abgeschlossen werden. `pytest pass` an altem Commit ersetzt keinen Abnahmelauf auf dem integrierten Kandidaten.

## 5. Was als überprüfbares Ergebnis zählt

Jede Arbeit liefert nur bei tatsächlichem Fortschritt:

```text
PHASE | TRACK(A/B) | WORKKEY | ACTUAL_OWNER | LEASE |
REPOSITORY | HEAD | PR/CI_RUN | CHANGED_FILES |
NEGATIVE_TEST | EXIT_CODE | EVIDENCE_TYPE | COST_SOURCE |
VERDICT(VERIFIED/REPORTED/BLOCKED/UNKNOWN) |
CHECKPOINT | NEXT_DEPENDENCY | NEXT_REAL_EVENT
```

- **Vorher/Nachher:** neuer belegter Defekt, kleiner Fix im erlaubten Scope, unabhängige Abnahme, tatsächliche CI-Veränderung, verbesserte Demo- oder Produktfunktion.
- Berichte und Proofs im bestehenden erlaubten **privaten** Checkpoint-System halten; in öffentliche Dokumentation nur nicht-sensitive Rollen, SHA, Testnamen und allgemeine Verfahren.
- Wenn alle aktuell zulässigen Aufgaben fehlen: ein Checkpoint, `QUIESCENT_SAFE`, abwarten. **Nicht** dieselbe abgeschlossene Lane erneut beschicken, nur um Laufzeit zu verlängern.

## 6. Abnahme der Orchestrierung selbst

Vor „automatische Agentenübergabe funktioniert“ folgende **reale**, erlaubte Schritte nachweisen:
1. Zwei **verschiedene**, bestehende und autorisierte Read-only-Workkeys.
2. Ein nativer Koordinator und zwei korrelierbare Ausführungs-/Agent-IDs, jeweils eigenes Ergebnis und Checkpoint.
3. Native Subscription/Trigger und tatsächlicher Übergang nach einem **neuen** freigegebenen Ereignis.
4. Wiederholtes identisches Event führt zu **0** weiterer Ausführung, **0** zusätzlichen Kosten.
5. Kein Writer-/Heavy-Job-Konflikt; keine Veränderung von außerhalb zugewiesenen Dateien.

Solange die native End-to-End-Übergabe nicht beobachtet wurde: `AUTONOMOUS_RELAY=UNPROVEN`. Kein Screenshot oder Skriptplan darf dies zum `VERIFIED` hochstufen.

## Weiterführende Dokumente

- [Kopier-Prompts für die fünf Phasen](./COURIER_RELEASE_TRAIN_PROMPT_PACK_V1_2026-10-23.md)
- [Goal-Stop und Windows-CI-Checkpoint V3](./GOAL_STOP_SCHEDULER_WINDOWS_CI_HANDOFF_V3_2026-10-23.md)
- [Cursor Ultra Mac Project-Koordinator](./CURSOR_ULTRA_MAC_PROJECT_COORDINATOR_PROMPT_V1_2026-10-23.md)
- [Cursor Mac vs. Google Mac](./COURIER_MAC_CURSOR_VS_GOOGLE_ROLE_MAP_2026-10-23.md)
- [Öffentliche Teamkoordination in gesondertem PR #839](https://github.com/happyhippovip/2026-courier/pull/839)
- [Privates Projektgedächtnis](https://github.com/happyhippovip/2026-project-memory) (nur für autorisierte Beteiligte)

**Dauerhafte Regel:** Die fünf Phasen führen zu einem echten Ergebnis oder zu einer ehrlichen Blockade. Sie sind **keine fünf Endlosschleifen**, keine zusätzlichen Controller-Instanzen und kein Garant für eine bestimmte Agentenlaufzeit.
