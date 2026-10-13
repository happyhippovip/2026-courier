# Gate G2b — Restpunkte des Motors

Basis: `gate/g2` @ `5b15097fa90abcab1ae0abb32802c22f1a2ae7ce` (Draft-PR #609).
Darunter: `integration/v1` @ `7cbbffcbb18fe2e071795a8624f2463c0f715333`.
Branch: `gate/g2b`
Owner dieses Laufs: Courier Grok. `BUILD_IF_AUTHORIZED` = ja.
Kosten: 0 EUR. Kein Deploy, kein Merge, kein Force-Push.
Nicht angefasst: `server/app.py`, Dateien unter `.github`, Ralph. Nichts gelöscht.

`VERIFIED` wird nicht vergeben. Ein pytest-PASS ist kein `REAL_EXECUTION_PROVEN` und kein Modellaufruf. Keine Sync-Behauptung. Der Gate-Status im Produktplan bleibt unverändert.

## Prüfer-Bericht

Einen aktuellen Prüfer-Bericht zu G2 gibt es in diesem Repo nicht.

- `docs/gates` enthält nur `G2_RESULTS.md`, den eigenen Bericht von #609.
- `docs/review` existiert nicht.
- #609 hat keine Issue-Kommentare und keine Review-Kommentare.
- `docs/revenue_v1/INDEPENDENT_VERIFIER.md` prüft Revenue V1, nicht Gate 2.

Die Restpunkte sind aus Abschnitt 7 des Produktplans abgeleitet, zusammen mit den Beispielen im Auftrag. #609 hat den Pfad, leere Queue als IDLE ohne Sleep-Poll, isolierten Provider-Ausfall, weiterlaufende unabhängige READY-Arbeit und einen lebenden Writer je Scope bereits belegt. `tests/test_host_loop.py` belegt weiterhin `manual_continue == 0`. Diese Punkte werden hier nicht erneut gebaut.

Offen danach, und hier geschlossen:

1. Abgelaufener Lease: die laufende Execution wird UNKNOWN reconciled, nicht blind erneut gestartet. Der wartende Writer darf den Scope danach nehmen. Der alte Token ist stale.
2. Restart ohne Doppel-Dispatch: ein offener Dispatch im Journal wird nicht ein zweites Mal gestartet.
3. Backpressure: erfolgreiche Dispatches je `advance` sind gedeckelt.
4. Begrenzte Retries, Regel „Retries sind begrenzt“.
5. Wakeup unter Windows über `ReadDirectoryChangesW`, unter Linux weiter inotify.

## Host

| Feld | Wert |
|---|---|
| HOST | Linux `cursor` 6.12.94+ x86_64, Python 3.12.3. Kein Windows-Host, `RESOURCE_PAUSE` ungesetzt. |
| CPU | 4, Load `0.01 0.03 0.00` |
| RAM | 15.6 GiB gesamt, 4.4 GiB free, 4.9 GiB available, etwa 11.3 GiB used |
| Swap | 0 B |
| SSD | `/` 254 G, 6.7 G belegt, 3 %, 247 G frei |
| RESOURCE_GATE | offen |
| BEFORE_SHA | `5b15097fa90abcab1ae0abb32802c22f1a2ae7ce` |
| COST_EUR | 0 |

Evidence-Block (SHA-256 `daf44b9fb637c475b32ef222ec3291febd01d1cd30a0b40e062a6ec2c18af407`):

```
BEFORE_SHA 5b15097fa90abcab1ae0abb32802c22f1a2ae7ce
BASE_INTEGRATION 7cbbffcbb18fe2e071795a8624f2463c0f715333
HOST Linux 6.12.94+ x86_64
MEM 15.6Gi total, 4.4Gi free, 4.9Gi available, about 11.3Gi used
DISK 247G free, 3 percent, 6.7G used
LOAD 0.01 0.03 0.00
NPROC 4
SWAP 0
RESOURCE_PAUSE unset
RED g2b 7 failed in 0.06s
GREEN g2b 7 passed in 0.07s
GREEN related 36 passed in 0.67s
MOTOR_SHA256 247da1baa3965fd284e9612029ccbb1a596d390ffb150864bfb1135ce422e653
HOST_LOOP_SHA256 446e3fed65c7b11d23a3f1d163fec148da36eabf9b0b289608296524f1de6ca4
```

Vorher, gegen den Motor und den Host-Loop von #609, Exit 1:

```text
python3 -m pytest -q tests/test_gate_g2b_motor.py --tb=line
FFFFFFF
7 failed in 0.06s
```

- Lease: `assert 'RUNNING' == 'RECONCILED'`
- Restart: `assert 'B' not in ['B']`
- Backpressure: `TypeError: advance() got an unexpected keyword argument 'max_dispatch'`
- Retries: `TypeError: advance() got an unexpected keyword argument 'max_retries'`
- Windows-Zweig: `module 'courier_runtime.host_loop' has no attribute 'sys'`
- Windows-Wait: `module 'courier_runtime.host_loop' has no attribute '_wait_windows'`
- Linux bleibt inotify: `module 'courier_runtime.host_loop' has no attribute 'wakeup_backend'`

Danach, Exit 0:

```text
python3 -m pytest -q tests/test_gate_g2b_motor.py --tb=line
.......
7 passed in 0.07s
```

Zusammen mit dem G2-Motor, dem Host-Loop, dem Lease und dem Provider-Circuit:

```text
python3 -m pytest -q tests/test_gate_g2b_motor.py tests/test_gate_g2_motor.py tests/test_host_loop.py tests/test_runtime_lease.py tests/test_provider_circuit.py --tb=line
....................................
36 passed in 0.67s
```

## 1 — Lease-Ablauf — DONE

`advance` liest den Lease über die Uhr des `LeaseStore`. Nach `ttl_s=30` und `clock.t += 31` ist der Lease von A weg. A steht auf `RECONCILED`, `execution` ist `UNKNOWN`, und A ist nicht im zweiten Dispatch. `check_write` mit dem alten Token wirft `StaleLease`. C auf demselben Scope `src/shared/` wird danach dispatcht. A wird nicht ein zweites Mal gestartet.

## 2 — Restart ohne Doppel-Dispatch — DONE

Ein erfolgreicher Dispatch schreibt `{"kind":"dispatch","task_id","attempt"}` ins Journal. Wird der In-Memory-Status von B danach auf `READY` gesetzt und Token sowie `open_attempt` entfernt, bleibt die Journalzeile. Der nächste `advance` dispatcht B nicht erneut und setzt B auf `RECONCILED`. Ein späteres `PASS`-Result mit derselben `task_id` schliesst den offenen Attempt; bis dahin gilt er als offen.

Das Result bleibt der erste Journaleintrag. Der G2-Test prüft das weiter und zählt genau eine Dispatch-Zeile neben dem ungültigen Folge-Result.

## 3 — Backpressure — DONE

`max_dispatch` begrenzt die erfolgreichen Dispatches eines `advance`. Voreinstellung ist 50. Mit `max_dispatch=2` und vier bereiten Aufgaben auf getrennten Scopes gehen `T0` und `T1` raus. `T2` und `T3` bleiben `READY` mit Grund `BACKPRESSURE`. `SCOPE_HELD` und `PROVIDER_DOWN` verbrauchen das Kontingent nicht.

## 4 — Begrenzte Retries — DONE

`max_retries` ist voreingestellt 3. Wirft der Provider, zählt der Versuch und die Aufgabe bleibt `READY` mit Grund `PROVIDER_DOWN`. Beim vierten `advance` ist der Zähler am Anschlag: der Provider wird nicht mehr aufgerufen, der Grund ist `RETRIES_EXHAUSTED`. Im Lauf waren es drei Aufrufe von Alpha und kein vierter.

## 5 — Wakeup unter Windows — DONE, ohne Live-Aufruf

`wakeup_backend()` liefert auf `win32` `read_directory_changes` und sonst `inotify`. `wait_for_wakeup` ruft dann `_wait_windows` oder `_wait_inotify`. `_wait_windows` öffnet das Verzeichnis, ruft `ReadDirectoryChangesW` einmal auf und schliesst das Handle. Der Test setzt `kernel32` ein: ein Read, ein Close.

Dieser Host ist Linux. Die Windows-API ist hier nicht gelaufen. Der Linux-Idle-Pfad von #609 bleibt ein `select` auf inotify. Solange die Queue Arbeit hat, bleibt `time.sleep(interval)` der Health-Tick.

## Grenzen

Kein lebendiger Provider, kein CI-Lauf, kein Windows-Host. Der Produktplan wird durch diesen Bericht nicht auf PASS gesetzt und nicht auf `VERIFIED`.
