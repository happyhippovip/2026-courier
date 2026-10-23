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

Diese Pull Requests waren beim letzten öffentlichen Check **offen**; ihre konkreten Git-SHAs und CI-Ergebnisse sind zum Handlungszeitpunkt erneut zu prüfen:

- [#835 — H10 Claim Safety und Process Nonce](https://github.com/happyhippovip/2026-courier/pull/835).
- [#836 — Provider DONE darf Workkey nicht FINAL machen](https://github.com/happyhippovip/2026-courier/pull/836).
- [#837 — A→B→C Journal Proof](https://github.com/happyhippovip/2026-courier/pull/837).
- [#838 — exakt eine Fortsetzungsnachricht, keine Queue-Duplikate](https://github.com/happyhippovip/2026-courier/pull/838).
- [#840 — Vorschlag für wiederverwendbaren Safe-Autonomy-Modus](https://github.com/happyhippovip/2026-courier/pull/840).

PR #827 wurde bereits gemergt. Externe, ältere Receipt-Patches gegen frühere HEADs dürfen deshalb nicht blind angewandt werden: zuerst Diff- und Konfliktvergleich, dann isolierte Neuprüfung. PR #834 wurde gemergt. Status weiterer PRs immer aktuell prüfen.

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
