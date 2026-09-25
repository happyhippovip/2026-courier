# Dead Code Cleanup Plan

## Beobachtung
Das Root-Verzeichnis enthält eine Vielzahl von Legacy-Patch-Skripten, darunter:
- `patch_tomato_test.py`
- `patch_tomato_test_2.py`
- `patch_tomato_test_3.py`
- `patch_tomato_test_4.py`
- `patch_retries.py`

## Analyse
Diese Skripte wurden in vergangenen Iterationen verwendet, um `app.py` oder andere Core-Dateien per String-Replace (Suchen & Ersetzen) zu modifizieren. 
Solche Skripte sind temporäre Hilfswerkzeuge ("Throw-away Code"), die nach erfolgreichem Patching und Commit ihren Nutzen verlieren.
Im aktuellen, gereiften Projekt-Zustand stellen sie "Dead Code" dar und stören die Codebase-Übersicht.

## Empfehlung (Schlafmodus-Paket)
Da im Schlafmodus keine destruktiven Aktionen (`rm`) erlaubt sind, wird empfohlen, im regulären Betrieb folgenden Aufräum-Schritt durchzuführen:
1. Sicherstellen, dass alle Änderungen, die von diesen Skripten implementiert wurden, ordnungsgemäß im aktuellen `app.py` (oder relevanten Modulen) verankert und mit Tests abgesichert sind.
2. Alle `patch_*.py` Skripte in einen separaten `archive/patches/` Ordner verschieben ODER komplett aus dem Repository löschen.

## Nächste Schritte
Bei Bestätigung durch den User (HUMAN_GATE) kann dieses Arbeitspaket als "Aufräum-Task" in die Queue aufgenommen werden.

- `apply_ledger_patch.py`
- `stack_inspector.py`
