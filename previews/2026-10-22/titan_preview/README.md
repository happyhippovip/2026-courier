# Kolibri TITAN Vorschau (lokal, keine Produktdatei)

Verdrahtet vorhandene Kolibri-Module, ohne geschützte Dateien zu ändern:
`kolibri_universe.mjs` (Master-Orb, Planeten, `toBeamGraph`), `kolibri_beams.mjs` (Lichtstrahlen),
`kolibri_biosphere.mjs` (Hintergrund), `evidence_badge.mjs` (Badge), `kolibri_core.mjs` (`demoSnapshot`).
Neu sind nur Detailkarte, Filter, Quellenwahl und Bewegungsschalter in `preview.mjs`.

## Start
    ./start_preview.sh /pfad/zu/2026-courier
Danach http://127.0.0.1:18777/titan/index.html öffnen. Nötig: Checkout von `integration/v1` mit PR #776 und #777.

## Quellen
| Modus | Daten | Grün möglich? |
|---|---|---|
| REPLAY | `replay_snapshot.json`, erzeugt von `gen_replay.py` aus einem echten lokalen Controller-Lauf (synthetischer Adapter, kein Provider) | ja, nur mit Journal-Beweis und Hub-Anker |
| DEMO | `kolibri_core.demoSnapshot()` | nie (Magenta, Banner) |
| LIVE | `/hub/api/kolibri` des laufenden Hubs | ja, nur mit Beweis; ohne Hub: UNKNOWN |

REPLAY neu erzeugen: `python3 gen_replay.py /pfad/zu/2026-courier replay_snapshot.json`
