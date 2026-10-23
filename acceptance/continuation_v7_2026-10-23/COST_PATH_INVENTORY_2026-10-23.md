# Kostenrelevante Ausführungswege · Inventur (CLD-106) · Basis `d5b19f1`
Quelle: unabhängiger Subagent (nur lesend), Kernaussagen von Claude nachgeprüft (✔ = selbst im Code bestätigt).

| Pfad | Startet | argv aus Daten? | Kostenentscheidung vor Start? | erreichbar von | Risiko |
|---|---|---|---|---|---|
| `adapters/local_shell.py:222` ✔ | beliebige argv; **Kind erbt komplette Worker-Umgebung** (`env = dict(os.environ)`, nur `COURIER_CONTROLLER_TOKEN` entfernt) ✔ | ja | **nein** | V1-Worker-Dienst → `host.py` → `adapter_runner.py` | **HOCH** (Kosten + Schlüssel-Abfluss) |
| `scripts/windows_worker/daemon.py:328` | `powershell -EncodedCommand <instruction>` | ja | teilweise: `unknown` sperrt; fehlende Angabe wird 0.0 bei selbst erklärtem free/local/included_quota (`:294`); geprüft wird `windows_native`, nicht was das Skript aufruft | alter Windows-Worker | HOCH |
| `scripts/mac_worker/daemon.py:537` (`run_agy`) | `agy -p` | Prompt | teilweise: fehlende Angabe = 0.0 (`:504`) ✔ | alter Mac-Worker (launchd) | MITTEL-HOCH |
| `scripts/google_builder_worker.py:504` | `agy --model/--effort` aus Payload | Prompt, Modell, Effort | teilweise: fehlende Angabe = 0.0 (`:473`) — Fix in `cursor/google-builder-unknown-cost-4598`, **nicht gemergt** ✔ | `run_autonomous_loop` | MITTEL-HOCH |
| `scripts/gemini_worker_adapter.py:123` | `agy -p` | Prompt, Timeout ohne Obergrenze | teilweise (`:102`) — Fix in `cursor/gemini-missing-cost-4598`, **nicht gemergt** ✔ | manuell | MITTEL |
| `scripts/google_builder_worker.py:582` | `payload.command` | ja | nein | wie oben | MITTEL |
| `scripts/run_codex_bridge.py:376` | codex CLI | Prompt | **nein** (nur Label „ZERO_COST_ONLY“) | nur mit `--real-codex` (Standard aus) | MITTEL |
| `scripts/github_worker_adapter.py:275` | `gh workflow run` | Payload | nein | Dispatcher / Supervisor | NIEDRIG (Repo öffentlich ✔ → GitHub-gehostete Minuten kostenlos) |
| `courier_worker/adapters/provider_exec.py` | agy/muse, absoluter Pfad aus Host-Config | geprüfte Flags | **ja, fail-closed** (`admit_cost`, `evaluate_cost_gate` vor `_execute`) | V1-Worker-Dienst | NIEDRIG* |
| übrige (`workspace.py`, `ledger_tick.py`, `home_agent.py`, `kolibri_data.py`, Intake-Adapter) | feste Befehle / freie öffentliche Endpunkte | nein | nein | diverse | NIEDRIG |

\* vertraut der deklarierten Angabe; `muse_subscription` steht nicht in `resource_policy.json` → Muse-Starts sind heute ohnehin gesperrt.

## Lücken → Owner
| # | Lücke | Kleinster Fix | Owner |
|---|---|---|---|
| G-A | `local_shell`: keine Kostenentscheidung, volle Worker-Umgebung | Spec nur mit endlicher 0.0 + CostGate-Freigabe einer `local_shell`-Ressource; Kind bekommt eine kurze Umgebungs-Allowlist statt `os.environ` | L4 Adapter (+ Worker) — F-C1 im Controller ist zweite Linie, kein Ersatz |
| G-B | Default `estimated_cost_eur=0.0` in `mac_worker/daemon.py:504`, `gemini_worker_adapter.py:102`, `google_builder_worker.py:473`; free/local-Fallback `windows_worker/daemon.py:294` | `.get("estimated_cost_eur")` ohne Default (CostGate sperrt None); Gemini/Google-Builder: vorhandene Cursor-G2-Branches mergen statt neu bauen | scripts-Owner / Cursor (G2) |
| G-C | `run_codex_bridge` ohne CostGate | `CostGate.evaluate_spend_request("chatgpt_plus_codex", estimate)` vor `:376` | scripts-Owner |
| G-D | agy-Wege: Modell/Effort aus Payload, Gemini-Timeout unbegrenzt | Allowlist wie `provider_exec._agy_model`, Timeout-Obergrenze | scripts-Owner |
| G-E | Controller prüft nichts | F-C1 v2 landen; Schätzung im Journal festhalten | L2 |

UNKNOWN: ob der alte Windows-Daemon auf sauberen Maschinen noch als geplante Aufgabe installiert wird; ob `Workspace.run` produktiv aufgerufen wird.
