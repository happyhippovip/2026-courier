# M3 — LOCAL_DIFF_FALSE_GREEN (Muse 3)

Stand: 2026-09-28, Quelle: Repo-Reads (Abgleich, KEINE Revalidierung)

## USER_PROBLEM (Operator-Sicht)
Mehrere Dokumente sagen gleichzeitig GREEN/READY — aber mit verschiedenen Zahlen
und widerspruechlichen Details. Welche Aussage gilt, welche ist false-green?

## CURRENT_RUNTIME_TRUTH (belegt, nur gelesen, nichts neu gemessen)
- M3-1 Zaehlen: GATE sagt 57 Tests / 1 skipped / 0 failed; HANDOFF sagt
  "51 targeted assertions GREEN", SKIPPED_COUNT 0. Das sind verschiedene
  Einheiten (Tests vs Assertions) UND verschiedene Boundaries — beide stehen
  als jeweils "GREEN" da, ohne dass die Differenz erklaert wird.
- M3-2 `git diff --check`: HANDOFF sagt PASSED ("whitespace resolved locally",
  `:35-37`); GATE sagt WHITESPACE_ONLY (40 Zeilen). Widerspruch, zeitliche
  Ordnung aus den Dateien NICHT ableitbar (kein Datum) → UNGELOEST, kein Urteil.
- M3-3 Scope: SCOPE_CHECK sagt `SCOPE_OK=NO` (Extra `tests/test_integration_contract.py`);
  PROOF_CARD-Scope listet 5 Dateien (ohne sie); HANDOFF Changed-Files listet 6
  (mit ihr). Die Datei ist gleichzeitig Scope-Verletzung und Evidenz-Bestandteil.
- M3-4 Externe Pfade: 12/12 PROVEN verweisen auf `c:\Users\lol\courier_work\...`
  (ausserhalb Repo, HANDOFF `:16-27`) → EXTERNAL_UNVERIFIED (vgl. UA-D01).
- M3-5 Fingerprints: PROOF_CARD nennt 5 SHA256 (`:41-45`). Pruefbar im Prinzip
  (lesen + hashen), aber Hashen braucht Ausfuehrung → von hier UNGEPRUEFT,
  Check benannt, nicht behauptet.

## VERDIKT
M3-CLOSED als Inventar: 1 Einheiten-Verwirrung (M3-1), 1 offener Widerspruch
(M3-2, unloesbar ohne Datum/Lauf), 1 Regel-Konflikt (M3-3), 1 extern-unverifiziert
(M3-4, vgl. UA-D01), 1 offener Check (M3-5). Kein False-Green-Urteil gefaellt —
das waere Revalidierung. Aber: "alles green" ist als Gesamt-Aussage IRREFUEHREND,
solange M3-1..M3-3 nebeneinander stehen.

## ACCEPTANCE_REQUIREMENT
M3.1: EINE Zahlentabelle: `Suite | Einheit (Tests/Assertions) | passed/skipped/
failed | Datum | Quelle`. Keine zwei GREENs ohne diese Zeile.
M3.2: Widersprueche werden als `CONTRADICTION_OPEN` markiert, nicht gemittelt.

## MISSING_SYSTEM_SUPPORT
- Kein Zahlen-Cache mit Datum/Quelle; keine Kontradiktions-Markierung.

## PREPARABLE_NOW
- Dieses Inventar + Tabellen-Schema M3.1 (ausfuellbar ohne einen Lauf).

## BLOCKED_UNTIL
- Datierte Primar-Reports (fremde Lane) fuer M3-2; Scope-Regel-Entscheid fuer M3-3.

## NEXT
M4 (Replay-Identitaet) — M3 liefert: Zahlen misstrauen, Mechanik pruefen.
