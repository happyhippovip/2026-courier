# W-HUB — Desktop Hub liest das echte Journal

Auftrag: Der Desktop Hub zeigt Ledger-Status, laufende und blockierte Tasks aus der echten Projektion (`<home>/courier.db`), und bei fehlender Quelle `keine Daten/UNKNOWN` statt einer gemessenen leeren Home-Ansicht.

Owner: Courier Grok. `BUILD_IF_AUTHORIZED` = ja. Kein externer Blocker.

## Basis

- Branch: `work/hub-live`
- Basis `origin/integration/v1`: `7cbbffcbb18fe2e071795a8624f2463c0f715333`
- Roter Test: `57723b472f1eb364691f6fc08ab8708897dd274d`
- Umbau: `e1e63b91de13559c0fb725a3fb5cfb0ce1370881`
- Dieser Bericht ist der Commit danach.

Nicht angefasst: `server/app.py`, Ralph, `.github`. Nichts gelöscht. Kein Merge, kein Force-Push, kein Deploy, keine Ausgaben.

## Befund vor dem Umbau

`courier_hub/server.py` las schon `<home>/courier.db` read-only und projizierte Tasks über `courier_hub.model`. Die Desktop-Fixture (`t-blocked`, `t-running`, `t-verified`, …) hängt nur an `tests/hub/fixture_source.py` und `tests/desktop/fixtures/home_view.json`. Der laufende Hub hat sie nicht geladen.

Zwei Lücken:

1. Fehlende oder unlesbare Quelle lieferte `counts` `{needs_you: 0, working: 0, done: 0}`. Die Seite sagte dazu „Nothing needs you right now.“ Das ist eine gemessene leere Home-Ansicht, keine fehlende Quelle.
2. Die Home-Antwort hatte kein Ledger-Feld aus `Journal.verify_chain()` und `projection_current()`.

## Roter Test

`tests/hub/test_hub_live_ledger.py` und ein Fall in `tests/desktop/hub_core.test.mjs`, Commit `57723b472`.

Lauf vor dem Umbau:

- `python3 -m pytest tests/hub/test_hub_live_ledger.py --tb=short`: 2 failed.
  - `test_missing_home_is_unknown_not_an_empty_ledger`: `KeyError: 'ledger'`.
  - `test_real_journal_projects_running_and_blocked_not_fixtures`: die Assertions davor hielten (`working` = `live-running`, `needs_you` = `live-blocked`, Fixture-Ids abwesend, `done` leer). Danach `KeyError: 'ledger'`.
- `node --test tests/desktop/hub_core.test.mjs`: 20 pass, 1 fail. `renderHome` einer Quelle mit `ledger.status == UNKNOWN` enthielt `keine Daten/UNKNOWN` nicht und zeigte weiter die leeren Stapel-Sätze.

Der Journal-Test baut ein echtes Append-only-Journal: `TASK_CREATED` + `TASK_CLAIMED` + `TASK_STARTED` für `live-running`; dieselbe Folge plus `LEASE_EXPIRED` (`reason: ttl`) und `TASK_BLOCKED` für `live-blocked` (`effect_class: non_idempotent`). Danach startet `HubServer` auf `127.0.0.1` und `GET /hub/api/home` prüft die Antwort.

## Umbau

`courier_hub/server.py`

- Lesbare Quelle: Home trägt `ledger` mit `status` `OK` nur wenn `verify_chain().ok` und `projection_current()`. Sonst `BROKEN`. Felder: `chain_ok`, `head_seq`, `projection` (`current` oder `stale`), `reason`.
- `TruthUnavailable` (`not_set_up`, `unreadable`, `updating`): `ledger.status` `UNKNOWN`, `data` `keine Daten/UNKNOWN`, `counts` `null`. Die Listen bleiben leer und gelten nicht als gemessene Null.

`courier_hub/static/hub_core.mjs`

- `ledger.status == UNKNOWN` oder `data == keine Daten/UNKNOWN`: Statuszeile und Home zeigen `keine Daten/UNKNOWN`, nicht die drei leeren Stapel-Sätze.
- `OK` oder `BROKEN`: Statuszeile und ein Ledger-Satz nennen `Ledger OK` bzw. `Ledger BROKEN`, auch wenn der Controller `unreachable` ist.
- Eine Ansicht ohne Ledger-Feld behält den bisherigen Text („hasn't been set up“, leere Stapel, Zählerzeile). Die Fixture-Tests bleiben darauf stehen.

`tests/hub/test_hub_product.py` `test_empty_and_not_set_up_states` erwartet jetzt `UNKNOWN`, `keine Daten/UNKNOWN` und `counts is None`. `truth == not_set_up` und `controller == not_set_up` bleiben.

`scripts/windows_worker/dist/libs/courier_hub/` ist eine ältere Kopie und wurde nicht geändert. `python -m courier_hub` und die Tests laden `courier_hub/`.

## Smoke nach dem Umbau

Gleicher temporärer Ledger, Hub gegen `http://127.0.0.1:9` (kein Controller-Token, kein Controller-Prozess).

Fehlende Quelle:

```json
{"counts": null, "data": "keine Daten/UNKNOWN", "ledger": {"chain_ok": null, "head_seq": null, "projection": "UNKNOWN", "reason": "not_set_up", "status": "UNKNOWN"}, "status": {"controller": "not_set_up"}, "truth": "not_set_up"}
```

Echtes Journal, 8 Events, Kette in Ordnung, Projektion current. Controller bleibt `unreachable`; die Tasks kommen aus dem Journal:

```json
{"counts": {"done": 0, "needs_you": 1, "working": 1}, "ledger": {"chain_ok": true, "head_seq": 8, "projection": "current", "reason": null, "status": "OK"}, "needs_you": ["live-blocked"], "status": {"controller": "unreachable"}, "truth": "ok", "working": ["live-running"]}
```

`checked_at` in diesem Lauf: `2026-10-13T15:25:35Z`. Fixture-Ids waren nicht in der Antwort.

## Grüne Läufe

- `python3 -m pytest tests/hub/test_hub_live_ledger.py tests/hub/test_hub_product.py tests/hub/test_hub_fixture.py -q`: 64 passed in 19.51s.
- `node --test tests/desktop/hub_core.test.mjs`: 21 pass, 0 fail.

Host dabei: 4 CPUs, `MemAvailable` 5149896 kB, Load `0.00 0.02 0.00`, `/` 254G, 6.7G belegt, 247G frei (3%), Python 3.12.3, pytest 9.1.1. `requests` nur lokal für die vorhandenen Hub-Produkttests installiert, nicht ins Repo geschrieben.

## Offen, ohne falsches Grün

- `ledger.status == BROKEN` ist im Code der Zweig für eine fehlgeschlagene Kette oder eine nicht aktuelle Projektion. Die Append-only-Trigger lassen einen Kettenbruch im Test nicht per Update erzeugen. Dieser Zweig hat keinen eigenen Lauf.
- Die Dist-Kopie unter `scripts/windows_worker/dist/libs/courier_hub/` zeigt den alten Stand.
- Kein `VERIFIED`. Kein unabhängiger externer Beleg außerhalb dieses Laufs.
