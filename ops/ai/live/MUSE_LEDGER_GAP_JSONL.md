# Ledger-Gap: jsonl-Export unvollständig (db intakt)

MODE=READ_ONLY | BASE=e11749b6 | LEDGER_WRITES=0 (Owner-Tooling aktiv:
repair_bak + migrated-Backups von heute Nacht — kein Eingriff)

## Befund (NEU, read-only verifiziert)
- wall_ledger/ledger.db: 683 Zeilen, Kette 0 Breaks (id-order).
- wall_ledger/ledger.jsonl: 667 Zeilen, 2 Ketten-Breaks:
  (1) Z.617 HNI_01 nach MAC_HNI_06, (2) Tip Z.667 MAC_HNI_23.
- Ursache: jsonl fehlen exakt MAC_HNI_07..22 (16 Fingerprints, alle in db,
  0 Fingerprints nur in jsonl). db ist striktes Superset; beide Breaks
  zeigen auf existierende db-Blöcke (MAC_HNI_20, MAC_HNI_22).
- Kein Fork, keine Korruption, kein Datenverlust in der Wahrheit (db).

## Was fehlt / NEXT (Ledger-Owner)
- jsonl-Re-Export aus db (oder Export-Pfad reparieren: schreibt offenbar
  nur einen Stream / Stand vor Repair+Migrate).
- Bis dahin: Kette NUR gegen db prüfen; jsonl-Kettenprüfung meldet
  falsch-positive Breaks an genau diesen 2 Stellen.
- Finish-Gates unverändert extern: Windows-Writer-Commit (OPEN),
  Codex-Review (BLOCKED) — Ledger-intern ist nichts mehr offen.

DO_NOT_REPEAT_FINGERPRINT=museledger-gap-jsonl-16rows-db683
