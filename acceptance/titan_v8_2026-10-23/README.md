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

---

# Teil 2 · nach Merge von #826/#829/#830/#831/#832 (Trunk `e9d7f1f29`)

**#830 wurde von Dennis gemergt** (`011b8456b`). Die Check-ins für #830 sind damit erledigt.

## Integrationspakete auf dem neuen Trunk (VERIFIED)
| Reihenfolge | Patch | SHA256 | Owner | Hängt ab von |
|---|---|---|---|---|
| 1 | `../l2_build_2026-10-23/F-C1_L2_controller_cost_admission.diff` + `../l2_build_2026-10-23/F-C1_followup_830_pin_to_regular_test.diff` | `6e695c34…` / `08dcfe78…` | L2 (+L4 `COST_CLASS`) | — (Folgepatch ist jetzt nötig, weil #830 im Trunk ist) |
| 2 | `F-C1b_runner_cost_recheck.diff` | `c9fddfcd…` | L3 (`adapter_runner`) | 1 |
| 3 | `GUARD-1_provider_cli_guard.diff` (neue Datei `courier_core/provider_cli_guard.py`) | `c9a67787…` | L2 (neu) | — |
| 4 | `H12_v3_local_shell.diff` (**ersetzt** v1/v2) | `f17e1bf7…` | L4 | 3 |
| 5 | `WIN-COST-1_v3_windows.diff` (**ersetzt** v1/v2) | `3f5910e5…` | Cursor Windows | 3 |
| 6 | `WQ-1b_v2_lease_recovery.diff` | `8451444a…` | Queue | — |
| 7 | `VC-1_v2_on_e9d7f1f.diff` (**ersetzt** VC-1 v1, baut auf #831/H10 auf) | `c0c6150b…` | Google | — |
| 8 | `../auto_continue_2026-10-23/CDX-COST-1_codex_bridge_costgate.diff` | `dfbb21b9…` | Codex-Bridge | — |
| 9 | `PE-1_provider_exec_overflow.diff` | `b021cf95…` | L3 | — |
| — | `POL-1_included_quota_policy.diff` | `71087dd1…` | **Entscheidung Dennis** | — (betrifft auf e9d7f1f **60** Tests, `evidence/POL-1_affected_tests_e9d7f1f.log`) |

**Gesamtprobe:** Trunk `e9d7f1f29` + Pakete 1–9 lassen sich konfliktfrei anwenden. Ergebnis: **4194 passed, 16 skipped, 5 xfailed, 0 failed** (rc=0, 8:40 min, `evidence/COMBINED_full_suite_e9d7f1f.log`). Abgewählt ist nur der vorbestehende Linux-Fehler `test_stop_kills_the_child_process`. Die Einzel-Matrix auf `e9d7f1f` steht in `evidence/A03_matrix_on_e9d7f1f.log`.

## Neu in Teil 2
- **GUARD-1** (ein gemeinsamer Tripwire für `local_shell` und den Windows-Worker). Das unabhängige Review v8b hatte für H12 v2 und WIN v2 13 Befunde gemeldet, davon 8 P1; sie sind alle in GUARD-1/H12 v3/WIN v3 eingearbeitet:
  - Erkennung **an Befehlsposition**: Programm, Wrapper mit Optionswerten (`timeout 30s`, `sudo -u bob`, `xargs -a f`, `env -S`), Paket-Runner (`npx -y @google/gemini-cli`, `codex@latest`, `uv run`, `npm exec`, `pnpm dlx`, `bun x`), Inline-Skripte (`sh -ec`, `bash -xc`, `python -Ic`, `node -p`, `cmd /ccodex`, `powershell "codex exec"`, `iex`, `Start-Process`).
  - PowerShell `-EncodedCommand`/`-enc` wird abgewiesen.
  - Keine Fehlalarme mehr bei `git commit -m 'fix codex bridge'`, `Write-Host "agy done"`, Pfaden wie `C:\src\claude\` oder `/opt/claude-tools/run.sh`.
  - 115 Tests; 3 Mutanten getötet.
- **Env-Regeln** über Namenssegmente statt Teilstrings: `GIT_AUTHOR_*`, `KEYBOARD_*` und `PWD` sind erlaubt. Login-Zeiger (`CODEX_HOME`, `CLAUDE_CONFIG_DIR`, `GIT_ASKPASS`, `GIT_SSH_COMMAND`, `NETRC`, `SSH_AUTH_SOCK` …) und URLs mit `user:pass@` werden entfernt. Proxy-, CA- und Windows-Lesevariablen werden geerbt.
- **H12 v3:** Das leere Home liegt außerhalb des Workdirs (temporär) und wird nach dem Lauf gelöscht, damit keine Caches als Evidence landen. Ergebnis: 59 grün, Regression 434 grün.
- **WIN-COST-1 v3:** Das PowerShell-Kind bekommt ein eigenes leeres `USERPROFILE`/`APPDATA`/`LOCALAPPDATA`. `$env:LOCALAPPDATA\Courier\…` führt damit nicht mehr zum Token; ein absoluter Pfad bleibt für denselben OS-Benutzer lesbar, das ist eine bekannte Grenze. Fehlt der Guard, startet PowerShell nicht (fail-closed). Ergebnis: 22 grün, Regression 189.
- **VC-1 v2:** #831 (H10) blockiert die Übernahme nur bei `.result` bzw. (autonom) bei `.partial`. Eine laufende Einheit ohne `.partial` wurde weiter übernommen, ebenso die Verlängerung durch einen fremden Prozess mit demselben Owner. v2: Abgelaufen heißt immer erst `reclaim`; `reclaim` verweigert, wenn bereits ein verifiziertes Ergebnis existiert. Der #831-Test „Case C“ wird bewusst angepasst. Ergebnis: 37 grün.
- **F-C1b:** `adapter_runner` prüft die Kosten vor dem Start von `local_shell` erneut. Das gilt auch für Tasks, die vor F-C1 ins Journal kamen. Ergebnis: 6 rot → 7 grün, Regression 195.
- **WQ-1b v2 + Crash-Punkt-Tests:** FINAL_DONE→release, release→nächster Claim, Claim→ASSIGNED (je genau einmal).

## Bekannte Grenzen (bewusst, dokumentiert)
- **Tripwire:** umbenannte oder verlinkte Binaries, Shell-Variablen, String-Konkatenation, Skriptdateien, `make`/npm-Skripte und Keychain-Logins werden nicht erkannt. Die tragenden Schichten sind die Kostenklasse `metered`, das leere Home und eine Umgebung ohne Zugangsdaten.
- **Windows-Label `free`/`local`:** bleibt 0 €, solange der Server-Dispatch (`server/app.py`, geschützt) keine Schätzung mitliefert.

---

# Teil 3 · finale Integrationspakete nach Review v8c (Trunk `e9d7f1f29`)

**Gültig sind die Dateien mit `_final` bzw. `v3`.** Frühere Versionen bleiben als Historie erhalten.

| Reihenfolge | Patch | SHA256 | Owner |
|---|---|---|---|
| 1 | `../l2_build_2026-10-23/F-C1_L2_controller_cost_admission.diff` + `../l2_build_2026-10-23/F-C1_followup_830_pin_to_regular_test.diff` | `6e695c34…` / `08dcfe78…` | L2 |
| 2 | `F-C1b_runner_cost_recheck.diff` | `c9fddfcd…` | L3 |
| 3 | `GUARD-1_v2_final.diff` | `fbd0f982…` | L2 (neue Datei) |
| 4 | `H12_v3_final.diff` | `11301d22…` | L4 |
| 5 | `WIN-COST-1_v3_final.diff` | `db6d966d…` | Cursor Windows |
| 6 | `WQ-1b_v2_lease_recovery.diff` | `8451444a…` | Queue |
| 7 | `VC-1_v3_on_e9d7f1f.diff` | `a8bdc737…` | Google |
| 8 | `../auto_continue_2026-10-23/CDX-COST-1_codex_bridge_costgate.diff` | `dfbb21b9…` | Codex-Bridge |
| 9 | `PE-1_provider_exec_overflow.diff` | `b021cf95…` | L3 |

**Gesamtprobe final (VERIFIED):** Trunk + 1–9 → **4239 passed, 16 skipped, 5 xfailed, 0 failed** (rc=0, `evidence/COMBINED_full_suite_e9d7f1f_final.log`).

Review v8c: 3 P1 und 7 P2 gefunden. Alle P1 und die P2 zu Bypass, Fehlalarmen, Laufzeit, Userinfo, Secret-Namen und Aufräumen sind behoben. Offen bleiben zwei P2: das Race zwischen `reclaim` und Renewal (nur entschärft) und die git-Identität im leeren Home (dokumentiert).
- **VC-1 v3:**
  - Erneuern nur mit Prozess-Nonce statt PID, denn PIDs werden in Containern und unter Windows wiederverwendet.
  - `reclaim` verweigert auch bei vorhandenem `checkpoint.json`. Das bisher geprüfte `.result` schreibt niemand.
  - `reclaim` verschiebt erst atomar und prüft dann. Eine zwischenzeitliche Erneuerung wird zurückgelegt; das Race-Fenster ist damit nur entschärft, nicht geschlossen.
  - Neu ist CLI `--reclaim WK --actor --reason`. Die Meldung unterscheidet abgelaufen und aktiv.
  - Ergebnis: 41 grün.
- **GUARD-1 v2:**
  - Eigener Scanner, der Anführungszeichen beachtet. `git commit -m "a; claude"` gilt nicht als Befehl, `$(…)` und Backticks schon, auch in doppelten Anführungszeichen.
  - Inline-Code von `python`/`node` wird auch im Daemon-Pfad erkannt, ebenso `$out = claude`, `start "" codex`, `wsl codex` und `gh copilot`.
  - Eingaben über 64 KB werden fail-closed abgelehnt; zuvor war der Tokenizer quadratisch langsam.
  - Tiefe Verschachtelung löst keine Ausnahme aus. Userinfo nur mit Token wird erkannt (`https://ghp_x@…`), dazu weitere Secret-Namen (PASSPHRASE, BEARER, JWT …).
  - Ergebnis: 154 grün.
- **H12 v3 / WIN v3:**
  - Fehler bei `mkdtemp` werden zu `LocalShellError`.
  - Das Aufräumen entfernt schreibgeschützte Dateien (Windows) und nutzt unter Python 3.12 `onexc`.
  - Ergebnis: 61 + 340 grün.
- **Dokumentierte Grenze:** Im leeren Home fehlt die git-Identität aus `~/.gitconfig`. Ein `local_shell`-Task, der committen soll, übergibt `GIT_AUTHOR_*`/`GIT_COMMITTER_*` in `params.env` (erlaubt).
