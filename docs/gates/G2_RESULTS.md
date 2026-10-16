# Gate G2 — Reliable Motor

Basis: `integration/v1` @ `7cbbffcbb18fe2e071795a8624f2463c0f715333`
Branch: `gate/g2`
Owner dieses Laufs: Courier Grok. `BUILD_IF_AUTHORIZED` = ja.
Kosten: 0 EUR. Kein Deploy, kein Merge, kein Force-Push.
Nicht angefasst: `server/app.py`, Dateien unter `.github`. Nichts gelöscht.

`VERIFIED` wird nicht vergeben. Ein pytest-PASS ist kein `REAL_EXECUTION_PROVEN` und kein Modellaufruf. Keine Sync-Behauptung.

## Host

| Feld | Wert |
|---|---|
| HOST | Linux `cursor` 6.12.94+ x86_64, Python 3.12.3. Kein Mac, `RESOURCE_PAUSE` ungesetzt. |
| CPU | 4, Load `0.05 0.03 0.01` |
| RAM | 15 GiB gesamt, etwa 10 GiB used, 4.4 GiB free, 4.9 GiB available |
| Swap | 0 B |
| SSD | `/` 254 G, 6.7 G belegt, 3 %, 247 G frei |
| RESOURCE_GATE | offen |
| BEFORE_SHA | `7cbbffcbb18fe2e071795a8624f2463c0f715333` |
| COST_EUR | 0 |

Evidence-Block (SHA-256 `e3b47e9ec09cf9f5d6f83383f01ab6d2d3d48e0b50e8a2d17776216966844089`):

```
BEFORE_SHA 7cbbffcbb18fe2e071795a8624f2463c0f715333
HOST Linux 6.12.94+ x86_64
MEM 15Gi total, 4.4Gi free, 4.9Gi available, about 10Gi used
DISK 247G free, 3 percent, 6.7G used
LOAD 0.05 0.03 0.01
NPROC 4
SWAP 0
RESOURCE_PAUSE unset
RED idle SystemExit 7 from time.sleep
RED motor ModuleNotFoundError
RED_COUNT 6 failed in 0.06s
GREEN gate 7 passed in 0.19s
GREEN related 29 passed in 0.62s
MOTOR_SHA256 2b20c9cd5a8ecc3d8187e73d318b8af24e21211fe34568cffd2172a845e8ec18
HOST_LOOP_SHA256 c8af307bdda99521db27811518e60ba6fad21ecd8dece5ab6bf0467dc15f2f4b
```

Vorher, Exit 1:

```text
python3 -m pytest -q tests/test_gate_g2_motor.py --tb=line
FFFFFF
6 failed in 0.06s
```

`test_idle_motor_blocks_on_wakeup_and_does_not_sleep` endete mit `SystemExit(7)`: `courier_runtime/host_loop.py` rief im Leerlauf `time.sleep` auf. Die übrigen fünf Tests endeten mit `ModuleNotFoundError: No module named 'courier_runtime.motor'`.

Danach, Exit 0:

```text
python3 -m pytest -q tests/test_gate_g2_motor.py --tb=short
.......
7 passed in 0.19s
```

Zusammen mit den bestehenden Suiten von Host-Loop, Lease und Provider-Circuit:

```text
python3 -m pytest -q tests/test_gate_g2_motor.py tests/test_host_loop.py tests/test_runtime_lease.py tests/test_provider_circuit.py --tb=line
.............................
29 passed in 0.62s
```

## 1 — Pfad des Motors — DONE

`courier_runtime/motor.py` `advance` geht in dieser Reihenfolge durch: persist, validate, contract, reconcile, dependencies, ready, eligibility, select, dispatch.

Ein `PASS` für Aufgabe A, deren Vertrag `PASS` verlangt, schreibt das Result ins Journal, setzt A auf `DONE` und gibt die abhängige Aufgabe B an ihren Provider. Ein Result ohne `result_id` stoppt nach validate und dispatcht nichts. Ein `FAIL` gegen einen Vertrag, der `PASS` verlangt, stoppt nach contract; A und B bleiben stehen.

## 2 — IDLE ohne Polling — DONE

Die leere Queue ruft `idle(wait)` genau einmal auf und ruft `time.sleep` nicht auf. `main` in `host_loop.py` blockiert bei leerer Queue auf `wait_for_wakeup` (ein `select` auf inotify). Solange Arbeit offen oder claimed ist, bleibt das bisherige Intervall für den Health-Tick.

Der rote Lauf zeigte `SystemExit(7)` aus `time.sleep`. Der grüne Lauf zeigt Exit 0, keine Sleep-Aufrufe, und ein gewachsenes Signalfile löst den echten Wait aus.

## 3 — Isolierter Provider-Ausfall — DONE

Alpha wirft `RuntimeError`. Beta wird trotzdem aufgerufen und läuft. A bleibt `READY` mit Grund `PROVIDER_DOWN` und hält keinen Lease. Der Ausfall verlässt `advance` nicht.

## 4 — Ein Writer je Scope — DONE

`advance` nimmt den Lease über `courier_runtime.lease.LeaseStore`. A und C teilen `src/shared/`. A erhält den Lease (`holder-A`). C bleibt `READY` mit Grund `SCOPE_HELD`. B auf `src/other/` wird dispatcht.

## Grenzen

Kein lebendiger Provider und kein CI-Lauf. Der inotify-Wait ist der lokale Linux-Wait in diesem Prozess. Der Status dieses Gates bleibt der Stand des Produktplans, bis eine unabhängige Prüfung ihn ändert. Dieser Bericht setzt ihn nicht auf PASS und nicht auf `VERIFIED`.
