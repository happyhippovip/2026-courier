# Gate G3 prep — Zero-Human A→B

Stand: 2026-10-13. Branch `gate/g3prep` ab `integration/v1` `7cbbffcbb18fe2e071795a8624f2463c0f715333`.

Diese Vorbereitung ist keine Verifikation von Gate 3.

## Kanonischer Windows-Core

Gelesen, nicht geändert, nicht gepickt, nicht umgeschrieben:

`ad7dbc2c42273b755d8daefa16ad8762e55b1a07`

Autor Claude, 2026-10-13, „test: dependent task across a controller restart and with an unknown outcome“. Der Commit liegt auf `lane/L2-task-dependency-input` und `lane/L2-ledger-abc-chain`. Er ist kein Vorfahr von `integration/v1` (Merge-Base `68de315616b70adcc24cdcd77577dc457e0d0da6`).

Sein Vertrag, nur gelesen: Der Controller stoppt, nachdem A COMPLETE ist und bevor B dispatched wird. Ein neuer Controller und ein frischer Worker führen B genau einmal aus und claimen A nicht wieder. Ein abhängiger `non_idempotent` Task mit stillem Worker wird BLOCKED; `retry_authorized` ist eine menschliche Entscheidung.

Die dafür nötigen Typen (`depends_on`, `from_input`, der LiveService-Worker-Loop aus diesem Commit) sind auf `integration/v1` nicht vorhanden. Der Diff des Controllers gegen den Trunk würde `task_result` entfernen. Er wurde nicht angewendet.

## Was der Test prüft

`courier_core/gate_g3.py` `assess_gate_g3` liest ein Journal. `human_relay_count` ist die Anzahl der Events `EFFECT_CONFIRMED` und `RETRY_AUTHORIZED`. Ein vom Aufrufer gesetztes 0 wird nicht angenommen (`TypeError`).

FAIL, und der Zähler bleibt ungemessen (`None`), wenn:

- das Journal fehlt oder `verify_chain` fehlt
- `verify_chain().ok` nicht genau `True` ist (`None` ist unbekannt, `False` ist eine unvollständige Kette)
- ein Event-Typ nicht zu `EventType` gehört

Ein leeres, lesbares Journal misst 0 und ist trotzdem FAIL. Gemessenes 0 allein ist kein Durchlauf.

PASS nur wenn zugleich gilt: gemessener Zähler 0, Kette `ok is True`, genau zwei Tasks, B trägt `depends_on` auf A und ist vor dem zweiten `CONTROLLER_STARTED` angelegt, A ist vor diesem Neustart einmal claimed und COMPLETE, B wird erst danach claimed, jeder Task hat genau eine Verifikation (`RESULT_ACCEPTED`) und genau ein `TASK_COMPLETE`, A wird nach dem Neustart nicht wieder claimed. `blocked` ist kein PASS. Das Feld `verified` ist immer falsch. Der Status ist nur `PASS` oder `FAIL`.

## Roter Lauf, dann der Judge

Vor `courier_core/gate_g3.py`, Commit `c9b2709ed45b1c75921fc64dc6da00fb1c169aad`:

```
ModuleNotFoundError: No module named 'courier_core.gate_g3'
ERROR tests/controller/test_gate_g3_zero_human.py
1 error in 0.21s
```

Danach, derselbe Test:

```
11 passed, 1 skipped in 0.15s
```

Skip, kein Pass:

```
SKIPPED tests/controller/test_gate_g3_zero_human.py:83
The canonical Windows-core A→B service proof is commit
ad7dbc2c42273b755d8daefa16ad8762e55b1a07. It was read and is not modified.
It needs that commit's LiveService worker loop, depends_on, and from_input,
which are not in this tree, plus a Windows worker host.
Skipping is not a pass and is not VERIFIED.
```

Der Skip ist unbedingt. Ein Windows-Runner wird dadurch nicht grün.

## Was auf diesem Host wirklich lief

Host: Linux 6.12.94+ x86_64, 4 CPUs, Load 0.00, RAM verfügbar 5099728 kB von 16387416 kB, Swap 0, Platte 6.7G von 254G (3%). Kein Ressourcenstopp. Python 3.12.3. `python3 -m pytest`. Kosten 0.

Am echten Trunk-Controller (`tests/controller/test_gate_g3_zero_human.py::test_trunk_restart_does_not_pass_without_a_recorded_dependency`): A wird abgeschlossen, der Controller neu gestartet, B danach ausgeführt. Die Kette ist ganz, A wird einmal claimed, der gemessene Relay-Zähler ist 0. Der Judge ist FAIL, weil `depends_on` nicht im Journal steht. Dieser Baum dispatcht B nicht automatisch.

Am echten Controller mit stillem `non_idempotent` Worker: `retry_authorized` ergibt `human_relay_count == 1` und FAIL.

Eine echte `courier.db` mit geänderter Hash-Zeile (nur im Test, Trigger dafür entfernt): `ledger_ok is False`, Zähler `None`, FAIL.

Der eine Judge-PASS benutzt eine Fixture-Eventliste mit gestubbtem `verify_chain().ok = True`. Das sperrt das Prädikat. Es ist kein Gate-3-Beweis. Fixtures dürfen Gate 3 nicht beweisen.

## Nicht angefasst

`server/app.py`, `.github`, Ralph, `C:\Users\lol\Tools\CourierRalph\pilot` und der zugehörige Pilot-Code. Nichts gelöscht. Kein Force-Push, kein Merge, kein Deploy, keine Ausgabe.
