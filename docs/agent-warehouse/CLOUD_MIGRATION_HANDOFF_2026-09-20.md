# Cloud Migration Handoff / Kauf- und Übertragungscheckliste

Date: 2026-09-20  
Status: provider-neutral pre-purchase checklist

## Ziel

Vor dem Kauf eines Cloud-Pakets soll klar sein, **was wirklich in die Cloud muss**, was lokal bleiben kann und welche Daten nicht einfach in ein öffentliches Repo oder unverschlüsseltes Storage gehören.

## 1. Datenklassen

### A — Public code/docs
Darf in das öffentliche GitHub-Repo:
- Produktcode, soweit bewusst Open/Public;
- öffentliche Dokumentation;
- öffentliche Marketing-/Branding-Unterlagen;
- public-safe Schemas.

### B — Private application state
Nur private DB/Object Storage:
- Kundenziele;
- Tasks;
- Resultate;
- private Knowledge Records;
- Mail-/Archivindex;
- Kundenprojekte;
- interne Agentenprotokolle.

### C — Secrets
Nur Secret Manager:
- API keys;
- OAuth client secrets;
- refresh tokens;
- signing keys;
- DB passwords;
- SMTP credentials;
- payment/webhook secrets.

### D — Large media
Object Storage:
- Video;
- Bilder;
- Audio;
- Build-Artefakte;
- Exportpakete;
- große Archive.

Git ist dafür nicht das Primärlager.

## 2. Cloud-Bausteine, die verglichen werden müssen

Vor Kauf Anbieter/Plan gegen diese Matrix prüfen:

- Linux compute / container support
- RAM/CPU limits
- persistent disk
- managed PostgreSQL
- pgvector oder Vektor-Suche
- S3-kompatibles Object Storage
- backups + point-in-time recovery
- outbound network rules
- secrets manager
- TLS / custom domains
- CDN
- job/queue worker support
- scheduled jobs
- observability/logging
- egress cost
- storage cost
- database cost
- API gateway / rate limiting
- EU/Germany region falls erforderlich
- DPA / GDPR-Unterlagen
- scaling limits
- exportability / vendor exit

## 3. Empfohlene logische Zielarchitektur

```
Web / API
  |
  +-- PostgreSQL
  |     +-- tenants
  |     +-- goals
  |     +-- tasks
  |     +-- durable results
  |     +-- knowledge metadata
  |
  +-- Vector index / pgvector
  |
  +-- Object Storage
  |     +-- media
  |     +-- artifacts
  |     +-- exports
  |
  +-- Worker Queue
  |     +-- agent jobs
  |     +-- content production
  |
  +-- Secret Manager
  |
  +-- Backup / Audit / Metrics
```

## 4. Migration Order

1. Freeze schema/version.
2. Create full backup.
3. Test restore **before** cutover.
4. Provision DB.
5. Provision Object Storage.
6. Configure secrets separately.
7. Deploy read-only/staging app.
8. Import sanitized test data.
9. Run end-to-end tests.
10. Import production data.
11. Verify counts/hashes.
12. Switch traffic.
13. Keep rollback window.
14. Only later retire old environment.

## 5. Agent Warehouse Mapping

Agenten sollen nach Cloud-Umzug nicht lose Ordner suchen.

Vorgeschlagene Datenobjekte:
- Goal
- WorkPlan
- Task
- WorkerCapability
- DurableResult
- Artifact
- KnowledgeRecord
- Source
- Approval
- AuditEvent
- CostEvent
- ArchiveItem
- ConversationReference

## 6. Mail/Archive

Mail und Archive brauchen vor Migration:
- eindeutige owner/tenant IDs;
- source system;
- message/document ID;
- timestamp;
- permissions;
- retention;
- search index;
- raw-object pointer;
- extracted text;
- deletion/export workflow.

Keine privaten Mailbox-Inhalte in GitHub committen.

## 7. Abgleich vor Cloud-Kauf

Für jeden angebotenen Plan diese Werte eintragen:

| Punkt | Anbieter/Plan | Wert | ausreichend? |
|---|---|---|---|
| Region | | | |
| Compute | | | |
| RAM | | | |
| PostgreSQL | | | |
| Vector Search | | | |
| Object Storage | | | |
| Backup/PITR | | | |
| Secrets | | | |
| Egress | | | |
| monatlicher Mindestpreis | | | |
| Skalierung | | | |
| Export/Exit | | | |

## 8. Definition of Done für Umzug

Cloud-Umzug ist erst abgeschlossen, wenn:
- Restore getestet;
- kein Secret im Repo;
- Task-/Result-Zahlen stimmen;
- Medien erreichbar;
- Knowledge-Suche funktioniert;
- Agenten-Queue funktioniert;
- Audit/Event-Historie erhalten;
- Domain/TLS funktioniert;
- Monitoring aktiv;
- Rollback dokumentiert.
