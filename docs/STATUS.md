# Courier Symphony – STATUS

Stand: 23.09.2026

## Aktuelle Stufe
**Stufe 1 – Cannon V1 fertig und einfrieren**

## Bekannter Stand
- `pre-yolo-patch` = `a0a959d7e6972c88348ac3732c2ebe53fa85e626` (Branch: `candidate/local-lazy-infinite-2026-09-19`, via Git Tag)
- `yolo-patch-applied` = `b8135b05f310f2821bf50f4c79c81127253636da` (Branch: `candidate/local-lazy-infinite-2026-09-19`, via Git Tag)
- Klärung: Die in einer früheren Version notierten SHAs (`49150d3f` und `e98ce2cc`) existieren in diesem Repository nicht. Die offizielle Vergleichsbasis ist der Tag `pre-yolo-patch` auf dem Branch `candidate/local-lazy-infinite-2026-09-19`.
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
(Erledigt: Offizielle Basis für pre-yolo-patch geklärt). Nächster Schritt: Cannon V1 Mac-Lauf auf Basis von `pre-yolo-patch` ausführen und Fehlerbild belegen.
