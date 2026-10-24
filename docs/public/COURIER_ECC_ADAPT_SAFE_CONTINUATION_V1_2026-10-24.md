# Courier Symphony — ECC ADAPT V1: Prüfqualität & sichere Fortsetzung

**Öffentliche Arbeitsregel · 24. Oktober 2026 · Status: PROPOSED / DOCS-ONLY / NO MERGE**

> **Freigabebasis:** Der Nutzer berichtet, dass der bestehende GrokBot-Master den selektiven ECC-Vorschlag mit **ADAPT** bewertet hat. Die lokale private Entscheidungsdatei wurde nicht von GitHub aus geprüft. Dieses Dokument ist eine öffentlich nutzbare, sichere Fassung der gemeldeten Entscheidung, **kein unverifizierter Claim über Produktionsänderungen**.

## Herkunft und Auswahl

Inspiration: [affaan-m/ECC](https://github.com/affaan-m/ECC), MIT-lizenziertes Projekt von affaan-m; zum Review betrachteter HEAD `90606c8315ee09cafc303515c5f33024db6b9882`. **Nur abstrakte Arbeitsmethoden inspiriert**, kein Drittcode, keine Hook-Dateien, kein ECC-Agenten-/Skill-/Command-Katalog und kein kopierter Inhalt.

Courier hat eigene Regeln und bestehende Skills `.agents/skills/courier-orchestrate` sowie `.agents/skills/courier-night-loop`. Diese bleiben maßgeblich. Die ECC-ADAPT-Regel darf ausschließlich **innerhalb** der bestehenden Courier-Architektur angewendet werden.

**Niemals annehmen:** Ein neuer Text-Prompt aktiviere selbst einen Scheduler, schaffe eine Writer-Lease, ermögliche private Host-übergreifende Dateizugriffe, bestätige Kontingent/Kosten oder autorisiere einen Merge.

## Die sechs selektiv übernommenen Methoden

| Methode | Courier-Interpretation | Kontrollpunkt |
| --- | --- | --- |
| **Evidence-first verification** | SHA + reproduzierbarer Test/Exitcode + erwarteter und tatsächlicher Status | `PASS / FAIL / NOT_PROVEN / UNKNOWN`; CI-GRÜN ist nicht Provider-REAL |
| **Red → Green → Review** | Zuerst auf relevantem HEAD mit fehlschlagendem Test reproduzieren, dann minimaler eigener Fix und unabhängige Gegenprobe | Nachweis der Fehler-Sensitivität; keine nur in Tests erfundene Simulation als Produktbeweis |
| **Agent architecture audit** | Unterscheide kanonischen Dispatcher, Queue-/Claim-Store, Ledger/Journal, Provider-Signale, Worker, Receipt und UI | Doppelwriter, Stale State, ACK/Replay, DONE ohne Proof, CostGate-Bypass verhindern |
| **Context & cost discipline** | Schlanker laufender Kontext, nur native tatsächlich belegte Quota-Informationen | Kein künstliches Quota-Verbrauchen, kein unbewiesenes 0-€-Claim |
| **Skill stocktake** | Bestehende Skills/Prompts zuerst inventarisieren, Überschneidungen entfernen | Keine doppelte Regel/Hook/Session, keine massenhafte ECC-Installation |
| **Progress-gated continuation** | Nächste wirklich unterschiedliche, autorisierte und verifizierbare Einheit statt Wiederholung | Fingerprint `role|owner|workkey|source_sha|proof_question`; `QUIESCENT_SAFE` bei keiner neuen Arbeit |

## Vorrangige Courier-Sicherheitsregeln

```text
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
```

- **Keine neue zentrale Dispatcher-Instanz**, kein neues `LedgerEngine`-Wahrheitssystem, keine verdeckte Writer-Lease, keine Agent-Rotation zur Limitumgehung.
- **Keinen zweiten Timer oder Stop-Hook:** Existierenden Scheduler, dessen echte Persistenz und die nächste Ausführung belegen; andernfalls `NOT_CONFIGURED`.
- **Keine neuen kostenpflichtigen Aktionen:** Auch „included_quota“ ist kein Freibrief für beliebige Befehle; für unklare Kosten `BLOCK`.
- **Kein stilles Umgehen von Human Gates:** Insbesondere Merge, Produktdateien fremder Owner, externe Veröffentlichungen, Credentials und rechtliche/finanzielle Aktionen.
- **Keine unnötigen Modell-Läufe:** Abgeschlossene Workkeys und identische PR-/CI-Events deduplizieren; bei Leerlauf ohne erzwungene Chatmeldung ruhen.
- **Keine privaten Daten auf öffentlichem GitHub:** Keine Tokenwerte, Geräte-/Privatpfade, Accounts, Nutzungsprozente, Handoff-Inhalte, Dateisicherungen, medizinische/persönliche Informationen.
- **Keine zusätzlichen Shell-/Repository-Scans gegen Projektvorgaben:** Kanonische `.agents/rules/NO_GREP_FAMILY.md` beachten.
- **Synthetische Tests und echte Provider-E2E-Abnahme getrennt benennen**; kein `FINAL` ohne journal- und taskgebundenes `RESULT_ACCEPTED` sowie überprüfte Receipt-Bytes.

## Einheitlicher Ablauf für künftige Courier-Fortsetzungs-Prompts

Ein guter Auftrag wird nicht nach Länge oder Anzahl der „Missionen“ bewertet, sondern nach nachvollziehbarer Fortschrittskette.

1. **ID & Rolle:** Bestehende konkrete Sitzung, Host und zugewiesene L1–L6-/Verifier-Lane. **Kein neuer Agent**.
2. **Aktueller Zustand:** `integration/v1`, PR-/Branch-HEAD, eigener letzter Checkpoint, bestehender Scheduler, Writer-Lease und Owner; historische Angaben neu prüfen.
3. **Eine priorisierte, neue Problemklasse:** ein tatsächlicher P0/P1 oder ein bestimmter unbelegter Produktvertrag mit kleiner, begrenzter Queue.
4. **Akzeptanz:** Ein reproduzierbarer Rotlauf, minimaler eigener Fix sofern autorisiert, gezielter Grünlauf und unabhängige Mutations-/Adversarial-Probe.
5. **Beweisvertrag:** `WORKKEY | OWNER | SOURCE_SHA | QUESTION | TEST | EXIT_CODE | ACTUAL | EXPECTED | PROOF_TYPE | RESULT | FOLLOWUP`.
6. **Weiterlauf:** Nach PASS nächste verschiedene eigene Einheit; nach FAIL reproduzieren; nach fremdem Scope nur Handoff; bei unverändertem Stand `QUIESCENT_SAFE`.
7. **Handoff:** Privater Checkpoint an existierendem berechtigtem Ort; nur über bestätigten Kanal als `SENT`, sonst `READY_TO_SEND`. Keine wiederholte Nachfrage bei bereits bekanntem Blocker.
8. **Zeit/Kosten/Limits:** Definierte Endgrenze des jeweiligen Auftrags; keine Dauerlaufgarantie durch Prompt, kein PAYG, maximal ein Heavy Job pro Host.

### Wiederverwendbarer kompakter Fortsetzungs-Prompt

```text
👑🥊👊😎🧪 COURIER SYMPHONY — ECC ADAPT SAFE CONTINUE
DU BIST DIE BESTEHENDE SITZUNG: <ROLE/HOST/LANE>.
KEIN NEUER AGENT, SCHEDULER, DISPATCHER ODER WRITER.

PRÜFE ZUERST:
- aktuellen kanonischen HEAD, eigenen Checkpoint, Owner und Lease;
- vorhandenen Trigger, dessen echte nächste Ausführung und Stopzeit;
- noch offene, unterschiedliche autorisierte Workkeys;
- tatsächliches Quota-/Kosten-Gate.

PRIORITÄT: <EINE KONKRETE OFFENE PRODUKTFRAGE>.
AKZEPTANZ: <NEGATIVTEST> -> <MINIMALER EIGENER FIX NUR MIT LEASE>
           -> <GEZIELTER GRÜNLAUF> -> <UNABHÄNGIGER PRODUKTPFADBEWEIS>.
PASS: Nächster neuer eigener Workkey.
FAIL: Reproduktion + genau ein Owner-Handoff.
BLOCKED: Andere autorisierte unabhängige Prüfung.
UNVERÄNDERT: QUIESCENT_SAFE statt Chat-Spam oder Pseudoarbeit.

PROTOKOLL:
WORKKEY, OWNER, SOURCE_SHA, TEST, EXIT_CODE, EXPECTED/ACTUAL,
PROOF_TYPE (SYNTHETIC / PRODUCTION_BOUND / REAL_PROVIDER),
COST_STATUS, CHECKPOINT, NEXT_ACTION.

PRIVATE Handoffs nur über tatsächlich bestehenden Kanal.
Keine doppelten Workkeys, fremde Writer-Leases oder unautorisierten Merges.
SINGLE_WRITER=YES; HEAVY_JOB_LIMIT=1; UNKNOWN_COST=BLOCK;
AUTONOMOUS_SPEND_LIMIT_EUR=0; NO_UNAUTHORIZED_MERGE=YES;
REAL_TRADES=0; WALLET_SIGNING=NO.
```

## Rollen bei Anwendung

- **GrokBot Mac – kanonischer Master:** Priorisiert und dedupliziert die übergreifenden Workkeys, respektiert Human Gates und die vorhandene Master-Zuständigkeit.
- **Separater GrokBot GR88/88-€-Account:** Unabhängiger, lesender Architektur-/Sicherheits-Reviewer und Handoff-Lieferant, **kein zweiter Master**, kein zweiter Produktwriter; individuelle Quota-Angaben nicht in öffentlichen Projektdateien festhalten.
- **Cursor Mac/Windows:** Ein klarer bestehender Writer-Scope nur mit aktueller externer Lease; Red/Green/Review.
- **Google Mac/Windows, Sindbad, Codex:** Getrennte unabhängige Prüffragen, Produktpfad-Negativtests, keine doppelte Implementierung.
- **Claude/L2:** Controller-/CostGate-/Ledger-Architektur innerhalb des explizit autorisierten Bereichs und der aktuellen tatsächlichen Verfügbarkeit.

## Einführung, Validierung und Rollback

- Zuerst nur **diese öffentliche Dokumentation** und die bewusste Anpassung neu formulierter Prompts.
- Keine stillen Änderungen an `AGENTS.md`, produktiven Skills, Runtimes, Hooks, globalen Regeln oder schedulenden Konfigurationen.
- Ein unabhängiger Prüfer vergleicht neue Fortsetzungsprompts mit den sechs Methoden und den Safety-Invarianten; **geringere Doppelarbeit / klarere Evidenz** ist die relevante Erfolgsmetrik.
- Falls die Regel Blocker verdeckt, neue Doppelarbeit erzeugt oder Kosten-/Owner-Gates schwächt: betreffende Prompt-Ergänzung zurücknehmen; keine Produkt-Rollback-Aktion nötig, da hier kein Produktcode verändert wird.
- **GitHub-Status:** Öffentlicher Dokumentationsentwurf im bestehenden offenen Dokumentations-PR. Ein Merge nach `main` oder `integration/v1` bleibt getrennt und freigabepflichtig.

## Quellen/Attribution

- [ECC / Everything Claude Code](https://github.com/affaan-m/ECC) — Ideeninspiration; [MIT-Lizenz](https://github.com/affaan-m/ECC/blob/main/LICENSE).
- Courier: `.agents/skills/courier-orchestrate/SKILL.md`, `.agents/skills/courier-night-loop/SKILL.md` und gültige kanonische V1-Projektregeln.

**Diese Arbeitsregel kann künftige Courier-Prompts anleiten. Sie aktiviert keine dauerhaft in ChatGPT gespeicherte Memory-Einstellung und überträgt keine Dateien zwischen Hosts.**
