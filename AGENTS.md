# AGENTS.md

Repository-weite Regeln für Code-Agenten.

- `MASTERPLAN.md` ist die kanonische Roadmap.
- `docs/STATUS.md` ist der laufende technische Zustand.
- Aktuelle Stufe: **Cannon V1 einfrieren**.
- Kein neues Feature vor Abschluss dieser Stufe.
- Kein Beleg = kein PASS.
- Vor Code-Aussagen Branch + SHA nennen oder UNKNOWN.
- Keine Secrets, Tokens, Kundendaten oder Förderdaten ins Repo.
- Keine Merges, Veröffentlichungen oder kostenwirksamen Aktionen ohne Freigabe von Dennis.
- Sandbox verwenden; keine ungesicherten YOLO-Modi.
- Ein Agent bearbeitet eine klar abgegrenzte Aufgabe.
- Nach Änderungen: Tests ausführen und reproduzierbaren Beleg liefern.
- Keine Tests, die fremde Prozesse abschießen.
- Bei drei Fehlschlägen am selben Problem: stoppen, Zustand und Belege dokumentieren.

Priorität:
1. Basis-Referenz klären.
2. Live-Text-Fehler klären.
3. Tests grün.
4. 5er-Lauf / Endlos-Lauf.
5. Freeze Cannon V1.
