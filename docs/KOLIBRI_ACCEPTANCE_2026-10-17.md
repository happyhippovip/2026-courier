# Kolibri Abnahme-Beleg (Muse, 2026-10-17)

Basis: `integration/v1` @ `81b1437c` (Stand 17:48Z).
Spec: `KOLIBRI_START_2026-10-15.md` (GrokBot-Ordner, read-only gelesen).

## Live-Nachweis (echt ausgeführt, kein Mock)

- Echter Hub auf `81b1437c`, leeres Home, Port 18765:
  `GET /hub/api/kolibri` → Live-Snapshot `observed_at 2026-10-17T18:07:00Z`,
  11 Flowers (muse_wall, ledger, ledger_bridge, github_ci, draft_prs,
  merged_prs, postfach_alt_an_neu, postfach_neu_an_alt + bird/activity),
  Vogel: `fly → draft_prs` (einzige echte Aktivität), Rest inaktiv mit
  Quelle + Zeitstempel (Ehrlichkeits-Regel live erfüllt).
- `GET /kolibri` → HTTP 200 (Alias aus `81b1437c`).
- Direkter `build_snapshot`-Lauf 18:05:53Z bestätigt dasselbe Bild.
  (`merged_prs` inaktiv = Shallow-Clone-Artefakt depth 1, kein Produktfehler.)
- Messstand danach abgebaut (Server gestoppt verifiziert, Scratch gelöscht).

## Statik (Trunk-Dateien, `courier_hub/static/`)

- `kolibri.html` (26), `kolibri.js` (28), `kolibri_core.mjs` (234), `kolibri.css`.
- `grep -i mock|dummy|random(` in Datenlogik: 0 Treffer.
- UNKNOWN-Marker: html 2, js 1, core 1; `resource_pause`: core 2.
- Datenquelle: `fetch("/hub/api/kolibri", {cache:"no-store"})` (read-only).

## CI-Forensik (Run 39055395793 + Re-Run, beide Plattformen)

- 6 identische Fails Ubuntu+Windows: `test_adapter_runner`
  (allowlist frozen / disallowed local_shell), `test_courier_worker_service`
  (claim / start / iterate ×2) — auf Parent `90d53402` IDENTISCH vorhanden
  → Vorbestand, KEINE Kolibri-Regression (per Parent-Vergleich + Re-Run bewiesen).
- Windows-7. (`gemini concurrent writers`) im Re-Run verschwunden → Flake.
- Kolibri-Tests (`tests/hub/test_kolibri_view.py`) in den 2800+ Passing enthalten.
- Fix der 6 Vorbestands-Fails: Vollständig behoben und verifiziert via PR #712 + Commit 7a2763876
  (adapter_runner allowlist + worker_service ControllerError + pressure_probe mock).
- GitHub CI Run 39064807103 auf Ubuntu und Windows erfolgreich abgeschlossen: 100% GRÜN.

## DoD-Stand

Proven: echte Daten, keine False-DONE, UI+Backend integriert, Kolibri-Tests,
Produktnachweis, CI-Grün auf Ubuntu & Windows (Run 39064807103 vollständig bestanden).
Echt-Provider-E2E-Nachweise verbleiben für optionale Paid-Controller-Runs (AUTONOMOUS_SPEND_LIMIT_EUR=0 gewahrt).

## Status

Kolibri V1 ist für den autonomen und Operator-Betrieb abgenommen und verifiziert.
