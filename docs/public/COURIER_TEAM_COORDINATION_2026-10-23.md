# Courier Symphony — Teamkoordination und sichere Nachtschicht
**Öffentlicher Koordinations-Snapshot: 23. Oktober 2026 · Happy Hippo VIP 👑🥊🧪🚀**

> **PRE-RELEASE · KONZEPT + AKTUELLER GITHUB-SNAPSHOT.** Dieses Dokument startet keine Agenten, setzt keine Tasks oder Leases, autorisiert keinen Merge und garantiert keinen unbeaufsichtigten Dauerlauf. Der öffentliche Text enthält bewusst keine privaten Checkpoints, Kontostände, Gesundheits-/Finanzdaten, Token oder Rechnerdetails.

## Worum es geht

Courier Symphony entwickelt ein lokales, prüfbares System für die sichere Ausführung, Wiederaufnahme und Verifikation von Computeraufgaben. Mehrere getrennte KI-Agentensitzungen unterstützen Implementierung, Review, Regressionstests und Release-Vorbereitung. **Ein Agenten-„DONE“ ist keine technische Verifikation und eine grüne Einzel-CI kein Produktions-GO.**

### Ansprechpartner und Zuständigkeiten

| Rolle | Eindeutiger Aufgabenbereich | Ergebnis / Übergabe |
| --- | --- | --- |
| **GrokBot Ultra — Master-Dispatcher / Coordinator** | Einmalig aktuelle Änderungen zusammenführen, fehlende Owner/Leases erkennen, Workkeys klar verteilen, keine Produktdateien als zweiter Writer bearbeiten | Privater Koordinationscheckpoint + eindeutig nächste autorisierte Aufgabe |
| **GrokBot GR88 — Architektur, L3-Integration & Recovery-Koordinator** | Read-only Architektur-Reviews von L3, Controller, Ledger, Cross-Home, sichere Datenrettungs-Bereitschaft für Mac und Windows koordinieren | Unabhängiger Review, private Owner-Handoffs, keine Reparatur ohne Zustimmung |
| **GrokBot Sindbad — Receipt/FINAL Red-Team** | Unabhängige Negativtests zu Digest, Receipt-, Task-/Attempt-/Dispatch-/Worker-Bindung und doppeltem FINAL | Tests/Patches nur isoliert, dann fachlicher Owner-Handoff |
| **Cursor Ultra Mac — A→B→C / L2-Integrationspfad** | Controller- und A→B→C-Integration im jeweils autorisierten Schreibscope | Implementierung mit Proof, Tests, Commit, freigegebener PR |
| **Cursor Windows — L6/Windows-Worker** | Windows-Daemon, LeaseStore, Installer, Windows-Regression und eigenständige Releasesicherheit | Windows-Build-, Restart-, Lock- und CI-Nachweise |
| **Google Antigravity Mac — unabhängiger Auditor** | Synthetic A→B→C, Proof, Cross-Host, Offline-Demo und Mac-Regression | Isolierte Auditnachweise ohne zweiten Produktwriter |
| **Google Antigravity Windows — unabhängiger Windows-Verifier** | Claim-/Nonce-/Lease-Negativtests, Replay, CostGate und Windows-Portabilität | Isolierte Regression, Evidenz und Owner-Handoff |
| **Claude Opus — Ledger-Engine und CostGate** | In seinem autorisierten Scope: Journal-Proof, Admission, Idempotenz, CostGate und sichere Queue-Logik | Gezielte Implementierung mit negativen Tests; kein zweiter Ledger |
| **Codex — unabhängige Sicherheitsabnahme** | Receipt-/FINAL-/CostGate-Reviews mit neuem Scope und nachgewiesener Testevidenz | Review-Votum und reproduzierbare Befunde |

Die **L1-Integrationsinstanz** ist allein für die Promotion nach `integration/v1` zuständig. **HG-02** und andere menschliche Freigaben bleiben erhalten. Rollen und Agenten sind nicht automatisch Writer-Leases; alle Zuständigkeiten sind zur Laufzeit anhand aktueller kanonischer Projektregeln zu prüfen.

