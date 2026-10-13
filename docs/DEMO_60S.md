# Courier 60-Sekunden-Demo (MOCK) – Fördertermin 26.10.2026

**Botschaft:** Ziel eingeben → Agenten arbeiten → Mensch gibt Kritisches frei → geprüftes Ergebnis mit Beleg (SHA-256).

> Die Demo läuft ausschließlich im **Mock-Modus** des Orchestrators aus PR #542
> (`courier_orchestrator`, MockWorker + unabhängiger MockPruefer).
> Kein echtes Geld, keine bezahlten Modellaufrufe, kein Netzwerk, keine Live-Systeme.
> Das Terminal zeigt das am Anfang und am Ende als Banner `DEMO / MOCK-MODUS`.

## Starten

Voraussetzung: Python 3.12 (stdlib reicht, keine Pakete).

| System | Befehl (im Repo-Ordner) |
|---|---|
| macOS / Linux | `./scripts/demo_60s.sh` |
| Windows (PowerShell) | `powershell -ExecutionPolicy Bypass -File scripts\demo_60s.ps1` |

Optionen: `--goal "Eigenes Ziel"`, `--interactive` (Freigabe bei NEEDS YOU per Tastatur `j`),
`--fast` (ohne Pausen), `--no-color`, `--out <ordner>`.
Laufzeit mit Pausen: ca. 37 s. Beleg: `demo_out/demo_60s_evidence.json` + `.sha256`
(deterministisch: gleicher Lauf → gleicher Hash).

## Phasen auf dem Bildschirm

1. **GOAL** – Ziel, Mock-Budget, drei Aufgaben (Spezifikation, HTML-Entwurf, Testplan).
2. **WORKING** – Agenten liefern; der unabhängige Prüfer lehnt einen schlechten Entwurf ab, zweiter Versuch geht durch. Nur geprüfte Ergebnisse werden geschrieben.
3. **NEEDS YOU** – T3 will „publication“ auslösen → nur ein Mensch darf das freigeben (in der Demo simuliert, mit `--interactive` live).
4. **DONE** – 3/3 geprüfte Ergebnisse, Mock-Kosten, Pfad zum Beleg und SHA-256.

## Bildschirmaufnahme

**Vorbereitung (beide Systeme):** Terminal ca. **100×30 Zeichen**, Schrift 18–20 pt,
dunkles Theme, Fenster auf **1280×720** bzw. 1920×1080 (16:9). Benachrichtigungen aus
(macOS: Fokus „Nicht stören“, Windows: „Benachrichtigungen nicht stören“). Einmal `--fast`
als Probelauf, dann `clear`.

**macOS:** `Cmd+Shift+5` → „Ausgewählten Bereich aufnehmen“ (oder Fenster) → Rahmen um das
Terminal → *Optionen*: Speicherort Schreibtisch, Mikrofon nach Bedarf → „Aufnehmen“ →
`./scripts/demo_60s.sh` → nach dem DONE-Banner 2 s warten → Stopp-Symbol in der Menüleiste
(oder `Cmd+Ctrl+Esc`). Ergebnis: `.mov`.

**Windows:** Terminal-Fenster aktiv machen → `Win+Alt+R` (Xbox Game Bar, nimmt das aktive
Fenster auf; ggf. erst unter *Einstellungen → Spielen → Captures* aktivieren, `Win+G` öffnet
die Game Bar) → `scripts\demo_60s.ps1` starten → nach DONE `Win+Alt+R` erneut zum Stoppen.
Ergebnis: `.mp4` unter *Videos\Captures*.

**Ablauf (≤ 60 s):** 0–5 s Banner + GOAL · 5–20 s WORKING (Ablehnung + Wiederholung
kommentieren: „Kein Ergebnis zählt ohne unabhängige Prüfung“) · 20–27 s NEEDS YOU
(„Geld, Veröffentlichung, Löschen – entscheidet immer der Mensch“) · 27–37 s DONE + Hash
(„Jedes Ergebnis hat einen Beleg“) · Rest: Puffer/Schlusssatz.

## Test

`python3.12 -m pytest tests/orchestrator/test_demo_60s.py` – prüft Determinismus, alle vier
Phasen, Mock-Banner, Beleg + Hash, Laufzeit < 60 s.

## Statusanzeige (statische HTML, optional)

Eine einzelne HTML-Datei ohne JavaScript, ohne externe Ressourcen, ohne Server und ohne Pakete
(kein Node). Sie zeigt GOAL / WORKING / NEEDS YOU / DONE als große Kacheln; NEEDS YOU ist orange
hervorgehoben mit Grund (z. B. `T3: publication`), oben und unten ein gelbes MOCK-Banner, darunter
der SHA-256 des Belegs.

- Zusammen mit der Demo: `./scripts/demo_60s.sh --html` (Windows: `scripts\demo_60s.ps1 --html`)
  → `demo_out/needs_you_view.html`
- Aus einem vorhandenen Beleg: `python3 scripts/demo_view.py demo_out/demo_60s_evidence.json -o demo_out/needs_you_view.html`
- Öffnen per Doppelklick im Browser. Für die Aufnahme: nach dem DONE im Terminal zur
  Browser-Seite wechseln (macOS `Cmd+Tab`, Windows `Alt+Tab`) und 3–5 s auf der NEEDS-YOU-Kachel bleiben.

Quelle ist der Demo-Beleg; `courier_worker/queue_feed.py` (needs_you.jsonl) ist in diesem Branch
nicht vorhanden. Die Ausgabe ist deterministisch (Test: `tests/orchestrator/test_demo_view.py`).
