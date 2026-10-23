# Final Safety Review V1 · 23.10.2026 · Claude Opus (nur lesend, Vorschläge für Owner)

Status-Wörter: VERIFIED (selbst ausgeführt) · REPORTED · UNKNOWN · BLOCKED. Keine Datei eines fremden Owners auf einem geteilten Branch geändert; alle Code-Vorschläge entstanden in Wegwerf-Worktrees und liegen hier nur als Patch.

## Heads und CI (abgerufen 23.10. ~11:45 UTC)
trunk `d5b19f1df` · #830 `8c4858692` (CI läuft: 6 success, 1 in progress) · #826 `7686b97f6` (1 failure: pytest windows) · #827 `4a136b88f` (nur Acceptance, 2 success) · #829 `1bcaf9299` (7 success) · #818 `642611465` (7 success).

## Mission 1 — F-C1 direkte Controller-Kostensperre (Owner L2)
**Befund (VERIFIED):** Alle HTTP-Aufrufer münden in `courier_core/serve.py:233` → `Controller.create_task`: Intake-Skripte (`courier_adapters/*_intake.py`, `ai_ranking_worker.py`), `courier_hub/demo.py`, `scripts/github_wake_inbox.py`, `scripts/ledger_v1_bridge.py`, `courier_hub/mission_chip.py`. Dort gibt es keine Kostenprüfung. Kostenpflichtig ist nur `provider_exec`; dessen eigene Sperre greift erst beim Worker vor dem Prozessstart — der Task ist dann schon im Journal angelegt und beansprucht (Stufe-2-Entwurf 7.3 verlangt „kein Journal-Effekt“).

**Vorschlag, rot→grün belegt (Wegwerf-Worktree auf `d5b19f1`):**
- Neuer Test `tests/controller/test_ctrl_cost_admission.py`: 17 Fälle. **Vorher 14 failed / 3 passed, nachher 17 passed.**
- **Variante B (empfohlen, `F-C1_variantB_compatible.diff`):** `cost_admission()` vor dem Journal-Append in `create_task`; Fehler `400 cost_blocked`. Sperrt immer bei `unknown_cost: true` / `cost_class: "unknown"` und bei ungültiger Angabe (NaN, inf, negativ, bool, String); `PAID_ADAPTERS = {"provider_exec"}` braucht immer eine endliche Angabe. Wirkung auf 31 auftragsanlegende Testdateien + golden: **437 passed, 1 failed** — der eine Fehlschlag (`test_windows_exe_build.py::test_stop_kills_the_child_process`) scheitert identisch auf unverändertem Trunk (VERIFIED), also vorbestehend.
- **Variante A (strikt, `F-C1_variantA_strict.diff`, nur Code):** jeder nicht als kostenlos gelistete Adapter, auch ein unbekannter, braucht eine Angabe. Fail-closed-er, aber **177 bestehende Tests rot**, weil Controller-Tests erfundene Adapter-Namen (`probe`, `s`, `a`) ohne Angabe nutzen. Owner-Entscheidung.
- Idempotenz: ein Replay mit gleichem `idempotency_key` bleibt Duplikat (Test enthalten); die Prüfung läuft vor dem Append, nichts wird geschrieben.
- Folge für #830: der strict-xfail-Pin `test_gap_direct_controller_create_task_bypasses_the_cost_gate` erwartet einen Status ≥ 400 als Rückgabewert; mit dem Fix wirft `create_task` `ApiError`. Der Pin wird dann rot (gewollt) und ist durch `pytest.raises(ApiError)` zu ersetzen.
- Grenze: der Bridge-Fall „Spec ganz ohne Kostenangabe“ mit Adapter `synthetic` bleibt in Variante B erlaubt (synthetic ist kostenlos); `unknown_cost: true` wird jetzt auch über den Bridge gesperrt.

## Mission 2 — F-K1/F-K2 Host-Loop (Owner L3, noch offen)
**Kontext (REPORTED aus `handoffs/taskpacket_c48_windows_kirby_driver_20261008.json`):** kein produktiver Runner ruft `host_loop` heute auf; das Risiko ist latent und wird scharf, sobald der Windows-Kirby-Treiber (C48) gebaut wird.

