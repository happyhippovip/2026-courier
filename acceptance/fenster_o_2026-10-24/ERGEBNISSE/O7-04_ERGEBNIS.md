# O7-04 · B2 Single Writer · Writer-Lease ohne Besitzer-ID · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-04_test_writer_lease_without_owner.py` · sha256 `fb08296f582a33c5ed2b75d01ee89d03903f5f83e9e4ccd209be328fd120918e` |
| Marker | 5 × `xfail(strict=True, raises=AssertionError)` (4 Holder-Werte + Zweit-Writer) + 2 Schutztests |
| Lauf auf Basis | `2 passed, 5 xfailed`, Exit 0; mit `--runxfail`: `lease granted to holder '' / None / True / 0 with token 1` |
| Kosten | 0 €, sqlite in tmp |

## Befund (VERIFIED)
- Der Katalog-Input `tests/test_windows_costgate_and_writer_lease.py` testet nur gültige Holder (Z. 168-226). Ein Negativfall ohne Besitzer-ID **fehlt dort**.
- **Echter Defekt:** `courier_runtime/lease.py:73-75` definiert `holder_ok()`, aber `LeaseStore.acquire` (`lease.py:125-170`) ruft es **nicht** auf. Für Holder `""`, `None`, `True` und `0` wird eine Lease **mit Fencing-Token** vergeben. Geprüft wird es nur in `check_write` (`lease.py:200`).
- **Folge bei `holder=None`:** Die Zeile wird mit `holder NULL` gespeichert. `current()` (`lease.py:121`) und der Overlap-Scan (`lease.py:136`, `holder IS NOT NULL`) sehen den Scope deshalb als frei. Ein zweiter Writer bekommt denselben Scope mit Token 2, während der erste Aufrufer noch ein Lease-Objekt mit Token 1 hält. Das Fencing über `check_write` würde Token 1 zwar ablehnen, aber nur, wenn der Writer `check_write` tatsächlich aufruft.
- Schutz vorhanden (2 passed): Der Windows-Daemon lehnt eine leere bzw. fehlende Worker-ID vor jedem Lock ab (`scripts/windows_worker/daemon.py:534-541`), und sein Holder entsteht über `format_session_holder` (`daemon.py:597-599`). Der Defekt betrifft also direkte LeaseStore-Aufrufer (Controller/Runtime), nicht den Daemon-Startpfad.

## Erwartung nach dem Fix
`acquire` (und `renew`) lehnt `not holder_ok(holder)` ab; gleiche Prüfung empfohlen für `workkey` (heute ebenfalls `""`/`None` erlaubt, per Probe belegt).
sha256: fd9f5f7b088e1275fe35beac7251c8e959e757b969f6970caf90f76d8bd276dc
