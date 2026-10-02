# Cloud Reactivation Runbook

Date: 2026-09-20  
Status: safe reactivation handoff

## Was im Repository bereits belegt ist

### External Linux Courier deployment

`deploy/README.md` beschreibt einen Linux-Deployment-Wrapper um den autonomen Supervisor.

Wichtige Eigenschaften:
- Code-Checkout unter `/opt/courier` ist ersetzbar.
- Durable Event-/Queue-Daten liegen unter `/var/lib/courier/events`.
- Worker/Provider-Konfiguration gehört in `/etc/courier`.
- Credentials sollen **nicht** in den Checkout.
- Der Dienst soll fail-closed bleiben, wenn Ziel-Agenten nicht ausdrücklich erlaubt sind.

### Content production pipeline

`scripts/run_content_production_pipeline.py` beschreibt:
- FruitKI YouTube: IDEA -> SCRIPT -> ASSET_SELECTION -> VIDEO_BUILD -> REVIEW -> METADATA -> READY_TO_PUBLISH
- 3D-KI TikTok: IDEA -> HOOK -> SCRIPT -> 3D_ASSET_OR_SCENE -> VERTICAL_VIDEO_BUILD -> REVIEW -> CAPTION_HASHTAGS -> READY_TO_PUBLISH
- Stage-Level-Deduplizierung
- technische Review
- Publish-Paket nur nach Voraussetzungen

Aber: Der aktuelle Code referenziert lokale Mac-Pfade für Godot. Deshalb darf ein Agent nicht automatisch behaupten, dass **dieser konkrete Content-Runner** bereits vollständig cloud-native ist.

## Sichere Reaktivierung

Wenn die frühere Cloud wieder aktiviert wird:

### Phase 1 — Read only inventory

Nur lesen:
- Host/Provider/Region
- OS
- laufende Services
- Git commit/branch
- `/opt/courier`
- `/var/lib/courier/events`
- `/etc/courier` (nur Dateinamen/Rechte, keine Secret-Ausgabe)
- systemd Status
- Disk/RAM
- letzte Logs
- letzte Queue-/Result-Zeit

Keine Jobs starten.

### Phase 2 — Backup before activation

Vor Start:
- Snapshot/Backup der VM oder Disk,
- Backup durable events,
- DB/Object Storage falls vorhanden,
- aktuelle Git-Revision notieren.

### Phase 3 — Configuration comparison

Vergleichen:
- Cloud-Branch gegen aktuelles GitHub;
- erlaubte Ziel-Agenten;
- Worker/Provider;
- Pfade;
- Ports;
- Secrets vorhanden aber nicht ausgeben;
- alte Autostarts/cron/systemd units.

### Phase 4 — Dry health

Nur Health/Status:
- Dienst nicht doppelt starten;
- keine Publisher;
- keine externen Side Effects;
- Queue prüfen.

### Phase 5 — One bounded canary

Erst danach:
- genau ein ungefährlicher, klar belegbarer Canary;
- Ergebnis persistieren;
- verifizieren;
- keine automatische Serienarbeit, bis Canary grün.

### Phase 6 — Restore automation

Nur wenn Canary grün:
- vorherige Cloud-Automation schrittweise wieder aktivieren;
- Publishing-Gates erhalten;
- Budget/Rate-Limits setzen;
- Monitoring + Alarmierung aktivieren.

## Rückmeldung, die ein Agent liefern soll

```
CLOUD_HOST=
CLOUD_PROVIDER=
REGION=
OS=
COURIER_BRANCH=
COURIER_COMMIT=
SERVICE_STATUS=
DURABLE_STATE_PATH=
DURABLE_STATE_HEALTH=
DB_PRESENT=
OBJECT_STORAGE_PRESENT=
CONTENT_PIPELINE_LOCATION=
CONTENT_PIPELINE_CLOUD_NATIVE=YES/NO/PARTIAL
PUBLISHING_GATE=
SECRETS_EXPOSED=NO
BACKUP_BEFORE_START=
CANARY_RESULT=
FIRST_BLOCKER=
```

## Abbruchbedingungen

Nicht reaktivieren wenn:
- durable state unklar,
- Git-Version unklar,
- Secrets fehlen/öffentlich sind,
- möglicher aktiver Publish-Job unklar,
- DB/Media-Backup fehlt,
- mehrere konkurrierende Worker laufen,
- Kosten-/Budgetgrenze nicht festgelegt ist.