**Vorschlag, rot→grün belegt (Wegwerf-Worktree auf #830 `8c4858692`, `F-K1_F-K2_hostloop_proposal.diff`):**
- `provider_events.handle/drive` und `host_loop.run_once` erhalten optional `prove(workkey)`. `TURN_ENDED outcome=DONE` wird nur mit Journal-Beweis DONE (Beweis wird an den Checkpoint angehängt); ohne Prüfer oder ohne Beweis: Checkpoint gespeichert, Workkey bleibt beansprucht, Ergebnis `NOT_PROVEN`. BLOCKED/FAILED_FINAL unverändert.
- `host_loop.main` lädt Kirby jede Runde neu, unter demselben Lock `kirby.json.lock` wie `LedgerEngine`; neues `--rounds N` für begrenzte Läufe.
- Neue Tests `tests/test_host_loop_proof.py`: **vorher 4 failed / 1 passed, nachher 5 passed.** Gegenprobe: Kirby wieder dauerhaft im Speicher → 1 failed (Test misst das Verhalten, nicht nur Namen).
- **Bewusste Verhaltensänderung:** 8 bestehende L3-Tests (`test_host_loop.py` 3, `test_provider_events.py` 5) erwarten DONE auf Zuruf und müssen einen Prüfer mitgeben; der #830-Pin `test_gap_host_loop_provider_signal_marks_done_without_proof` wird damit wie vorgesehen rot (Marker entfernen). 112 weitere Tests der Suiten bleiben grün.
- Abhängigkeit: der Vorschlag importiert `_exclusive` aus `courier_runtime/ledger_engine.py` → setzt #830 voraus.

## Mission 3 — Stufe-2-Entwurf gegen den Code
| Aussage im Entwurf | Ergebnis | Beleg |
|---|---|---|
| Controller-Journal = Ausführungs-/FINAL-Beweis | **BESTÄTIGT** | Zustandsmaschine läuft im Append; COMPLETE nur nach `RESULT_ACCEPTED` vom Verifier; manipuliertes Journal → `degraded_readonly` (Abnahme-Proben `cld003/004/013`) |
| #830 = geschützter Zugang, kein eigener Dispatcher | **BESTÄTIGT mit Bedingung** | `LedgerEngine.next()` nutzt Kirbys Auswahl (`wake/deliver`), keine eigene Auswahl. Gilt nur, solange alle Kirby-Schreiber dasselbe Lock nehmen — heute nicht (F-K2, Vorschlag Mission 2) |
| #827 = Adapter, keine zweite Engine | **BESTÄTIGT mit Hinweis** | `ledger_v1_bridge.py`: „One invocation. No loop, no daemon, no scheduler.“ Hinweis: er persistiert eine eigene Sicht `ledger_bridge_state.json` mit `FINAL_DONE`; sie wird nur nach Controller-COMPLETE+verified gestempelt (Tests), ist also Projektion — bei Abweichung greift die CONFLICT/UNKNOWN-Regel des Entwurfs |
| **Keine zweite schreibende Queue** | **WIDERLEGT für den Ist-Stand** | Neben dem Controller gibt es vier unabhängige Claim-Speicher: `courier_runtime/continuity.py` (Kirby, `kirby.json`), `courier_core/work_queue.py` (nennt sich selbst „Canonical ledger-backed work queue“, JSONL), `scripts/verified_continuation.py` („Verified Continuation Engine“, eigene O_EXCL-Claim-Dateien und eigener CLAIM→…→NEXT-Zyklus), `scripts/local_swarm_claim.py` (`.courier_swarm/claims`). #830 baut auf Kirby; `work_queue.py` beansprucht die Kanonizität. Der Architecture Choice Record muss genau einen wählen |
| Keine Roh-Tokens in der Queue | **BESTÄTIGT für Kirby/Engine** | Kirby-`token` ist ein Fencing-Zähler (int), kein Credential. Die offenen `owner_token` liegen in den Muse-Wall-Slot-Dateien, nicht in Kirby (P0 separat) |
| Keine automatischen Replays bei Lease-Ablauf | **TEILWEISE** | Controller: `idempotent` wird nach Lease-Verlust automatisch neu versucht (gewollt, nur diese Klasse), nicht-idempotent → BLOCKED (Probe `cld006/cld008`). **`scripts/verified_continuation.py` übernimmt eine abgelaufene Claim-Datei neu, ohne Effekt-Abgleich** — widerspricht der Entwurfsregel. Vorschlag: Entwurf präzisieren („außer explizit idempotent“) und `verified_continuation` dem Owner melden |

## Verbleibende Gates
| Gate | Wer |
|---|---|
| F-C1 Variante wählen und umsetzen | L2 (Owner offen) |
| F-K1/F-K2 umsetzen, 8 Tests anpassen, nach #830 | L3 (Owner offen) |
| Architecture Choice Record: Kirby **oder** work_queue als einzige Workkey-Wahrheit; verified_continuation und local_swarm_claim einordnen | Dennis/L1 + Owner |
| Bridge-Kostensperre (#827), Stack-CI, #827↔#829 | Cursor Mac / Cursor Windows (bereits übergeben, nicht doppelt) |
| owner_token-Rotation P0, MERGE-GOs, Provider-GO | Dennis |
