# O7-03 · B2 Single Writer · zwei Writer gleichzeitig auf work_queue · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-03_test_two_writers_work_queue.py` · sha256 `c6773a9f03f0f0696b4e15c57da6c0c01d28383d1c345cf3ee9ab18b871d1ff8` |
| Marker | 1 × `xfail(strict=True, raises=AssertionError)` + 1 Schutztest (20 Rennen) |
| Lauf auf Basis | `1 passed, 1 xfailed`, Exit 0; mit `--runxfail`: `assert 2 == 1`; beide Writer erhalten `status: CLAIMED` |
| Kosten | 0 €, nur Dateien in tmp |

## Befund (VERIFIED)
- **Kein Defekt beim Lock (nicht gefunden):** Zwei *verschiedene* Holder, die per Barrier gleichzeitig starten, ergeben in 20 von 20 Rennen genau eine CLAIM-Zeile und einmal `DUPLICATE_CLAIM`. Belegt durch `courier_core/work_queue.py:242-279` (flock/msvcrt) und den Neuprüfungsschritt unter Lock bei `work_queue.py:98-104`.
- **Echter Defekt:** Bei `courier_core/work_queue.py:101-103`
  ```python
  if _held(current, moment):
      if current["lease"]["holder"] == holder:
          return _claim_view(current, idempotent=True)
  ```
  wird nur der Holder-String verglichen, **nicht der Host**. Zwei Writer auf verschiedenen Hosts mit gleichem Holder-Namen (z. B. ein kopiertes `work_queue_feed.json`, `courier_worker/queue_feed.py:93`) bekommen beide einen erfolgreichen Claim. Der zweite erhält eine Lease, deren `host` auf den ersten zeigt. `queue_feed.feed_once` prüft das Ergebnis von `claim` nicht (`queue_feed.py:139`), und `renew` (`work_queue.py:141`) vergleicht ebenfalls nur den Holder. Ergebnis: **zwei Writer, eine Lease**.

## Erwartung nach dem Fix
Bei gleichem Holder und anderem Host gibt es keinen idempotenten Erfolg mehr, sondern eine Ablehnung (z. B. `DUPLICATE_CLAIM`/`HOST_MISMATCH`). Dasselbe gilt für `renew`. Ein idempotenter Neustart auf demselben Host bleibt erlaubt.

## Hinweis
Die Holder-Eindeutigkeit ist heute nur eine Konvention. Eine erfundene Lease wird hier nicht unterstellt; der Test erzeugt beide Claims selbst in tmp.
sha256: 3105a67fcb80a8fcb1a505ccc30e98fa423462765939a64197fa445c81851dc2
