# Gate G1 — Ledger

Basis: `integration/v1` @ `7cbbffcbb18fe2e071795a8624f2463c0f715333`  
Branch: `gate/g1`  
Owner: Courier Grok. `BUILD_IF_AUTHORIZED` = ja.  
Kosten: 0 EUR. Kein Deploy, kein Merge, kein Force-Push. `server/app.py`, `.github` und Ralph sind unverändert.

Das ist kein `VERIFIED` und kein `LEDGER_FROZEN`. `CANDIDATE` bleibt, was es war: kein `PASS`.

| Feld | Wert |
| --- | --- |
| HOST | Linux `cursor` 6.12.94+ x86_64, Cursor-Cloud-VM, live gelesen. Kein Windows-Runner, kein Mac-`RESOURCE_PAUSE`. |
| RESOURCE_GATE | OPEN. 4 CPUs, load `0.00 0.00 0.00` (2026-10-13 15:19:34 UTC). RAM MemTotal 16387416 kB, MemAvailable 5126792 kB. Disk `/` 3%, 247G frei. |
| BEFORE_SHA | `7cbbffcbb18fe2e071795a8624f2463c0f715333` |
| AFTER_SHA | `50e8002de7162aed4c056f34b7ebd4b36230ca5a` |
| TESTS | `python3 -m pytest tests/test_gate_g1_ledger.py tests/test_gate_g1_job_object.py tests/test_ledger_candidate_binding.py -q` |
| LEDGER_TEST_SHA256 | `584c3f91dc4d4fb8ec0f8ef5494587b7062e6644b33bb9ef5f10ea00b5084a12` |
| JOB_TEST_SHA256 | `5791faf61b8701f8d1f8cec71fa1434d5a685e305c47eac68d7f70dd65e679b9` |
| BINDING_SHA256 | `15b88857e84f9f61941cdca7cf4ccc3e2fae8b86fbba3d25268e1403e7e5cf3f` (`scripts/ledger_candidate_binding.py`) |
| HOST_SHA256 | `0d7fb1b162fc8da2ffd9646f1c43af354e7efb4fb7fa31614c17473388931d0f` (`courier_worker/host.py`) |
| COST_EUR | 0 |

Grün zusammen: **15 passed, 1 skipped**. Die bestehenden fünf Pins in `tests/test_ledger_candidate_binding.py` bleiben grün. `tests/test_l3_worker_host.py -k "cancel or terminat or contain or orphan"`: **4 passed, 1 skipped** (der vorhandene Windows-only-Test).

## 1 — Runtime-Bindung

Ledger-Einträge der Gate-1-Bindung hängen an der geladenen Runtime, nicht nur an der Git-SHA auf der Platte. Ein nachträgliches Umschreiben der Runtime im Dokument bricht das Siegel. Fehlen die Append-only-Trigger, ist das Journal umschreibbar und nicht bindbar.

Rot, vor dem Fix, `tests/test_gate_g1_ledger.py`:

- `test_binding_pins_the_loaded_runtime_and_a_seal`: `KeyError: 'runtime'`
- `test_rewriting_the_runtime_breaks_the_seal`: `KeyError: 'runtime'`
- `test_missing_append_only_guards_are_not_bindable`: `KeyError: 'guards_present'`

Die Bindung kannte weder `runtime` noch `guards_present` noch ein Siegel. Eine Kette ohne die Trigger `events_no_update` / `events_no_delete` blieb damit ein Kandidat.

Grün danach: dieselben drei Tests passed. `runtime.source_sha256` ist `build_identity()["source_sha256"]` und ungleich der 40-stelligen `source_sha`. `binding_intact` ist falsch, sobald `runtime.source_sha256` geändert wird. Ohne die Trigger ist `status` `NOT_BINDABLE`, `unknowns` enthält `append_only_guards_missing`, und `main` endet mit Exit-Code ungleich 0.

## 2 — UNKNOWN-Gate

Ein unbekannter Zustand ist kein Erfolg. Leere Source-Identität und eine nicht lesbare geladene Runtime blockieren. Ein Dokument, das nachträglich auf `UNKNOWN` umetikettiert wird, bleibt abgelehnt, auch wenn das Siegel dazu neu gesetzt wird.

Rot, vor dem Fix:

- `test_blank_source_identity_is_not_success`: `assert 'source_identity_unavailable' in []` — leere Git-Ausgabe ließ `unknowns` leer, der Status blieb damit `CANDIDATE`, Exit 0.
- `test_unknown_loaded_runtime_blocks`: `assert 'loaded_runtime_unknown' in []` — `source_sha256 is None` wurde nicht geprüft.
- `test_relabelled_unknown_is_not_accepted`: `AttributeError: module 'ledger_candidate_binding' has no attribute 'seal_of'`

Grün danach: alle drei passed. `accepted()` verlangt Siegel, `status == "CANDIDATE"`, leere `unknowns`, vorhandene Guards, sauberen Baum, intakte Kette und eine 64-stellige Runtime-`source_sha256`. `UNKNOWN` fällt durch. Es gibt weiterhin kein `PASS`.

## 3 — Windows Job-Object-Kill

Kindprozesse sollen über das Job Object enden. `TerminateJobObject` mit Rückgabe falsch, ein fehlendes Job Object oder ein Prozess, der nach der begrenzten Wartezeit noch lebt, ist `ContainmentError` und kein erfolgreiches Aufräumen. Der Handle wird nur geschlossen, wenn der Root eingesammelt ist.

Rot, vor dem Fix: `tests/test_gate_g1_job_object.py` bricht beim Import ab.

`ImportError: cannot import name 'terminate_job_tree' from 'courier_worker.host'`

Der Windows-Zweig von `terminate_tree` hat den BOOL von `TerminateJobObject` ignoriert und danach `proc.wait()` ohne Frist aufgerufen.

Grün danach: **4 passed, 1 skipped**.

Skip, mit Grund, kein Ersatz für einen Windows-Lauf:

`SKIPPED tests/test_gate_g1_job_object.py:75: no Windows runner: kernel32 Job Object kill is not executed on this Linux host`

Der Mock belegt den Vertrag: fehlgeschlagenes `terminate` wartet nicht und schließt nicht; erfolgreiches `terminate` bekommt das Job-Handle, wartet mit `grace` und schließt danach; ein hängender Root blockiert. Der echte `kernel32`-Lauf ist auf diesem Host nicht ausgeführt. Nicht `VERIFIED`.
