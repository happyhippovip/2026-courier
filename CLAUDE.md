# CLAUDE.md

Dieses Repository folgt `MASTERPLAN.md`. Vor Änderungen zuerst `MASTERPLAN.md` und `docs/STATUS.md` lesen.

## Arbeitsregeln
1. Kein Beleg = kein PASS.
2. Vor Code-Aussagen Branch + voller SHA nennen; wenn nicht bekannt: UNKNOWN.
3. Keine neuen Features, solange Cannon V1 nicht eingefroren ist.
4. Keine Worker-Branches mergen ohne explizite Freigabe von Dennis.
5. Keine Geheimnisse, Tokens, Zugangsdaten, Kunden- oder Förderdaten committen.
6. Sandbox beibehalten; keine ungesicherten YOLO-Ausführungen.
7. Pro Schritt genau ein Ziel, reproduzierbarer Test, Beleg im Output.
8. Tests dürfen keine fremden Prozesse beenden.
9. Wenn drei Versuche am gleichen Problem scheitern: Zustand sichern, Belege notieren, stoppen.

## Aktuelle Priorität
**Stufe 1 – Cannon V1 fertig und einfrieren.**

Reihenfolge:
1. `pre-yolo-patch`-Basis eindeutig klären.
2. Live-Text-Fehler reproduzierbar identifizieren.
3. Tests Mac + Windows stabil grün.
4. 5er-Lauf und Endlos-Lauf auswerten.
5. Freeze-Vorlage erstellen: Tag `courier-cannon-v1`, Bundle, Push-Entscheidung durch Dennis.

## Ausgabeformat für jeden Arbeitsblock
- STATUS: BELEGT | BEHAUPTET | VERMUTET | UNKNOWN
- BRANCH:
- SHA:
- GEÄNDERT:
- TEST:
- BELEG:
- NÄCHSTER EINZELNER SCHRITT:
