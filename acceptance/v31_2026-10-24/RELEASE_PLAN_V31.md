# Release-Plan V31 · 8 Fix-Pakete · Claude Opus · 24.10.2026

**Status:** Plan und Abnahmepaket. Es gibt **keine Merge-Freigabe**: Jeder Schritt braucht ein eigenes MERGE-GO von Dennis bzw. L1. Ich halte für keine der Dateien eine Writer-Lease (`LEASE = NONE`); umsetzen darf nur der jeweilige Owner. Eine neue Ledger-Engine gibt es nicht. POL-1 ist **ausdrücklich BLOCKED**.

Begriffe: VERIFIED heißt, ich habe es selbst ausgeführt und der Beleg liegt unter `evidence/` oder ist ein CI-Lauf. REPORTED heißt, die Aussage stammt aus fremden Berichten und wurde nicht nachgeprüft.

## 1. Basis (VERIFIED, 24.10.)
| Was | Wert |
|---|---|
| `integration/v1` | `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Quell-Branch der Pakete | `claude/ledger-autonomy-acceptance-2026-10-23` @ `b7ceacaac` (Hashes aus diesem Branch neu berechnet; sie stimmen mit allen früheren Berichten überein: `evidence/hashes.txt`) |
| Abnahme-Branch | `claude/v31-acceptance-combined-81bbf22` @ `43ee82615`: ein Commit pro Paket in Integrationsreihenfolge (`evidence/acceptance_branch_commits.txt`). **Nicht zum Mergen**; er dient nur als Beleg |
| CI des Abnahme-Branchs | [Courier v1 CI 40071011287](https://github.com/happyhippovip/2026-courier/actions/runs/40071011287): **success**. Windows-pytest **4118 passed / 0 failed**, Gate PASS, Golden 11/11, 0 skipped. Ubuntu-pytest, Windows-Build, Desktop-JS und Golden-Ratchet sind ebenfalls success |
| Linux-Volllauf lokal | 4269 passed, 0 failed (`evidence/linux_full_suite_81bbf22.log`) |
| Customer-Reality-Gate-Tests lokal auf dem Abnahme-Branch | `tests/test_github_customer_contract.py` + `tests/test_github_worker_adapter.py`: 59 passed |
| Trunk-CI 81bbf22 | [40008119253](https://github.com/happyhippovip/2026-courier/actions/runs/40008119253) **failure** (nur Windows-pytest; laut Release-Train-Checkpoint `test_windows_worker_contract::test_success_without_any_artifact_evidence_is_reported_failed`, REPORTED). Auf dem Abnahme-Branch läuft derselbe Test in derselben Datei grün. Er ist damit sehr wahrscheinlich instabil (#843 „stabilize windows worker contract“); keines der 8 Pakete ist dafür Ursache oder Fix |

## 2. Paket-Tabelle
`TEST_EVIDENCE` stammt vom Einzellauf: Trunk 81bbf22 + nur dieses Paket + seine Abhängigkeiten (`evidence/single.log`, Skript `evidence/single.sh`). Die Rot→Grün-Belege der Entwicklung stehen in den Vorgänger-Ordnern.

| PACKAGE | HEAD (Abnahme-Commit) | PATCH_SHA256 | OWNER | LEASE | TEST_EVIDENCE | CONFLICT | RELEASE_VERDICT | NEXT_STEP |
|---|---|---|---|---|---|---|---|---|
| **F-C1** Controller-Kostensperre + **Folgepatch** (#830-Pin wird regulärer Test) | `9509302eb` + `3fdb521d2` | `6e695c34ffec744c8befb72e46557b1febca56051e48dd6d3f927363c5818b13` + `08dcfe78ed007e9a272b48c4d1577df395bffdf6905cb2403984ee72d39187a8` | L2 Controller (+ L4 für je 1–4 Zeilen `COST_CLASS` in 5 Adaptern) | NONE | F-C1 allein: 199 passed, **1 failed** = strikter #830-Pin `test_gap_direct_controller_create_task_bypasses_the_cost_gate` (VERIFIED, gewollt). Mit Folgepatch: 50 passed. Folgepatch ohne F-C1: 1 failed | keine; Folgepatch passt auf #836 (`ad50f362a`, 3-way sauber) | **OWNER_REVIEW_READY**. Nur als **eine** Einheit mergebar | L2 prüft (Abschnitt 4), dann MERGE-GO |
| **F-C1b** Runner prüft Kosten vor `local_shell` erneut | `d90fca74b` | `c9fddfcd57b8ddda3b04e5e42539ffc0c6e3609d541d2d63f74a803aa13b1892` | L3 Worker Host | NONE | mit F-C1: 113 passed / 1 skipped; ohne F-C1: 7 failed (Abhängigkeit VERIFIED) | #824 kollidiert, zielt aber auf `main` (nicht v1) und ist veraltet: **kein v1-Konflikt** | **OWNER_REVIEW_READY**, nach F-C1 | L3-Review |
| **GUARD-1 v3** Provider-CLI-Tripwire (neue Datei `courier_core/provider_cli_guard.py`) | `518093175` | `1394fcc6263390d1fc159c7f89fe44863eff5b09cafb2b9870b66246697d3d21` | L2 (neue Datei; L1 bestätigt den Owner) | NONE | 181 passed; 4 Subagenten-Reviews eingearbeitet; Fuzz mit 20 000 Eingaben ohne Ausnahme | keine (neue Datei) | **OWNER_REVIEW_READY** | unabhängiges Security-Review (Abschnitt 5) |
| **H12 v3** local_shell: Env-Allowlist, leeres Home, Provider-CLI-Sperre | `bff89b6f1` | `11301d22b8d72d1369469552e9d90d8f6c67e8de61845332d7eccb8834d904d4` | L4 Adapter | NONE | mit GUARD-1: 87 passed; ohne GUARD-1: Import-Fehler (Abhängigkeit VERIFIED) | keine offene v1-PR auf `adapters/local_shell.py` | **OWNER_REVIEW_READY**, nach GUARD-1 (und F-C1, das dieselbe Datei um `COST_CLASS` ergänzt) | L4-Review |
| **WIN-COST-1 v3** PowerShell-Kind ohne Credentials/Profil, Provider-CLI-Sperre, `included_quota` ≠ 0 € | `9a174c92b` | `db6d966d8991f9e235676dcbc2368c5e018e4db537f97bb81e777a7ac1a4e9be` | Cursor Windows (Windows-Daemon) | NONE | mit GUARD-1: 68 passed (inkl. `test_windows_worker_contract`, `test_artifact_upload_flow`); ohne: 7 failed; Windows-CI grün | passt auf #788 (`9937f98bb`, sauber; #788 selbst ist `dirty` gegen v1); W14-Branch berührt die Datei nur in alten, bereits integrierten Zeilen | **OWNER_REVIEW_READY**, nach GUARD-1 | Cursor-Windows-Review, sobald das Kontingent es erlaubt; vorher kein Merge |
| **WQ-1b v2** Cross-Home-Lease-Rückgewinnung (ATTACH/RECLAIM/RECONCILE/PARK) | `3f345fc9a` | `8451444a241fb07883a740bbfbf29eea99a5ad9ca946226dfed859f75644f4d0` | Queue: `work_queue.py` L1 / `queue_feed.py` L3 | NONE | 89 passed inkl. Gate-2; Mehrprozess-Race-Probes ergaben 0 doppelte ASSIGNED (Vorgänger-Ordner) | keine offene v1-PR | **OWNER_REVIEW_READY**; Rollout nur auf allen Homes gleichzeitig | L1/L3-Review + Rollout-Entscheidung |
| **CDX-COST-1** Codex-Bridge: CostGate vor echtem CLI-Start | `9867964f0` | `dfbb21b9a4d8faa9a29fa5fe051d92554d3f955e049045270159fd70eff5e5b2` | Codex-Bridge (L1-Triage) | NONE | 43 passed | passt auf #810 (`cd7d03613`, sauber) | **OWNER_REVIEW_READY** | L1 legt die Reihenfolge zu #810 fest |
| **PE-1** provider_exec: Overflow-Schätzung blockt statt Crash | `43ee82615` | `b021cf95d3e497ed6c67ec5e7498276e9af64b83b1bed5f1d6fe256d09c6ee1f` | L3 | NONE | 23 passed | passt auf #785 (`fb2a026db`, sauber) | **OWNER_REVIEW_READY** | L3-Review |
| ~~POL-1~~ | — | `71087dd1ea370d3aa574af8938fcf943f26e4c167569e3c232951eea5835e8db` | Dennis (Kostenentscheidung) + L2/L1 | NONE | 12 eigene Tests grün; 60 bestehende Tests erwarten altes Verhalten | — | **BLOCKED** (Entscheidung offen) | nichts tun bis zur Entscheidung |

**Überschneidungen**, geprüft gegen 60 offene PRs mit Aktivität seit 20.10. (`evidence/overlap.txt`):
- **Cursor-Mac:** Kein Paket berührt `scripts/mac_worker/*`. #841 enthält nur Doku.
- **Reality-Check:** Der Customer-Reality-Gate-Workflow (`github-ci.yml`) testet `test_github_customer_contract.py` und `test_github_worker_adapter.py`; beide sind mit allen Paketen grün. `scripts/repo_reality_check.py` wird von keinem Paket berührt.
- **Windows-W14** (`preserve/mac/w14/overlay-integration-tests`, Desktop-Overlay): Einzige gemeinsame Datei ist `scripts/windows_worker/daemon.py`. Die W14-Änderung dort (Zustandsordner `LOCALAPPDATA/Courier`) ist schon im Trunk; es gibt keine Hunk-Überschneidung mit WIN-COST-1.
- **#836** (Provider-DONE ohne Journalbeweis, Cursor Mac) ändert `tests/test_ledger_engine.py`. Der F-C1-Folgepatch passt 3-way darauf, es gibt **keine Doppelarbeit**: #836 deckt F-K1 ab, der Folgepatch F-C1.
- **Resource-Policy-PRs** #779/#798/#799 betreffen nur POL-1, und POL-1 ist blockiert.

## 3. Integrationsplan (jeder Schritt einzeln prüfbar)
Nach **jedem** Schritt gilt: v1-CI auf dem neuen `integration/v1`-Head grün (Ubuntu + Windows), sonst Stopp und Revert dieses einen Schritts. L1 merged.

| Schritt | Paket | Vorbedingung | Prüfung vor dem Merge |
|---|---|---|---|
| 1 | F-C1 + Folgepatch (ein Merge) | — | `pytest tests/controller tests/test_ledger_engine.py`; ein Adapter ohne `COST_CLASS` ergibt `cost_blocked` |
| 2 | F-C1b | 1 | `pytest tests/test_adapter_runner_cost_recheck.py tests/test_adapter_runner.py tests/test_l3_worker_host.py` |
| 3 | PE-1 | — | `pytest tests/test_provider_exec_cost_overflow.py tests/test_p0_provider_costgate.py` |
| 4 | CDX-COST-1 | — (Reihenfolge zu #810 klären) | `pytest tests/test_run_codex_bridge_costgate.py tests/test_run_codex_bridge.py` |
| 5 | GUARD-1 v3 | — | `pytest tests/test_provider_cli_guard.py` + unabhängiges Security-Review |
| 6 | H12 v3 | 1, 5 | `pytest tests/test_local_shell_env_allowlist.py tests/test_local_shell_adapter.py` |
| 7 | WIN-COST-1 v3 | 5 (Reihenfolge zu #788 klären) | `pytest tests/test_windows_costgate_and_writer_lease.py tests/test_windows_worker_contract.py tests/test_artifact_upload_flow.py`; **Windows-CI Pflicht** |
| 8 | WQ-1b v2 | — | `pytest tests/test_queue_*.py tests/test_work_queue.py tests/test_ledger_tick*.py tests/test_gate2_two_workkeys.py`; Rollout-Entscheidung „alle Homes zugleich“ |

Die Schritte 3, 4 und 8 sind unabhängig und können parallel geprüft werden; gemergt wird trotzdem einzeln (SINGLE_WRITER).

## 4. Unabhängige Abnahme je Paket (vorbereitet)
Für jedes Paket gilt derselbe Ablauf. Er läuft nur lesend in einer Wegwerf-Kopie und kostet nichts.
1. Patch aus dem Quell-Branch holen und den SHA256 aus Abschnitt 2 vergleichen.
2. Auf `81bbf224b` (oder den aktuellen Head) mit den Abhängigkeiten anwenden: `git apply --3way`.
3. Die Testbefehle aus Abschnitt 3 ausführen und die Ergebnisse mit `evidence/single.log` vergleichen.
4. **Gegenprobe:** nur den Produktcode-Teil zurücknehmen, die Tests behalten. Die neuen Tests müssen dann rot werden.
5. Ergebnis als `VERIFIED_ACCEPT` oder `REJECT` mit Grund.

| Paket | Fokus der Abnahme | Vorgeschlagener Prüfer |
|---|---|---|
| F-C1 + Folgepatch | Kein Pfad zu `TASK_CREATED` ohne Kostenentscheidung; ein unbekannter Adapter wird blockiert; Idempotenz-Replay bleibt Duplikat | L2 + Grok 88 (Architektur) |
| F-C1b | Kein Start von `local_shell` ohne endliche 0,0; der Fehlerreport ist nicht retrybar | L3 |
| GUARD-1 v3 | Umgehungen an Befehlsposition; Fehlalarme bei normalen Befehlen; keine Ausnahme bei beliebiger Eingabe | Grok 57,50 (Red-Team) oder Codex |
| H12 v3 | Kein Provider-Key oder Login-Zeiger im Kind; temporäres Home wird gelöscht; git-Identität nur per `params.env` | L4 + Codex |
| WIN-COST-1 v3 | PowerShell-Kind ohne `COURIER_API_KEY`/Profil; Windows-Pfade und Quoting | Cursor Windows (Owner) + Google Antigravity Windows (unabhängig) |
| WQ-1b v2 | Höchstens ein ASSIGNED pro Workkey über alle Homes; RECLAIM ist an genau einen Lease gebunden | L1 + Grok 88 |
| CDX-COST-1 | Echte CLI nur mit expliziter 0,0 bei aktiver Ressource | L1 |
| PE-1 | `10**400` ergibt BLOCKED statt Crash | L3 |

## 5. Ausdrücklich offen und blockiert
- **POL-1 (BLOCKED):** Ein inkludiertes Kontingent zählt nur mit `billing_mode: INCLUDED_QUOTA`, `effective_cost_eur: 0` und `cost_source: PROVIDER_VERIFIED`. Das würde alle agy-, Codex- und Gemini-Läufe sperren und 60 Tests ändern. Die Entscheidung liegt allein bei Dennis. Bis dahin wird nichts davon vorbereitet oder angewendet.
- **owner_token (P0, Mensch):** Auf `integration/v1` 81bbf22 enthalten **64** öffentliche Dateien unter `scripts/windows_muse_wall/runtime/slots/` einen nicht-leeren `owner_token`; am 23.10. waren es 40. Werte wurden weder gelesen, kopiert noch ausgegeben. Nötig sind Rotation bzw. Widerruf durch den berechtigten Kontoinhaber, danach Entfernen der Dateien und Verhindern neuer Commits (z. B. ein Safety-Ratchet-Muster). Eine History-Bereinigung braucht ein eigenes GO.
- **Bekannte Grenzen der Pakete:**
  - Der Tripwire ist keine Sandbox: umbenannte Binaries und Skriptdateien erkennt er nicht.
  - Unter Windows gilt das Label `free`/`local` weiter als 0 €, solange der Server-Dispatch (`server/app.py`, geschützt) keine Schätzung mitliefert.
  - WQ-1b hat keinen produktiven Probe; ohne ihn wartet ein angehängtes fremdes Item auf `reclaim`.
