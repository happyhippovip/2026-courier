# TITAN Continuous Engineering V8 · Claude Opus · 23.10.2026

Basis: `integration/v1` `d5b19f1df` (geprüft, unverändert). VERIFIED heißt: selbst oder durch einen Subagenten ausgeführt, Befehl und Ausgabe stehen unter `evidence/`. Es gab keinen Merge, keinen Force-Push und keinen echten Provider-Aufruf; Provider-CLIs wurden nur als Stubs in `evidence/redteam_v8_probes/fakebin` aufgerufen. Fremde Branches wurden nicht verändert.

## Patch-Inventar (A01/A02/A04/A10)
| Patch (Datei hier oder im Vorgänger-Ordner) | SHA256 | Owner | Dateien | Hängt ab von | Status |
|---|---|---|---|---|---|
| `../l2_build_2026-10-23/F-C1_L2_controller_cost_admission.diff` | `6e695c34…` | L2 + L4 (`COST_CLASS`) | controller, verification, 5 Adapter, 4 Tests | — | unverändert |
| `WQ-1b_v2_lease_recovery.diff` (**ersetzt** v1 und WQ-1) | `68e23c32…` | Queue (L1/L3) | `work_queue.py`, `queue_feed.py`, 2 Tests | — | v2 neu |
| `H12_v2_local_shell_env_and_provider_cli.diff` (ersetzt v1) | `6e2d366c…` | L4 | `adapters/local_shell.py`, 1 Test | (F-C1: `local_shell` = metered) | v2 neu |
| `WIN-COST-1_v2_windows_cost_env_provider_cli.diff` (ersetzt v1) | `e2051f34…` | Cursor Windows | `windows_worker/daemon.py`, 1 Test | — | v2 neu |
| `../auto_continue_2026-10-23/VC-1_*.diff` (Trunk / #826) | `ba4a0667…` / `9b9541d4…` | Google / #826 | `verified_continuation.py` | — | unverändert |
| `../auto_continue_2026-10-23/CDX-COST-1_codex_bridge_costgate.diff` | `dfbb21b9…` | Codex-Bridge | `run_codex_bridge.py`, 1 Test | — | unverändert |
| `PE-1_provider_exec_overflow.diff` | `b021cf95…` | L3 | `provider_exec.py`, 1 Test | — | neu |
| `POL-1_included_quota_policy.diff` | `71087dd1…` | L2/L1 + **Gründer-Entscheidung** | `resource_policy.py`, `resource_policy.json`, 1 Test | — | **Entscheidungspaket**, 33 bestehende Tests betroffen |
| PR #830 `claude/ledger-engine-v1` | Commit `8932d287f` | Claude | `ledger_engine.py`, Test, Contract | — | gepusht (eigener PR) |

**A03 — Matrix (VERIFIED, `evidence/A03_patch_x_owner_matrix.log`):** 6 Patches × 5 Heads (Trunk, #826 `7686b97f6`, #827 `73a134a4f`, #829 `93207fc99`, #830). 28 von 30 Kombinationen sind grün. VC-1-Trunk lässt sich auf #826/#827 nicht anwenden; dafür gibt es die eigene #826-Variante (35 grün).

## Neue Befunde und Fixes in V8
| # | Befund | Quelle | Rot → Grün | Fix |
|---|---|---|---|---|
| **P0** #830 | Absturz zwischen Kirby-Receipt und Save → nach Neustart **zweiter DONE-Receipt** | Ledger-Reviewer, reproduziert | neuer Test rot → 49 grün, Regression 301 | `finish_turn` prüft vorhandenen Receipt (workkey + Proof); Commit `8932d287f` |
| P1 #830 | geänderter Body unter gleichem Workkey wird still akzeptiert (D08) | Ledger-Reviewer | rot → grün | Controller-409 → `TaskConflict`, nichts geparkt |
| P2 #830 | `depends_on` lässt den Slot dauerhaft NOT_PROVEN (D10) | Ledger-Reviewer | rot → grün | `submit` lehnt `depends_on` ab |
| **P0** WQ-1b | doppelte RECLAIM/RECONCILE-Zeile beendet einen **späteren** Lease desselben Holders → 2 ASSIGNED | Race-Tester, 20/20 | 2 rot → grün | Ereignis bindet an `ends` = `expires_at` des beendeten Leases |
| P1 WQ-1b | `NOT_HOLDER` entkommt `feed_once` (Clock-Skew) | Race-Tester | rot → grün | wird als `lost` gemeldet |
| P1 Queue (D11) | Mission ERROR/BLOCKED → Item wird endlos erneuert, Holder blockiert | Ledger-Reviewer | 2 rot → grün | `park()` → BLOCKED für Menschen, `reclaim` gibt frei |
| **P0** H12 | `local_shell` mit selbst erklärten 0,0 € startet `codex`/`claude`/`gemini`/`agy` (auch via `env`, `sh -c`, `python -c`); `HOME` gibt CLI-Logins frei | Red-Team, 4/4 gestartet | 17 rot → 50 grün; Probe 4/4 abgewiesen | Provider-CLI-Sperre (Programm, Wrapper, Inline-Skript) + eigenes leeres Home |
| P1 Windows | PowerShell-Kind erbt **`COURIER_API_KEY`** und Provider-Keys; Anweisung kann Provider-CLI starten | Red-Team + eigene Prüfung | 6 rot → 16 grün, Regression 112 | Umgebung ohne Zugangsdaten + Provider-CLI-Sperre |
| P1 Policy | CostGate lässt inkludierte Kontingente mit der 0,0 des Aufrufers zu | Red-Team | 10 rot → 12 grün | **POL-1**: `billing_mode` LOCAL bzw. INCLUDED_QUOTA + `effective_cost_eur: 0` + `cost_source: PROVIDER_VERIFIED` |
| P2 | `provider_exec`: Schätzung `10**400` → `OverflowError` | Red-Team | 2 rot → grün, 106 | PE-1 |

## Cross-Home-Beweis (Phase B, VERIFIED, `evidence/race_v8/`, `race_v8_rerun.log`)
Mehrprozess-Probes mit echten Locks gegen WQ-1b v2:
- 4 Homes × 120 Pässe × 60 Läufe mit Uhrversatz und simulierten Abstürzen ergeben **0 doppelte ASSIGNED und 0 entkommene Ausnahmen**.
- Bei SIGKILL zwischen Claim, ATTACH und ASSIGNED gilt in 5 Varianten × 20 Läufen genau ein Übernehmer bzw. keiner.
- Veraltetes Fencing und doppelte RECLAIM-Zeilen: 0 Fehler.
- Replay-Determinismus: 645 Snapshots, alle gleich.

## Entscheidungen, die nicht bei mir liegen
1. **POL-1 (Kosten, Dennis):** Setzt die Gründerentscheidung 1 vollständig um. Nebenwirkungen:
   - Jeder agy-, Codex- und Gemini-Lauf ist blockiert, bis ein vom Provider verifizierter 0-€-Eintrag in der Policy steht.
   - 33 bestehende Tests erwarten das alte Verhalten (Liste in `evidence/POL-1_affected_tests.log`). Ihre Fixtures bräuchten eine Test-Policy.
2. **Windows `free`/`local`:** Der Server-Label bleibt als 0 € stehen; eine Entfernung würde alle Server-Tasks blockieren, weil `server/app.py` (geschützt) keine Schätzung mitgibt. Das Restrisiko ist abgefangen: Provider-CLI-Sperre und Umgebung ohne Zugangsdaten. Eine echte Lösung braucht eine Schätzung im Server-Dispatch (L2/L5).
3. **WQ-1b-Rollout:** Alle Homes müssen gleichzeitig aktualisiert werden. Der echte Probe (`GET /v1/tasks/<id>`) ist nicht verdrahtet; das entscheiden L1/L3.

## Offene P2-Punkte (dokumentiert, nicht gebaut)
- Die Bridge-409-Behandlung (Spec ändert sich nach dem Dispatch) hat keinen Test; Owner ist die Cursor-Bridge.
- Die Crash-Punkte in `queue_feed` sind durch Probes belegt, aber nicht als reguläre Tests; Owner ist die Queue.
- `verified_continuation` Mode A führt `packet["command"]` ohne Gate aus. Das ist latent, denn die CLI setzt keinen Befehl; Owner ist L1-Triage.
- F-C1 prüft nur bei `TASK_CREATED`. Alte Journal-Tasks werden nicht erneut geprüft (SUSPECTED); Owner sind L2/L3.
