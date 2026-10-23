# Courier Symphony — Windows GrokBot Relay Dispatcher V1
**Öffentliche Teamregel · 23.10.2026 · Koordination, keine Ausführungsfreigabe**

> Diese Anweisung dokumentiert Zuständigkeiten. Sie startet weder einen Bot noch eine Automation, erteilt keine Writer-Lease und ersetzt keine private kanonische Projektregel.

## Architektur: ein Master, ein Windows-Relay

- **GrokBot Ultra / bestehender Master-Dispatcher:** Kanonische, übergreifende Workkey-, Owner-, Lease- und L1-Entscheidungskoordination. Kein zweiter Claim-/Queue-Store.
- **GrokBot auf Windows / GR88-Relay:** Lokaler stellvertretender Windows-Dispatcher für Zusammenfassung, Statusbelege, private Übergaben und gezielte Eskalation. Er darf **keine zweite autoritative Dispatcher-Instanz** und keine Worker-/Controller-Schreibrechte erzeugen.
- **Google Antigravity Windows:** Unabhängige Tests, CI-Watch und L2-/L3-Regressionen, nicht produktiver Writer.
- **Cursor Windows / L3- und Windows-Worker-Owner:** Implementiert nur mit exklusiv gültiger Dateilease; verantwortet RESULT_READY, ACK, Heartbeat, StopLoop und Ledger/Lock-Grenzen im jeweils autorisierten Scope.
- **Mac-Architektur-/Koordinator:** Empfängt genau eine deduplizierte private Windows-Übergabe, erkennt gleiche Workkeys und weist nicht parallel denselben Task zu.
- **L1 und Claude/L2:** Human Gates, Architektur- und CostGate-Entscheidungen; kein stillschweigender Merge.

## Windows-Eingang und lokale Handoffs

Das **Windows-GrokBot-Relay** legt in einem vom Benutzer bereits autorisierten privaten Desktop-Projektordner (sofern lokal vorhanden und beschreibbar) ein separates Windows-Unterverzeichnis mit:
1. einem datierten `WINDOWS_DISPATCHER_STATUS.md` einschließlich UTC-/Berlin-Zeit, GitHub-SHAs, CI-Zustand, aktiven Agenten/Schedulern und nächsten berechtigten Schritten;
2. einem `WINDOWS_OWNER_HANDOFFS.md` mit je einem Hand-off an L1, L2/Claude, L3/Windows, Receipt-Owner und den Mac-Master, inklusive Beleg-IDs und ausdrücklich offener Entscheidungen;
3. einem `WINDOWS_WORKKEY_INBOX.md` als **nicht-autoritative Sicht** auf vorhandene kanonische Workkeys. Fingerprint, Owner, Scope, Quelle, Gate und Status dokumentieren; ohne Freigabe keine neuen Produkt-Writer-Workkeys ausgeben.

Vorhandene private Dateien niemals überschreiben; sie versionieren oder datierte Checkpoints erstellen. Dateizugriff selbst nachweisen. Öffentliches GitHub bekommt nur diese **abstrahierte Rollenregel**, keine Windows-Pfade, Kontoinformationen, Recoverys, Logs, Tokens oder privaten Workkey-Payloads.

## Laufende technische Übergaben

- **PR #836:** Provider-DONE/FINAL, stale Host-Loop-Stand sowie Journal-Proof-Bindung. Der aktuelle Head muss beim Lauf neu gelesen werden; frühere Tests belegen nicht automatisch neue Commits.
- **PR #837:** synthetische A→B→C-Journal-Evidenz von echter Workkey-Abhängigkeit und CostGate-Admission unterscheiden.
- **PR #842/#844:** Tests auf Falschgrün prüfen und tatsächliche Produktpfade von Testlokalsimulationen unterscheiden. Kein grüner Job ist allein eine reale Provider-Abnahme.
- **PR #843:** Test-only CPU-pressure-Isolation für den Windows-Delivery-Test; keine damit behauptete Produktionskorrektur von `daemon.py`.
- **F-C1:** Direkte `Controller.create_task`-Admission mit fehlender Kostenprüfung erfordert L2-Entscheidung; unbekannte Kosten bleiben blockiert.
- **`daemon.py` Owner:** bestehenden Eigentümer und konkurrierende Branches prüfen, keinen neuen Writer behaupten.
- **Receipt und veröffentlichte Eigentümer-Token:** Reproduktionsbelege privat an Sicherheitsowner, gültige Tokens von Berechtigten widerrufen/rotieren lassen, Werte niemals speichern oder mitteilen.

## Event-/Statusverfahren

1. Vorhandene Scheduler auf Windows inventarisieren; keine doppelten Timer, keinen neuen kostenpflichtigen Agenten.
2. Mac-Master-Handoff zuerst auf Duplikate prüfen; nur neuere Sha-/CI-/Test-/Lease-Ereignisse verarbeiten.
3. Isolierte Read-only-Prüfung innerhalb des autorisierten Bereichs ist zulässig; keine fremden Datei- oder Produktmutationen.
4. Bei Abschluss einen privaten Checkpoint und genau ein eigenes Übergabepaket an den bestehenden Mac-Master vorbereiten. Versand nur über bereits autorisierten, überprüften Kanal; sonst `READY_TO_SEND`.
5. Bei unverändertem Zustand `QUIESCENT_SAFE`, nach Möglichkeit ohne Chat-Rückmeldung.
6. Quelle und Wahrheitsstatus je Feststellung angeben: `GITHUB_VERIFIED`, `LOCAL_REPORTED`, `INDEPENDENT_REPRODUCED`, `UNCONFIRMED`, `BLOCKED`.

## Unveränderte Sicherheitsgrenzen

```text
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
```

**Endgrenze des aktuellen Nachtauftrags:** 24.10.2026, 20:00 Europe/Berlin; keine automatische Verlängerung, es sei denn der kanonische Owner autorisiert einen neuen Zeitrahmen.
