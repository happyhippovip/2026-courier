# Freeze-Plan Cannon V1

Stand: 23.09.2026

## Aktueller Zustand
- Windows-Lauf: Status muss verifiziert werden (vermutlich lauffähig, aber Tests haben harte Asserts).
- Mac-Lauf: Path-Separatoren (`\`) in `core-source-manifest.json` und macOS Caching in `resource_state()` blockierten Starts. Diese sind lokal gepatcht (`agent/mac-cannon-v1-fixes`).
- Weitere Unit-Tests in `test_cannon.py` schlagen fehl wegen V0-Dauerlauf-Schutz (`mode != 'NORMAL'`) und fehlender Mac-Prozessidentität (`creation_filetime = None`).

## Nächste Schritte zum Freeze
1. **Test-Stabilität (Mac & Windows)**:
   - `test_cannon.py` anpassen: Asserts für `creation_filetime` bei POSIX lockern.
   - Test-Aufrufe mit `mode='TURBO TEST'` umgehen oder den V0-Schutz im Test mocken.
2. **Review & Merge**:
   - Die minimalen Fixes aus `agent/mac-cannon-v1-fixes` reviewen und in den Release-Candidate mergen.
3. **Physischer Abnahmelauf**:
   - 5er-Lauf auf Mac und Windows durchführen.
   - `result_id == voller Commit-Hash` prüfen.
   - Sicherstellen, dass `DUPLICATE_EXECUTIONS = 0` und `LOST_RESULTS = 0`.
4. **Tagging**:
   - Bei Erfolg Branch einfrieren und Tag `courier-cannon-v1` setzen.
