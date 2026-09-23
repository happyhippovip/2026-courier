# Courier Symphony – STATUS

Stand: 23.09.2026

## Aktuelle Stufe
**Stufe 1 – Cannon V1 fertig und einfrieren**

## Bekannter Stand
- `pre-yolo-patch(-v2)` = `49150d3f`
- `yolo-patch-applied-v2` = `e98ce2cc`
- Offene Frage: Welche Referenz ist die offizielle Vergleichsbasis?
- Live-Text-Fehler: UNKNOWN, genauer Fehler noch zu belegen.
- Ziel: Tests auf Mac und Windows stabil grün.
- Danach: 5er-Lauf + Auswertung des Endlos-Laufs.
- Freeze-Ziel: Tag `courier-cannon-v1` + Bundle.

## Abnahmekriterien Cannon V1
- Mac: belegter Lauf
- Windows: belegter Lauf
- `result_id == voller Commit-Hash`
- `DUPLICATE_EXECUTIONS = 0`
- `LOST_RESULTS = 0`
- Notaus < 15 Sekunden

## Update-Regel
Nur belegte Zustände als BELEGT markieren. Alles andere ausdrücklich als BEHAUPTET, VERMUTET oder UNKNOWN kennzeichnen.

## Nächster einzelner Schritt
Die offizielle Basis für `pre-yolo-patch` klären und mit Branch + SHA belegen.
