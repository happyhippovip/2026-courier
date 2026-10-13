# COURIER EINSTEIN LAYER — Courier als Betriebssystem für digitale Arbeit

**Leitfrage:** Welche fundamentale Abstraktion fehlt heute zwischen menschlicher Absicht und digitaler KI-Arbeit?
**Antwort:** Die *verifizierte Arbeitseinheit mit Zielbezug* — ein Stück Arbeit, das beweist, welchen Beitrag es zu welchem Ziel geleistet hat, wer es geprüft hat und was es gekostet hat. Chats produzieren Text; Courier produziert *bewiesene Ziel-Deltas*.

Code-Bezug: `courier_orchestrator/mission.py` (Experiment aus Abschnitt 14), Architektur in `COURIER_GROKBOARD_V1.md`.

## 1 New Category Definition
**Proof-Carrying Work OS**: ein Betriebssystem, das Absicht in Missionen kompiliert, Arbeit auf austauschbare Worker verteilt (Economic Scheduler), nur bewiesene Ergebnisse festschreibt (Trust-System) und daraus dauerhaft lernt (Memory-System). Nicht Agent-Framework, nicht Chat, nicht Projektmanagement.

## 2 Fundamental Abstraction
Die **Goal-Delta-Einheit**: `(Goal, Delta, Evidence, Verifier, Cost)`. Alles andere — Prompts, Modelle, Provider — ist austauschbare Ausführung. Ein OS hat Prozesse und Dateien; Courier hat Missionen und bewiesene Deltas. Der Hubwriter ist der Kernel: einziger Schreibpfad.

## 3 Work Physics
```
EXPECTED_UTILITY = EXPECTED_VALUE − COST − RISK_PENALTY − UNCERTAINTY_PENALTY − DELAY_PENALTY
```
- **UNCERTAINTY_PENALTY** = Wert × (1 − TRUST(worker, task_class)) — im Slice vereinfacht als `1 − trust`.
- **COUNTERFACTUAL_VALUE_SCORE** = Wert des Ergebnisses − Wert dessen, was ohne den Task ohnehin passiert wäre. Tasks, deren Ergebnis sowieso entsteht, haben Score ≈ 0 und werden nicht geplant.
- **VALUE_OF_INFORMATION** = erwartete Verbesserung der nächsten Entscheidung durch einen Erkundungs-Task − dessen Kosten. Rechtfertigt billige Probe-Tasks vor teuren Bau-Tasks.
Ein Task mit Utility ≤ 0 wird nicht ausgeführt (`run_experiment`: `SKIPPED_LOW_UTILITY`).

## 4 Mission Compiler
`Mission → Success Conditions → Constraints → Required Evidence → Streams → Packages → Tasks → Verification Plan`.
Jeder Task trägt `WHY_THIS_TASK_EXISTS, WHAT_GOAL_DELTA, WHAT_EVIDENCE, WHY_NOW, WHY_THIS_WORKER`. Ohne Goal-Delta (Bezug zu einer Success Condition) wird er nicht ausgeführt. Im Slice: `compile_mission()` erzeugt PRODUCT-1 und WEBSITE-1 mit allen fünf Begründungen; ein Test erzwingt, dass jedes Goal-Delta eine Success Condition ist.

## 5 Proof-Carrying Work
Jedes Ergebnis ist ein Paket: **Result, Provenance, Evidence, Verification Method, Runtime Identity, Cost, Side Effects**. Keine Selbstzertifizierung: ein PASS des Erzeugers zählt nie (Hubwriter `SELF_PASS_NOT_ACCEPTANCE`).
| Domäne | Evidence | Verification Method |
|---|---|---|
| Code | Diff + Commit-SHA + Testlauf-Log | unabhängiger Testlauf/Review |
| Research | Quellen-URLs + Zitate + Abrufzeit | Stichprobenprüfung der Zitate |
| Website | HTML-Diff + Screenshot + Botschafts-Bindung | Reviewer: nur gebundene Botschaft, keine neuen Claims |
| Revenue | Zahlungs-/CRM-Beleg-ID (read-only) | Abgleich mit Quelle; jede Zahlung = Human Gate |

## 6 Worker Market
Worker geben Gebote ab: `(Kosten, Zeit, Confidence, historischer Erfolg, Capability)`. Auswahl: maximale Utility unter Risikogrenze; **Verification Depth** steigt mit Risiko und sinkt mit Trust (vertrauter Worker auf risikoarmer Klasse → Stichprobe; neuer Worker oder hohes Risiko → volle Prüfung). Billigste ausreichende Fähigkeit gewinnt.

## 7 Trust Graph
`TRUST(worker, task_class)` = (PASS+1)/(Prüfungen+2), gespeist **nur** aus unabhängiger Verification-Evidence. Selbstbewertungen, Markenname, Werbung ändern nichts (Test `test_trust_ignores_self_certification`). Trust ist pro Task-Klasse: ein guter Coder ist nicht automatisch ein guter Texter.

## 8 Work Capsules
Eine Capsule = kleinster ausführbarer Kontext: Worker Contract + nur die gebundenen Results, die der Task braucht (`context_keys`). Kein Gesamt-Chatverlauf, keine Copy/Paste-Kette. Im Slice bekommt WEBSITE-1 ausschließlich das akzeptierte Output von PRODUCT-1. Capsules sind portabel (JSON) und providerneutral.

