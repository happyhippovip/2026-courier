# V38 + V40 · Einzeln abnehmbare Schritte, #846, Owner-Handoffs · Claude Opus · 24.10.2026

Basis `integration/v1` `81bbf224b` (unverändert). Es gibt **keinen Merge** und **keine Writer-Lease** (`LEASE = NONE` für alle Pakete). Den 4269-Test-Volllauf habe ich nicht wiederholt. Alle CI-Läufe liefen im öffentlichen Repo; Zusatzkosten 0 €.

## Neue Ergebnisse
| # | Ergebnis | Status |
|---|---|---|
| N1 | **#846 = F-C1 + Folgepatch, baumgleich** mit den V31-Abnahme-Commits `9509302eb`/`3fdb521d2` (Tree `1e4b1880…` bzw. `56e7b35b…`). Eigene CI 7/7 success. Es gibt **keine zweite F-C1-Implementierung** | VERIFIED |
| N2 | **#846 + #836 zusammen** mergen ohne Konflikt: 132 passed (F-C1-Pin und F-K1-Pin sind jetzt reguläre Tests). Der #836-Deadlock-Fix passt auch auf diese Kombination (89 passed) | VERIFIED |
| N3 | **Legacy-CostGate-Kompatibilität von #846:** `provider_exec` akzeptiert `estimated_cost_eur` (`KNOWN_PARAM_KEYS`/`AGY_PARAM_KEYS`); der Testkommentar in `test_provider_exec_agy_costgate.py` ist veraltet. `github_wake_inbox` legt die zugelassene Schätzung in `params`. `run_antigravity_bridge` (#832) liefert `0.0`. Damit ist **kein bestehender Erzeuger von `local_shell`/`provider_exec` durch #846 gebrochen** | VERIFIED |
| N4 | **Nicht deklarierter Adapter `telegram_delivery`:** `courier_adapters/ai_ranking_worker.py:56` legt solche Tasks an. Auf dem Trunk werden sie angenommen (201), mit #846 abgelehnt (400 `cost_blocked`), Probe `evidence/probe_telegram.py`. Schon auf dem Trunk gibt es für diesen Adapter **keinen Verifier** (`adapter_verifier` = None), er erreicht also nie FINAL. #846 bricht damit keinen funktionierenden Pfad, sondern macht ihn früher sichtbar | VERIFIED |
| N5 | **Bestehender Fehler (P2), unabhängig von #846:** `ai_ranking_worker` prüft die Antwort von `POST /v1/tasks` nicht und meldet den eigenen Task trotzdem als `success`; ein abgelehnter Liefer-Task geht still verloren. Negativtest als strikter xfail-Pin: `V40_ai_ranking_route_refused_pin.diff` (sha256 `b090e717b6c77051e67a770715a9223bcfb03b6949b92c950a92ddf2c328b319`), auf #846: 2 passed, 1 xfailed. Owner: Intake/L4. Minimalfix für den Owner: bei `not route_res.ok` den Ranking-Task mit Grund `delivery_refused` als `failure` melden | VERIFIED |
| N6 | **#836-Owner-Handoff erledigt:** [Kommentar auf #836](https://github.com/happyhippovip/2026-courier/pull/836#issuecomment-6381516229) mit Patch-SHA `2807873e…7156e`, Basis `ad50f362a`, Repro und Regressionstest. Ich habe ihn nicht selbst eingespielt | DONE |
| N7 | **Windows-Daemon-Tests sind instabil, nicht durch H12 verursacht:** `claude/v38-h12` ist unter Windows zweimal rot, jedes Mal mit einem *anderen* Test (`test_windows_worker_recovery::test_restart_after_final_does_not_execute_again`, dann `test_windows_worker_contract::test_success_without_any_artifact_evidence_is_reported_failed`). Gründe, H12 als Ursache auszuschließen: (a) H12 berührt keine Datei unter `scripts/windows_worker` und keinen dieser Tests (grep); (b) der zweite Test ist **derselbe**, der in der Trunk-CI [40008119253](https://github.com/happyhippovip/2026-courier/actions/runs/40008119253) rot ist; (c) die H12-Basis `claude/v38-guard1` und der Kombinations-Branch mit H12 sind unter Windows grün. Den einen erlaubten Rerun habe ich genutzt. Behebung über #843 (Stabilisierung `test_windows_worker_contract`); für `test_windows_worker_recovery` gibt es noch keinen Fix | VERIFIED |
| N8 | Die Tests aus #843 und #845 laufen gegen WIN-COST-1 v3 (`claude/v38-win`) grün: 47 passed. Es gibt keine Dateiüberschneidung mit #842–#845 und #837 | VERIFIED |
| N9 | Ein Codex-„V31-Reality/Cost-Admission“-Patch ist in GitHub **nicht sichtbar** (kein neuer `codex/*`-Branch und kein PR seit 24.10.); ein Abgleich war daher nicht möglich. Hinweis an Codex: auf #846 aufbauen, keine zweite Controller-Admission | UNKNOWN |

## Einzeln abnehmbare Schritte (CL-V38-03)
Jeder Branch enthält **nur** die echten Abhängigkeiten plus genau ein Paket. Der Patch-Inhalt ist per `git patch-id` identisch mit dem Original-Diff; bei H12 entspricht er dem Original-Diff, die Abweichung zum Kombinations-Commit kommt nur aus dem F-C1-Kontext. Ein grüner kombinierter Lauf gibt **keine** Freigabe; jeder Schritt hat seinen eigenen CI-Beleg.

| Schritt | Paket | Branch @ Head | Basis | CI (v1, Ubuntu + Windows) | Release-Gate |
|---|---|---|---|---|---|
| 1 | F-C1 + Folgepatch | **#846** `cursor/fc1-joint-integration-44b0` @ `2a07219c2` | Trunk | 7/7 success (PR-CI) | L2-Review + MERGE-GO; owner_token-Gate laut #846 |
| 2 | F-C1b | `claude/v38-fc1b` @ `439b5999c` | #846 | [40074791146](https://github.com/happyhippovip/2026-courier/actions/runs/40074791146) success | nach 1; L3-Review |
| 3 | PE-1 | `claude/v38-pe1` @ `f41dbaf2d` | Trunk | [40074793174](https://github.com/happyhippovip/2026-courier/actions/runs/40074793174) success | L3-Review |
| 4 | CDX-COST-1 | `claude/v38-cdx` @ `30cc812e5` | Trunk | [40074794708](https://github.com/happyhippovip/2026-courier/actions/runs/40074794708) success | L1; Reihenfolge zu #810 |
| 5 | GUARD-1 v3 | `claude/v38-guard1` @ `ad69f9ed6` | Trunk | [40074788910](https://github.com/happyhippovip/2026-courier/actions/runs/40074788910) success | Security-Review (Grok 57,50/Codex) |
| 6 | H12 v3 | `claude/v38-h12` @ `cde271f64` | 5 | [40074798430](https://github.com/happyhippovip/2026-courier/actions/runs/40074798430) **failure ×2, Windows-Daemon-Flake (N7)**; Ubuntu success | **BLOCKED**, bis #843 gemergt ist und ein grüner Lauf vorliegt; danach L4-Review |
| 7 | WIN-COST-1 v3 | `claude/v38-win` @ `4ed111395` | 5 | [40074800411](https://github.com/happyhippovip/2026-courier/actions/runs/40074800411) success | Cursor-Windows-Review; Reihenfolge zu #788 |
| 8 | WQ-1b v2 | `claude/v38-wq1b` @ `a2a6dfabd` | Trunk | [40074796599](https://github.com/happyhippovip/2026-courier/actions/runs/40074796599) success | L1/L3; Rollout alle Homes zugleich |
| — | POL-1 | — | — | — | **BLOCKED** (Entscheidung Dennis) |

Diese Branches sind Belege, **keine PRs** und nicht zum Mergen gedacht. Ein Owner kann sie als Vorlage für einen eigenen PR nehmen, wie bei #846.

## Vertragsüberschneidung mit neuen Owner-Handoffs (CL-V38-04)
- Seit dem 24.10. 06:00 sind neue Owner-Artefakte nur #846 (identisch mit Schritt 1) und das Memory-Update zur Grok-Account-Zuordnung, ohne Code.
- **GUARD-1, H12, WIN-COST-1, WQ-1b:** Kein offener oder neuer PR berührt `courier_core/provider_cli_guard.py`, `adapters/local_shell.py`, `courier_core/work_queue.py` oder `courier_worker/queue_feed.py`. Für `scripts/windows_worker/daemon.py` gilt nur #788 (3-way sauber) und die semantische Prüfung N8.
