# L2 Build Marathon V2 · 23.10.2026 · F-C1 Controller Cost Admission (Patch für L1, kein Merge)

Basis: `integration/v1` `d5b19f1dffe5f5478476bf090c522b38bfc7164e`. Kein exklusiver L2-Lease (Owner unbesetzt, Dispatcher pausiert, `controller.py` in offenem #826) → Patch, nicht Produkt-Branch.

| Datei | Inhalt |
|---|---|
| `F-C1_L2_controller_cost_admission.diff` | 12 Dateien, +194/−7: `controller.py` (`cost_admission` vor `TASK_CREATED`, `400 cost_blocked`, `SPEND_LIMIT_EUR=0.0`, einspielbarer `cost_class`-Resolver), `verification.py` (`adapter_cost_class` über denselben Import wie `adapter_verifier`), `COST_CLASS` in den 5 Adapter-Modulen, Testhelfer erklären ihre Fake-Adapter, neuer Test `tests/controller/test_ctrl_cost_admission.py` |
| `F-C1_followup_830_pin_to_regular_test.diff` | wandelt den F-C1-xfail in #830 in einen regulären Test; erst nach F-C1 anwenden |
| `ACR_WORKKEY_CLAIM_STORE_2026-10-23.md` | Architektur-Entwurf: eine Workkey-Claim-Wahrheit |

Regeln: Unknown-Marker → immer Block · Adapter ohne `COST_CLASS` → Block (auch mit 0.0) · `metered` braucht Angabe · Angabe muss endlich, ≥ 0, kein bool, ≤ 0 EUR sein · fehlende Angabe wird nie zu 0.0 · Replay mit gleichem Schlüssel schreibt nichts.

Belege (Wegwerf-Worktree):
- Neue Tests: ohne Controller-Änderung **22 failed / 7 passed**, mit **30 passed**.
- Gegenproben: jede der 7 Regeln einzeln entfernt → mindestens 1 Test rot (bool-Fall `False` ergänzt, nachdem die erste Runde ihn verfehlte).
- Regression: 34 auftragsanlegende Dateien + golden **461 passed, 1 failed**; breit 86 Dateien **1072 passed, 1 failed** — der eine Fehlschlag `test_windows_exe_build.py::test_stop_kills_the_child_process` scheitert identisch auf unverändertem Trunk.
- Fixture vs. Vertrag: 177 Altfehler waren ausschließlich Fake-Adapter (`probe`, `a`, `idprobe`, `l2probe`) ohne Erklärung → Testhelfer/Test-Adapter erklären `local`; das Produkt bleibt streng.
- #830: mit F-C1 schlägt der F-C1-Pin an (gewollt); mit Folge-Patch 47 passed; Folge-Test ohne F-C1 rot.