## 9 Compounding Memory
- **Semantic Delta**: Brain speichert nicht Transkripte, sondern was sich am Wissen über das Goal geändert hat.
- **Failure Dividend**: jede Ablehnung (z. B. `CONFLICT:new_claim_not_in_message`) wird zu einer Regel für künftige Capsules — Fehler werden einmal bezahlt.
- **Unsicherheitszustände** je Fakt: `KNOWN` (verifiziert), `LIKELY` (eine Quelle, unverifiziert), `UNCERTAIN`, `CONFLICTING` (widersprüchliche Results → Reviewer/Mensch), `UNKNOWN`. Nur KNOWN darf als Fakt in Capsules.

## 10 Autonomy Envelope
Grenzen pro Goal: **Zeit, Kosten, Write-Scope, externe Wirkung, Risiko, Concurrency**. Innerhalb arbeitet Courier ohne Rückfrage; außerhalb Human Gate. Dazu ein **Interruption Budget**: maximale Anzahl Rückfragen pro Goal/Tag; Courier bündelt Fragen, statt zu stören. Human Gates: payment, purchase, subscription, OAuth, publication, destruktiv, legal commitment, scope escalation, unbekannter externer Effekt.

## 11 Grokboard-Integration
Die vorhandenen Courier-Bots (Courier Grok, Umsatz, Produkt, Integration, Website, Prüfer, Katalog, Tests, Datenrettung, Wand-Aufsicht, Vogel) werden Worker-Instanzen in der Registry, mit Capabilities und Trust. Mission View über der Worker-Ansicht:
```
GOAL  Verbessere Landingpage + Produktbotschaft
VALUE 5,5 (geschätzt)   BUDGET 1,00 € / 0,19 € verbraucht
PROGRESS 2/2 Success Conditions   CONFIDENCE KNOWN
WORKERS ACTIVE 0   VERIFIED RESULTS 2   NEEDS YOU —
```

## 12 Billion-Scale Value — 3 Netzwerkeffekte ohne zentrale private Daten
1. **Trust-Graph-Effekt**: Verifikationsergebnisse (nicht Inhalte) pro Worker×Task-Klasse werden geteilt; jeder Nutzer macht das Routing für alle besser.
2. **Capsule-/Missions-Templates**: kompilierte Missionsstrukturen und Verification-Pläne (ohne Kundendaten) werden wiederverwendbar — Failure Dividends kumulieren netzwerkweit.
3. **Worker-Markt-Liquidität**: mehr Missionen ziehen mehr Worker/Provider an, Preise pro verifiziertem Ergebnis sinken. Daten bleiben exportierbar beim Nutzer (digitale Souveränität).

## 13 Moat-Bewertung
| Moat | Stärke | Begründung |
|---|---|---|
| Modellzugang | schwach | austauschbar |
| UI | schwach | kopierbar |
| Trust Graph aus echter Verifikation | **stark** | entsteht nur durch Zeit + Volumen |
| Failure-Dividend-Bibliothek | stark | kumulativ |
| Single-Writer-Journal (Beweiskette) | mittel | technisch kopierbar, organisatorisch selten |

## 14 ONE MVP Experiment
Goal „Verbessere die Courier-Symphony-Landingpage und ihre Produktbotschaft“ mit Mock-Workern Product, Website, Reviewer: Mission kompilieren → Product-Task → Result binden → Website-Task mit minimalem Kontext → unabhängiger Reviewer → Konfliktbehandlung (Website erfindet Claim, Reviewer lehnt mit CONFLICT ab, Retry) → Hubwriter-Delta → Goal-Status.
`python3 -m courier_orchestrator.mission` (Mock, gemessen):
```
GOAL_STATUS=DONE  MANUAL_COPY_PASTE=0  RESULT_BINDING=YES  CANONICAL_WRITERS=1
UNVERIFIED_CLAIMS_AS_DONE=0  TOTAL_COST=0.19 EUR (mock)  TOTAL_TIME≈0.000 s (mock)
VERIFIED_OUTPUTS=2  HUMAN_INTERRUPTS=0
```
Ohne Retry-Spielraum (max_attempts=1) endet es korrekt in NEEDS_YOU mit 1 Interrupt.

## 15 ONE North Star Metric
**VERIFIED_GOAL_DELTAS_PER_REAL_EURO** (verifizierte, akzeptierte Ziel-Deltas pro real ausgegebenem Euro, bei UNVERIFIED_CLAIMS_AS_DONE = 0).

## 16 ONE Sentence
**„Sag Courier dein Ziel – du bekommst nur Bewiesenes.“**

COURIER_CATEGORY=Proof-Carrying Work OS (Betriebssystem für verifizierte digitale Arbeit)
ONE_ARCHITECTURAL_MOVE=Ein einziger Schreibpfad (Hubwriter) akzeptiert nur Goal-Deltas mit unabhängiger Verifikation; alles andere ist austauschbare Ausführung
ONE_MVP_EXPERIMENT=Landingpage+Produktbotschaft mit Product, Website, Reviewer (Mock): gebundene Results, Konflikt erkannt, 2 verifizierte Outputs, 0 Copy/Paste, 1 Writer
NORTH_STAR_METRIC=VERIFIED_GOAL_DELTAS_PER_REAL_EURO
WHY_THIS_COULD_BE_10X_BETTER=Heute zahlt der Mensch für Text und prüft selbst; Courier zahlt nur für bewiesene Ziel-Deltas, routet zum billigsten vertrauenswürdigen Worker und stört nur an echten Gates
FIRST_THING_NOT_TO_BUILD=Keinen eigenen Chat und keine Live-Provider-Adapter, bevor Hubwriter über den Controller schreibt und der Trust Graph echte Verifikationsdaten hat