## Relevant für den GitHub-Snapshot vom 23. Oktober 2026

**Update vom 23.10.2026:** #835 wurde inzwischen gemergt. Die nachfolgenden Pull Requests waren beim letzten Check weiter **offen**; Git-SHAs und CI zur Laufzeit erneut prüfen:

- [#836 — Provider DONE darf Workkey nicht FINAL machen](https://github.com/happyhippovip/2026-courier/pull/836).
- [#837 — A→B→C Journal Proof](https://github.com/happyhippovip/2026-courier/pull/837).
- [#838 — exakt eine Fortsetzungsnachricht, keine Queue-Duplikate](https://github.com/happyhippovip/2026-courier/pull/838).
- [#840 — Vorschlag für wiederverwendbaren Safe-Autonomy-Modus](https://github.com/happyhippovip/2026-courier/pull/840).

PR #827, #830, #832 und #835 wurden bereits gemergt. Externe, ältere Receipt-Patches gegen frühere HEADs dürfen deshalb nicht blind angewandt werden: zuerst Diff- und Konfliktvergleich, dann isolierte Neuprüfung. PR #834 wurde gemergt. Status weiterer PRs immer aktuell prüfen.

## Übergabe Codex ↔ GrokBot Ultra ↔ Claude (23./24.10.2026)

**GrokBot Ultra:** Ein unabhängiger Audit wurde wegen einer erreichten Nutzungsgrenze **unterbrochen**, nicht fachlich abgeschlossen. Isolierte Prüfdateien sind nicht automatisch auf anderen Geräten/Konten vorhanden. Der Dispatcher führt den Zustand als `PARTIAL / QUOTA_STOP`; keine erfundenen PASS- oder Merge-Freigaben.

| Rolle | Eindeutige nächste Aufgabe | Evidenz |
| --- | --- | --- |
| **Codex — unabhängige Abnahme** | Prüft auf aktuellem `integration/v1` nur noch unbelegte Receipt-, Accepted-Attempt-, CostGate- und FINAL-Invarianten; unterscheidet #815-Dateibyte-Fix vom separaten roten CI-Fall; vergleicht bereits gemergte #827/#830/#832 | Exakte SHAs, gezielte Tests, Exitcodes, reproduzierbare Befunde und Owner-Handoffs |
| **GrokBot Ultra — Master-Dispatcher** | Codex registrieren, bisherigen Grok-Audit deduplizieren, klare Owner/Leases und offene P0-Gates koordinieren; keine fremde Implementierung übernehmen | Privater Koordinationscheckpoint, ein Workkey pro neuer Aufgabe, kein Doppelsender |
| **Claude Opus — spätere Übergabe ab ca. 03:00 Europe/Berlin am 24.10.** | Nach tatsächlicher Verfügbarkeit die kanonische Ledger-/Queue-/Controller-Architektur mit neuesten Commits prüfen, Admission-/F-C1-Grenzen untersuchen, eigene gesicherte L2-Arbeiten fortführen | Testgestützte eigene Änderungen nur mit gültiger Writer-Lease, ansonsten isolierte Patches und Handoff |

**03:00 ist die vom Team erwartete Übergabezeit, keine hier angelegte Automation und keine Startgarantie.** Kein unautorisierter Cron, Cloud-Start oder zusätzliche Abrechnung.

### Prüf- und Release-Gates

- [#815](https://github.com/happyhippovip/2026-courier/pull/815): Der Datei-/Bytes-Fix ist bereits vorhanden; die letzte geprüfte v1-CI war rot. Ein unabhängiger Audit meldete bestandene gezielte Datei-/Bytes-Tests, nicht die Behebung des separaten CI-Problems.
- [#830](https://github.com/happyhippovip/2026-courier/pull/830): Eine frühere Architekturwarnung betrifft das Risiko eines zweiten Dispatchers/Claim-Stores. Trotz erfolgtem Merge bleibt die **Single-Truth-Integration** auf aktuellem Stand nachzuweisen.
- [#832](https://github.com/happyhippovip/2026-courier/pull/832): Die `local_shell`-Kostendeklaration ist durch die zuständigen Prüfer unabhängig gegen tatsächliche unbekannte Kosten und Admission-Bypass zu untersuchen.
- Private Agenten-Arbeitsdateien, Nutzungswerte, Token, Computer-/Laufwerkspfade und operative Checkpoints bleiben privat.

**Update-Regel für Happy Hippo:** Neue öffentliche Commits nur bei einer bedeutsamen Änderung der Teamzuständigkeiten, Arbeitsweise oder belegten Release-Gates. Zwischenstände, temporäre Kontingente und private Prüfergebnisse bleiben im privaten Projekt-Handoff. Bei unverändertem Zustand keinen neuen PR, Sender oder Commit erzeugen.

## Zwei getrennte Windows-V10-Missionen (23.10., Abends)

- **Cursor Windows = Zustell- und Continuation-Owner:** [32 Aufgaben für echte Result-/ACK-/Heartbeat-/StopLoop-Regressionssicherheit](./CURSOR_WINDOWS_DELIVERY_MARATHON_V10_2026-10-23.md). PR #838 letzter gemeldeter Head `eb6393d52`; neue CI im letzten Snapshot noch in Bearbeitung. Keine Änderungen an fremdgeleasten `daemon.py`-Dateien.
- **Google Antigravity Windows = unabhängiger Verifier:** [35 Aufgaben mit Produktionspfad-Tests statt reiner Mock-Tests](./GOOGLE_WINDOWS_TRUE_PROOF_MARATHON_V10_2026-10-23.md). PR #842 letzter Head `0983d26c`; seine sieben Prüfjobs waren grün, aber einige Tests testen lokale Simulationen statt der echten Controller-/Receipt-Implementierung.

**Warum getrennt?** Cursor soll die echte Windows-Liefer-/Fortsetzungslogik in seinem zuständigen Bereich verbessern; Google soll die unabhängigen negativen Beweise für Journal/Receipt/CostGate/ACK bewerten. Beide nicht dieselben Produktdateien bearbeiten. Keine künstlichen Doppel-Queues, neuen kostenpflichtigen Agenten oder Merges ohne Berechtigung.

## Nachtmarathon V12 — echte Wiederaufnahme statt Prompt-Stürme

**Einzelfallrollen, Stand 23. Oktober 2026:**

- **GrokBot Windows Recovery:** Getrennter, ressourcenschonender Datenrettungs-Prüfer. Nur lesende Backup-/Archiv-/Checksum-Inventur und Risikoanalyse; keine destruktive Reparatur und kein Zugriff auf Originaldatenträger ohne explizite Freigabe.
- **GrokBot Mac Architecture/Coordinator:** Read-only Koordination zwischen Mac- und Windows-Recovery, L3 und Integrationsowner; private Checkpoints und deduplizierte Workkeys; keine fremden Writer-Rechte.
- **Cursor Windows:** Produktzustellung `DISPATCHED`/RESULT_ACK, Crash/Retry, Pressure Heartbeats; nur im eigenen Writer-Scope.
- **Google Windows:** unabhängige Regressionen gegen echte Controller-/Journal-/Receipt-Pfade; nicht dieselbe Implementierung.
- **Cursor Mac:** A→B→C, aktuelle Integrations- und Verifier-Verträge, eigene autorisierte Implementierungen.
- **Google Mac:** unabhängige A→B→C-/Ledger-Negativtests, bereits aktive Goal-/Timer-Instanzen deduplizieren.

**Native Mechanismen (erst Zustand und Kosten prüfen):**

1. [Grok Bot skills and routines](https://docs.x.ai/grok-bot/skills-routines-and-automations): Eine bereits autorisierte Routine pro Bot und Zweck, mit dem richtigen Eigentümer, Prüffrequenz, Stopdatum und Quota-/Kosten-Gate; kein künstliches Verbrennen von Kontingent.
2. [Google Antigravity Scheduled Tasks](https://antigravity.google/blog/google-io-2026-feature-deep-dive): Echte geplante Tasks im App-Projekt sind von einem bloßen Goal-Text verschieden. `/schedule` kann je Oberfläche gesprächsgebunden sein. Nie zugleich mehrere Sender für dieselbe Arbeit starten.
3. [Cursor /goal und /loop](https://cursor.com/docs/agent/overview): Langfristige Ziele und kontrollierte Wiederaufnahme; [Cursor Cloud Automations](https://cursor.com/docs/cloud-agent/automations) als kostenrelevanten gesonderten Pfad behandeln.

**Erst wenn ein tatsächlich aktiver Trigger mit nächster Ausführung bestätigt wurde, gilt ein Wiederanlauf als eingerichtet.** Ein offenes Goal, eine offene GitHub-PR oder ein langer Prompt garantiert keine nächtliche Arbeit. Nach einer echten Aufgabe: Verifikation → privater Checkpoint → deduplizierter nächster Workkey. Bei fehlender neuer Arbeit bewusst `QUIESCENT_SAFE`.

**Grenze des aktuellen Nachtauftrags:** 24. Oktober 2026, 20:00 Uhr Europe/Berlin. Keine selbstständige Verlängerung, keine neuen Ausgaben, keine zweiten Writer, keine unautorisierte Veröffentlichung. Belege, Kontingente und Recovery-Dateien gehören nicht in diese öffentliche Dokumentation.

## Windows GrokBot: lokaler Relay-Dispatcher (23.10., Nacht)

Der Windows-GrokBot übernimmt ab sofort eine **lokale Stellvertreter- und Handoff-Rolle** für die Windows-Flotte, ohne eine zweite kanonische Dispatcher-/Claim-Instanz zu betreiben. Der bestehende **GrokBot Ultra Master-Dispatcher** bleibt alleinige Instanz für die übergreifende Workkey- und Freigabekoordination. Der Windows-GrokBot überträgt nicht eigenmächtig Writer-Leases und versendet keine privaten Informationen über unbestätigte Kanäle.

Die [ausführliche Windows-Relay-Regel](./WINDOWS_GROKBOT_RELAY_DISPATCHER_V1_2026-10-23.md) beschreibt private lokale Dateien für Status, Owner-Handoffs und Workkey-Sicht sowie die getrennte Zuständigkeit von Google Windows (Verifier), Cursor Windows (autorisierter Produkt-Owner), L2/Claude (CostGate/Architektur) und Mac-Master (Deduplizierung). Der Windows-Relay soll seine vorhandenen Google-Windows-Prüfbelege und CI-Watches berücksichtigen und einen **privaten** Handoff an den Mac-Dispatcher vorbereiten, statt weitere echte Laufzeitagenten zu starten.

## Ledger-Abschluss: gemeinsamer Vier-Stunden-Vertrag (23./24.10.2026)

Der [Ledger-Closeout- und 4-Stunden-Vertrag](./LEDGER_CLOSURE_4H_ENGINEERING_CONTRACT_2026-10-23.md) trennt die vier Windows-Lanes und definiert acht explizite Ledger-Abnahme-Gates. **F-C1** (Controller-Admission ohne Pflicht-Kostenprüfung), die aktuell abgewiesene `depends_on`-Kette in `LedgerEngine.submit` und die tatsächliche Integration des L2-Abhängigkeits-PR #528 bleiben offen. Weder grüne synthetische Tests noch ein offener PR berechtigen zu `LEDGER_DONE=VERIFIED`.

Auftrag bis spätestens **24.10.2026, 03:35 Europe/Berlin**: GrokBot Windows koordiniert; Google Windows oben wacht CI; Cursor Windows arbeitet nur im gültigen Writer-Scope; Google Windows unten prüft unabhängig echte Negativtests. Es gelten ein schwerer Job pro Host, kein zweiter Dispatcher, keine automatischen Merge-/Kostenfreigaben und nur eine tatsächlich aktive Schedule-Routine pro identischem Zweck.

## Arbeitsprinzip: ein Sender je Sitzung

- Ein klarer **Goal + Workkey-Ledger + Checkpoint** ist besser als mehrfach identische Prompt-Queues.
- Nur **ein** aktivierter Wake-up-Mechanismus je gleichwertiger Sitzung; keine parallelen Stop-Hooks, Schedules und Glass-Duplikate.
- Bei einem neuen PR-Head, CI-Ergebnis oder wirklich offenen freigegebenen Workkey: gezielte Aufgabe starten.
- Bei unverändertem Zustand: kein künstliches Testen, keine Chat-Statusmeldung, kein zweiter Sender.
- Bereits bestandene Checks sind **Belege**, keine Aufforderung zur endlosen Wiederholung.
- Kontingente und Zeitfenster sind begrenzt; **keine 24/7- oder Fünf-Tage-Garantie** durch Prompttexte.
- Nur autorisierte vorhandene Tarife/Ressourcen nutzen; unklare Zusatzkosten blockieren.

## Datenrettung: Mac + Windows (vorsichtiges Vorgehen)

Für Recovery gilt zuerst der Erhalt der Originaldaten. **Recovery-Koordinator GR88** erstellt nur ein privates Zuständigkeitsregister und klärt, welche berechtigte Mac-/Windows-Person bzw. Agentensitzung tatsächlich Zugriff und Zustimmung besitzt.

1. Read-only Inventar betroffener Datenträger, Symptome und vorhandener Backups im privaten Scope.
2. Zustand und Beleg sichern; Original nicht mounten/beschreiben, nicht „reparieren“ oder formatieren, bevor Risiko und Einwilligung geprüft wurden.
3. Keine automatische SMART-, Repair-, `fsck`-, `chkdsk /f`-, First-Aid-, Wiederherstellungs-, Erase- oder Clone-Aktion auf beschädigten/fraglichen Originalen ohne gesondertes GO.
4. Falls sicher: SHA-256 von **bereits vorhandenen, lesbaren Kopien** vergleichen; keine fraglichen Datenträger unnötig voll auslesen.
5. Ein privater Mac-Handoff und ein privater Windows-Handoff gehen an ihre jeweiligen Owner; persönliche Dateien, Laufwerkspfade und Log-Inhalte bleiben privat.
6. Bei Hardwareausfall, Verschlüsselung oder fehlendem Backup: Risiken erklären und qualifizierte Hilfe/Images nach ausdrücklicher Zustimmung priorisieren.

Dieses öffentliche Dokument ist **kein Recovery-Auftrag und keine Autorisierung, fremde Hosts zu kontrollieren**.

## Die unumstößlichen Grenzen

```text
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
```

Bei bekannt gewordenen Zugangstoken: Validität und Exposure im zuständigen privaten Security-Prozess prüfen; berechtigte Inhaber rotieren/widerrufen sie. **Niemals Tokenwerte in Chats, Reports oder dieses öffentliche Repository kopieren.**

## Koordinator: wohin mit Ergebnissen?

**Öffentliches Orientierungspapier (dieser Link):**
[COURIER_TEAM_COORDINATION_2026-10-23.md](./COURIER_TEAM_COORDINATION_2026-10-23.md).

**Öffentliche technische Arbeitsweise:**
[COURIER_WORKING_METHOD_2026-10-23.md](./COURIER_WORKING_METHOD_2026-10-23.md).

**Operative Koordination:** ausschließlich in den bereits eingerichteten privaten, autorisierten Courier-Checkpoint-/Handoff-Bereichen. Jede Nachricht mit geheimen Daten, Recovery-Details, persönlichen Informationen oder Kontoauslastung bleibt dort. Der Dispatcher soll bei jeder Wake-up-Runde prüfen, ob dort ein konkreter neuer, genehmigter Auftrag existiert, ohne den gleichen Stand erneut zu versenden.

**Merksatz:** Nicht möglichst viele Agentenbewegungen zählen, sondern verifizierten Fortschritt — und nachts nur senden, wenn es wirklich etwas Neues gibt.
