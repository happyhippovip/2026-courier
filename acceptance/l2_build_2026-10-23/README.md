# L2 Build Marathon V2 · 23.10.2026 · F-C1 Controller Cost Admission (Patch für L1, kein Merge)

Basis: `integration/v1` `d5b19f1dffe5f5478476bf090c522b38bfc7164e`. Kein exklusiver L2-Lease (Owner unbesetzt, Dispatcher pausiert, `controller.py` in offenem #826) → Patch, nicht Produkt-Branch.

| Datei | Inhalt |
|---|---|
| `F-C1_L2_controller_cost_admission.diff` | v2 nach unabhängigem Review (s. u.); 12 Dateien: `controller.py` (`cost_admission` vor `TASK_CREATED`, `400 cost_blocked`, `SPEND_LIMIT_EUR=0.0`, einspielbarer `cost_class`-Resolver), `verification.py` (`adapter_cost_class` über denselben Import wie `adapter_verifier`), `COST_CLASS` in den 5 Adapter-Modulen, Testhelfer erklären ihre Fake-Adapter, neuer Test `tests/controller/test_ctrl_cost_admission.py` |
| `F-C1_followup_830_pin_to_regular_test.diff` | wandelt den F-C1-xfail in #830 in einen regulären Test; erst nach F-C1 anwenden |
| `ACR_WORKKEY_CLAIM_STORE_2026-10-23.md` | Architektur-Entwurf: eine Workkey-Claim-Wahrheit |

Regeln: Unknown-Marker → immer Block · Adapter ohne `COST_CLASS` → Block (auch mit 0.0) · `metered` braucht Angabe · Angabe muss endlich, ≥ 0, kein bool, ≤ 0 EUR sein · fehlende Angabe wird nie zu 0.0 · Replay mit gleichem Schlüssel schreibt nichts.

Belege (Wegwerf-Worktree):
- Neue Tests: ohne Controller-Änderung **22 failed / 7 passed**, mit **30 passed**.
- Gegenproben: jede der 7 Regeln einzeln entfernt → mindestens 1 Test rot (bool-Fall `False` ergänzt, nachdem die erste Runde ihn verfehlte).
- Regression: 34 auftragsanlegende Dateien + golden **461 passed, 1 failed**; breit 86 Dateien **1072 passed, 1 failed** — der eine Fehlschlag `test_windows_exe_build.py::test_stop_kills_the_child_process` scheitert identisch auf unverändertem Trunk.
- Fixture vs. Vertrag: 177 Altfehler waren ausschließlich Fake-Adapter (`probe`, `a`, `idprobe`, `l2probe`) ohne Erklärung → Testhelfer/Test-Adapter erklären `local`; das Produkt bleibt streng.
- #830: mit F-C1 schlägt der F-C1-Pin an (gewollt); mit Folge-Patch 47 passed; Folge-Test ohne F-C1 rot.

## Unabhängiger Review (Subagent, nicht Autor) und Korrekturen (v2)
| # | Befund | Stand |
|---|---|---|
| 1 HIGH | `local_shell` als „local“ erklärt, aber nur der Adapter-*Name* ist allowlisted; argv und env sind frei → bezahlter Provider-CLI ohne Kostenangabe (201) | **behoben:** `local_shell` = `metered`; neuer Test `test_local_shell_can_run_any_cli_so_it_needs_an_estimate` |
| 2 MEDIUM | `estimated_cost_eur` = 10**400 (gültiges JSON) → `OverflowError` → HTTP 500 | **behoben:** wird als „nicht endlich“ mit 400 abgewiesen; Testfälle ±10**400 |
| 3 LOW | `unknown_cost: "true"`/`1`, `cost_class: "Unknown"`/Nicht-String wurden zugelassen | **behoben:** jeder `unknown_cost` außer `None`/`False` sperrt; `cost_class` muss String sein, „unknown“ ohne Groß/Klein |
| 4 LOW | Vertragsänderungen: Prüfung läuft vor `effect_class`-Validierung; vor dem Patch angelegte metered-Tasks ohne Angabe antworten beim Replay 400 statt 200; Tasks in Alt-Journalen werden nicht nachgeprüft | dokumentiert (bewusst) |
| 5 LOW | Adapter-Modul, das beim Import scheitert → 500 (fail-closed, wie `adapter_verifier`) | akzeptiert |

Belege v2: neue Tests gegen v1 **16 failed / 28 passed** → v2 **44 passed**; breite Regression 86 Dateien **1087 passed, 1 failed** (derselbe vorbestehende Linux-Fehler).

**Produktfolge (Owner informieren):** `scripts/run_antigravity_bridge.py:403–410` baut Antigravity-Aufträge über `local_shell` ohne `estimated_cost_eur` → werden künftig mit `cost_blocked` abgewiesen. Gewollt nach Founder-Entscheidung 1 (included_quota ohne belastbare Kosten = BLOCK); der Owner muss eine belegte Kostenangabe liefern, bevor dieser Weg wieder läuft.

## WQ-1 — Lease-Ablauf in work_queue/queue_feed (`WQ-1_foreign_expired_lease.diff`)
- Befund (VERIFIED, Probe): zwei Homes mit gemeinsamer Queue → zweiter Holder übernimmt nach Lease-Ablauf und weist die Mission in **seiner** Koordinationsdatei neu zu → neuer Bridge-Schlüssel `ledger:<claim_event_id>` → zweiter Controller-Task möglich. Ein Home allein: sicher.
- Fix: `work_queue._effective` behält `expired_lease`; `feed_once` übernimmt keinen fremden abgelaufenen Lease (`foreign_expired`), der ursprüngliche Holder kann fortsetzen.
- Belege: ohne `queue_feed`-Änderung 2 failed / 1 passed → mit 3 passed; 82 Queue/Feed/LedgerTick-Tests inkl. `test_gate2_two_workkeys` grün.
