# AG ORIGINAL 18 AGENTS RECOVERY — V16 (2026-10-09)

**Host:** macOS 26.6.2, Intel x86_64 MacBook Pro, 16 GB RAM (Darwin x86_64, NOT Windows).  
**Session / Tool:** Google AntiGravity Mac (`GOOGLE_ANTIGRAVITY_MAC`).  
**Integration Branch:** `integration/v1` (Lokal: `muse/bridge-ledger-controller`, Commit `18c8eb336`).  
**Status:** Canonical Local Archaeology & Verification Checkpoint.

---

## 1. ORIGINAL_18_AGENT_INVENTORY

Die historische Zahl „18“ entstammt dem Agenten-Katalog [`docs/agent-warehouse/AGENT_CATALOG.json`](file:///Users/user/Downloads/2026-courier/docs/agent-warehouse/AGENT_CATALOG.json) und der Studio-Visualisierung [`studio/studio.js`](file:///Users/user/Downloads/2026-courier/studio/studio.js) (erster Commit `34cffc7ea`, 2026-08-30). Zusammen mit dem Bodyguard-Pool umfasst die Nomenklatur die 18 Kernrollen:

| # | AGENT_ID | HISTORICAL_ROLE | IMPLEMENTATION_PATH / EVIDENCE | V1 STATUS |
|---|---|---|---|---|
| 1 | `agent-chief-commander` | Zentraler Orchestrator | `scripts/run_chief_commander.py` | CONFIGURED / WORKING |
| 2 | `agent-antigravity-bridge` | AntiGravity Workflow Bridge | `scripts/run_antigravity_bridge.py` | CONFIGURED / VERIFIED |
| 3 | `agent-codex-bridge` | Codex Task Runner Bridge | `scripts/run_codex_bridge.py` | CONFIGURED / REACHABLE |
| 4 | `agent-thought-curator` | Ideen- & Gedankensynthese | `scripts/run_thought_curator.py` | CONFIGURED / VERIFIED |
| 5 | `agent-update-steward` | Context Sync & Snapshot-Steward | `scripts/run_context_sync.py` | CONFIGURED / VERIFIED |
| 6 | `agent-academy-teacher` | Lektions-Erstellung | `scripts/run_academy.py` | CONFIGURED / VERIFIED |
| 7 | `agent-academy-director` | Adoption Gate & Prüfer | `scripts/run_academy.py` | CONFIGURED / VERIFIED |
| 8 | `agent-snitch` | Host-Guardian & Überwachung | `schemas/snitch_event.json`, `scripts/host_guardian.py` | CONFIGURED / REACHABLE |
| 9 | `agent-bodyguard-pool` (8 Slots: Alpha–Hotel) | Bounded Reserve Hosts | `scripts/run_bodyguards.py` | CONFIGURED / STANDBY |
| 10 | `smart-resource-router` | Dynamisches Routing | `studio/studio.js` (UI / Router-Logik) | PARTIAL (Prompt/Catalog) |
| 11 | `agent-human-gate-monitor` | Freigabe-Überwachung | `studio/studio.js` | PARTIAL (Prompt/Catalog) |
| 12 | `agent-courier-relay` | Event-Weiterleitung | `scripts/run_chief_relay_cycle.py` | CONFIGURED / REACHABLE |
| 13 | `agent-architect` | Systemarchitektur | `docs/agent-warehouse/AGENT_CATALOG.json` | DISCOVERED (Catalog) |
| 14 | `agent-treasurer` | Kosten & Token-Ökonomie | `events/academy/economics.json` | CONFIGURED / VERIFIED |
| 15 | `agent-librarian` | Wissens- & Memory-Ablage | `AGENT_CATALOG.json` | DISCOVERED (Catalog) |
| 16 | `agent-designer` | UI/UX & Studio Layout | `AGENT_CATALOG.json` | DISCOVERED (Catalog) |
| 17 | `agent-salesman` | B2B & Kommerzielles Alignment | `docs/business/COURIER_BUSINESS_OFFERINGS_2026-10-09.md` | WORKING |
| 18 | `muse-runtime` | Muse Worker Integration | `AGENT_CATALOG.json` | CONFIGURED / REACHABLE |

---

## 2. LOCAL_ANTIGRAVITY_EVIDENCE

Eine Tiefenanalyse des lokalen AntiGravity-Zustands auf dem Mac ergab:
- **Lokale AG-Konfiguration:** `~/.gemini/antigravity/`
  - `courier_canonical.db`: Schema vorhanden (17 Tabellen wie `missions`, `attempts`, `execution_events`, `duty_cycle_state`), jedoch **0 Datenzeilen** (nur `schema_metadata: 1`).
  - `brain/`: 136 Brain-Verzeichnisse gescannt.
  - Historische AG-Subagenten-Definitionen (`agent.md`): Exakt 6 Subagenten wurden in früheren Brain-Sitzungen definiert (`c61b931a` am 2026-08-29: `courier_antigravity_bridge`, `google_writer`, `market-defense-builder`, `symphony-worker`, `windows-validator`; `11581869` am 2026-09-28: `courier-research-lane`). Diese sind isoliert conversation-scoped und nicht global im System geladen.
  - Es existiert kein globales Verzeichnis `~/.gemini/agents/`.
- **Repository `.agents/`:**
  - `.agents/rules/NO_GREP_FAMILY.md`: Verbietet unkontrollierte grep-Scans.
  - `.agents/skills/courier-orchestrate/SKILL.md`: Autorisierte Orchestrierungs-Skill.
  - `.agents/skills/courier-night-loop/SKILL.md`: Gedeckelte serielle Muse-Arbeitsschleife.

---

## 3. MISSING_CONFIGURATIONS

1. **Kein globales AntiGravity-Agenten-Registry-Verzeichnis:** AntiGravity lädt Subagenten nur zur Laufzeit per Tool (`define_subagent` / `invoke_subagent`) oder über Skills. Es gibt kein automatisches Laden von Agenten außerhalb der aktiven Session.
2. **Catalog $\neq$ Runtime Authority:** `AGENT_CATALOG.json` ist als `inventory_only_not_runtime_authority` klassifiziert. Es gibt keinen automatischen Controller-Sync für Katalog-Rollen ohne expliziten Worker-Adapter.
3. **Bridge-Runner $\neq$ V1 Worker Adapter:** Die Skripte `run_antigravity_bridge.py` und `run_codex_bridge.py` interagieren über Event-JSONs, sind aber in `courier_worker/adapter_bridge.py` (`ADAPTERS = {"synthetic", "local_shell"}`) nicht als native V1-Worker eingetragen.

---

## 4. RECOVERABLE_AGENTS

Sofort operational nutzbar über bestehende Courier-Skripte ohne Neuentwicklung:
1. **`agent-chief-commander`**: Ausführbar via `python3 scripts/run_chief_commander.py`.
2. **`agent-update-steward`**: Ausführbar via `PYTHONPATH=. python3 scripts/run_context_sync.py --refresh` (erzeugt verifizierte Snapshots `v63`/`v64`).
3. **`agent-academy-director` & `agent-academy-teacher`**: Ausführbar via `PYTHONPATH=. python3 scripts/run_academy_demo.py` (vollständiger 6-Stufen-Lifecycle testiert).
4. **`agent-antigravity-bridge`**: Ausführbar via `python3 scripts/run_antigravity_bridge.py` (Deduplizierung & ACK verifiziert).
5. **`agent-bodyguard-pool` (`BG-01` bis `BG-08`)**: Ausführbar via `python3 scripts/run_bodyguards.py --status` (8/8 in STANDBY).

---

## 5. HOST_DIFFERENCES (MAC VS. WINDOWS)

| Aspekt | macOS (Aktueller Host) | Windows (Zielhost für EXE) |
|---|---|---|
| **OS & Architektur** | Darwin x86_64 (Intel 16 GB RAM) | Windows 10/11 x64 |
| **Worker-Runtime** | POSIX Shell (`local_shell`), Python Daemon | `scripts/windows_worker/` (Inno Setup, C# Launcher, BAT/PS1) |
| **Prozess-Schutz** | `HEAVY_JOB_LIMIT = 1`, EMFILE-Schutz | Job Objects (`KILL_ON_JOB_CLOSE`), Mutex `Local\CourierV1` |
| **Status-Diagnostik** | Headless Status L0, Terminal Logs | Headless Status L0, `status.bat`, `stop.bat` via PID |
| **V1 Packaging** | Nicht Ziel für V1 EXE | PyInstaller onedir + Per-User Inno Setup (`CourierSetup-v1.exe`) |

---

## 6. REGISTRATION_GAPS

1. **Adapter-Bridge Allowlist Gap:** In `courier_worker/adapter_bridge.py` sind aktuell nur `synthetic` und `local_shell` als V1-Adapter registriert. Die Provider-Bridges (`run_antigravity_bridge.py`, `run_codex_bridge.py`) laufen als separate Event-Wrapper.
2. **L2/L3 Provider Overlap:** PR #266 (L2) und PR #141 (L3) beanspruchen beide die Provider-Allowlist. Dieser Konflikt muss vor einer Registrierung weiterer Agenten-Adapter auf Trunk durch L1 konsolidiert werden.
3. **Ledger-Persistence Gap:** In `courier_canonical.db` wurden historisch keine Missions-Zeilen persistiert. Der echte V1 Ledger liegt im SQLite Event Log (`courier.db`, getestet in `./test_hub/courier.db` mit 10 Events und 6 Tasks).

---

## 7. SAFE_ACTIVATION_PLAN

1. **Schritt 1 — L1 Trunk Landing abwarten:**
   - Warten, bis Lane L1 PR **#377** (Submodule Gitlink Fix), gefolgt von PR **#351** und **#349** gemergt hat.
2. **Schritt 2 — Einzellauf-Aktivierung über vorhandene Runner:**
   - Keine gleichzeitige Massenaktivierung von 18 Prozessen.
   - Jeder Agent wird seriell über seinen existierenden Runner gestartet (`run_context_sync.py`, `run_academy.py`, `run_antigravity_bridge.py`).
3. **Schritt 3 — Verifikation durch Ledger-Receipt:**
   - Ein Agent gilt erst als reaktiviert, wenn:
     - Ein Claim erzeugt wurde.
     - Die Ausführung erfolgreich quittiert wurde (`events/academy/deliveries/ack-...json`).
     - Ein Ledger-Eintrag / Context-Snapshot existiert.
4. **Schritt 4 — Bounded Concurrency wahren:**
   - Strikte Einhaltung von `HEAVY_JOB_LIMIT = 1` auf dem Mac.
   - Kein Start unkontrollierter Muse- oder Subagenten-Schwärme.
