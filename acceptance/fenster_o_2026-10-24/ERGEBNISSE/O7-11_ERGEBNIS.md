# O7-11 · B6 · Wake-Callback im Lock → Deadlock · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Gegenprobe | PR #836 Head `ad50f362a3d80501d2f3d3630d389be5ab5e0745` (lokal gefetcht, nur gelesen) |
| Testdatei | `O7-11_test_wake_callback_outside_lock.py` · sha256 `9fe84df8b80ed0182749e377093d34fce529a3992a9122176d7a151fda468598` |
| Marker | **kein xfail**, normaler Regressionstest (Begründung unten) |
| Lauf auf Basis | `1 passed`, Exit 0 |
| Lauf auf #836-Head | `1 failed`: `run_once still blocked after 5 s: wake callback ran inside the lock` |
| Kosten | 0 €, lokal |

## Befund (VERIFIED)
- **Katalog-Input `scripts/automation_wake_coalescing.py`: nicht gefunden.** Die Datei (84 Zeilen) ist eine reine Zustandsmaschine ohne Lock, ohne Callback und ohne Threads. Dort kann es keinen Deadlock geben.
- **Basis 81bbf224: nicht gefunden.** `courier_runtime/host_loop.py:58-87` (`run_once`) nimmt keinen Lock. Der Callback (`:81-85`) läuft ohne gehaltenen Lock, der Campaign-Lock der LedgerEngine (`courier_runtime/ledger_engine.py:97-125`, „Not re-entrant“, `_campaign` `:151-154`) ist frei.
- **Der Defekt steckt in PR #836 (nicht gemergt):** Auf dem Head `ad50f362a` hängt `run_once` (Signatur `…, engine=None`) nach 5 s noch. Der Callback läuft dort im nicht-reentranten Campaign-Lock. Der Fix ist übergeben: `acceptance/v34_review_2026-10-24/REV836_wake_callback_outside_lock.diff` (sha256 `2807873e…7156e`, [Kommentar auf #836](https://github.com/happyhippovip/2026-courier/pull/836#issuecomment-6381516229)).

## Warum kein strict xfail
Auf der Basis besteht der Test. Ein `xfail(strict=True)` würde dort XPASS melden und damit **rot** werden; das wäre ein falscher Befund. Deshalb liefere ich ihn als normalen Regressionstest. **C1-17:** Nichts zu entfernen. Der Test gehört mit #836 zusammen, damit #836 nur mit dem Fix grün wird.
sha256: 33306c6d436033077df59f1a41f75fef688ccaa123025c6f31f7c455e7ee9dcc
