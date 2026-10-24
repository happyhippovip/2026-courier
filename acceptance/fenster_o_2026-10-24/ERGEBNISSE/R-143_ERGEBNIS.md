# R-143 · Ops `ops/ai/BUGFIX_EVIDENCE_2026-09-28.md` · FENSTER O
Basis `81bbf224`, nur gelesen. sha256 `5cc97849bb632c773f7e235d2882095c7295d829bddd373300053b4028c08020`, 13 Zeilen.

| Aussage | Zeile | Urteil | Beleg |
|---|---|---|---|
| BUG 2: Verifier scheitert an Ziel-Liste, „repariert“ in `courier_verifier.py` | 3-6 | **teilweise**: Ergebnis ja, Weg anders | `scripts/courier_verifier.py:91-92`: `str(...)` plus Teilstring-Suche `any(t in target …)`. Eine Liste `["python","windows"]` wird damit erkannt, aber über den String `"['python', 'windows']"` und nicht durch die beschriebene Listen-Erkennung. Teilstring-Treffer sind locker (`"windows"` matcht jeden String, der `windows` enthält) |
| BUG 3: `ACK_DUPLICATE` scheitert bei `artifacts` None vs. `[]`, „repariert“ in `server/app.py` | 8-11 | **WIDERSPRUCH: auf Trunk nicht vorhanden** | `server/app.py:529` vergleicht `stored.get("artifacts") == data.get("artifacts")` roh. Ein `sort_artifacts`/`[]`-Normalisierer existiert nicht (grep leer). `None` vs. `[]` führt also weiterhin zu 409 statt ACK_DUPLICATE. Hinweis: `server/app.py` ist laut V4 „nie anfassen“; nur gemeldet |
| Kosten / PAYG | – | **nicht gefunden** | |

**Liste für Dennis:** BUG 3 ist als „Repaired locally“ dokumentiert, aber nie im Trunk gelandet. Für B5 (Replay/Idempotenz) relevant, weil ein legitimer Duplikat-Result abgelehnt wird.
sha256: e18ed6129e97daa858c06a0b40042df0fc0a645fb24653f0380bc737e7302a63
