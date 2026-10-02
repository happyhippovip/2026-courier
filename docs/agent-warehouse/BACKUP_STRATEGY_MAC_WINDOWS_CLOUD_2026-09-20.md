# Backup Strategy — Mac + Windows + Cloud

Date: 2026-09-20  
Status: operational recommendation / public-safe

## Ziel

Courier soll nicht von einem einzelnen Rechner, einer einzelnen Cloud-VM oder einem einzelnen Git-Checkout abhängen.

Empfohlene Rollen:

- **GitHub** = Quellcode, öffentliche Dokumentation, versionierte Konfiguration ohne Secrets.
- **Mac Time Machine** = System-/Datei-Rollback des Macs.
- **Windows Backup-Disk** = zweite lokale/offline Kopie wichtiger Windows-Daten und Exportpakete.
- **Cloud durable storage** = produktive Daten, Events, Datenbank, Medien/Artefakte.
- **Secret Manager** = API-Keys, OAuth, Tokens, Passwörter.
- **Object Storage** = große Videos/Bilder/Archive; nicht Git.

## Time Machine

Nicht nur monatlich sichern.

Begründung: Ein Monatsabstand kann bis zu ~30 Tage Arbeit kosten. Time Machine arbeitet inkrementell; nach dem ersten Backup werden nur Änderungen gesichert.

Empfehlung:
- Time Machine **automatisch** aktiv lassen, mindestens täglich oder wöchentlich je nach Last;
- wenn die Platte nicht dauerhaft angeschlossen bleiben soll: sie **einmal pro Woche** anschließen und Backup fertig laufen lassen;
- zusätzlich **monatlich** einen bewusst geprüften Recovery-Punkt markieren/prüfen.

Damit bedeutet "monatlich" nicht "nur einmal im Monat sichern", sondern:
- laufende Time-Machine-Historie,
- plus monatliche Recovery-Kontrolle.

## 3-2-1-Zielbild

Mindestens:
- 3 Kopien wichtiger Daten,
- auf 2 unterschiedlichen Medien/Systemen,
- 1 Kopie getrennt/offsite.

Beispiel:
1. aktives Mac/Windows/Cloud-System,
2. externe Festplatte,
3. Cloud/Object Storage oder zweiter physischer Standort.

## Mac

Sichern:
- Projekte / Arbeitsdateien,
- lokale Konfiguration ohne austauschbare Caches,
- Desktop/Dokumente,
- relevante App-Daten.

Nicht als "Backup-Strategie" betrachten:
- nur lokaler Git-Checkout,
- nur Time-Machine-Lokalsnapshots,
- nur iCloud-Sync.

## Windows

Die angeschlossene Festplatte kann günstig als zweite lokale Sicherung dienen.

Empfohlenes Schema:
```
BACKUP/
  courier/
    source-export/
    config-public/
    runtime-export/
    media-manifests/
  personal/
  restore-notes/
```

Keine Secrets in Klartext-Exportpakete legen.

Mindestens monatlich:
- neue Sicherung schreiben,
- Stichprobe öffnen,
- Hash/Dateizahl prüfen.

Bei aktiv entwickeltem Projekt besser wöchentlich inkrementell.

## Cloud

Cloud ist nicht automatisch Backup.

Produktivdaten brauchen:
- Datenbank-Backups / PITR,
- Object-Storage-Versionierung oder Snapshots,
- Export der durable events,
- getesteten Restore-Prozess,
- dokumentierte Aufbewahrung.

## Monatlicher Recovery Day

Einmal pro Monat:
1. Time Machine Status prüfen.
2. Windows-Backup aktualisieren.
3. Cloud DB Backup/PITR prüfen.
4. Object-Storage-Backup/Versionierung prüfen.
5. GitHub Branch/Tags prüfen.
6. Einen kleinen Restore-Test durchführen.
7. Ergebnis als Recovery Report dokumentieren.

## Definition of Done

Backup gilt erst als vertrauenswürdig, wenn mindestens ein Restore-Test erfolgreich war.
