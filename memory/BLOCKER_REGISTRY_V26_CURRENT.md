# COURIER SYMPHONY — CANONICAL BLOCKER REGISTRY (V26)
**Datum:** 2026-10-10  
**Status:** DEDUPLIZIERT · EVIDENZ-BASIERT · ZERO-SPEND  
**North Star:** Rule 0.000000000 — FINISH THE PRODUCT  

---

## 1. ZENTRALE BLOCKER REGISTRY (DEDUPLIZIERT)

### BLK-01
- **BLOCKER_ID:** BLK-01
- **HOST:** Multi-Host (GitHub Actions CI / Local Checkouts)
- **PROVIDER:** GitHub
- **SYMPTOM:** Checkout-Fehler auf `integration/v1`: `fatal: No url found for submodule path '.carrier-wtv-20261007' in .gitmodules`. Test `tests/test_repo_hygiene.py::test_no_gitlinks_without_gitmodules` schlägt fehl. Alle PRs gegen `integration/v1` scheitern am Customer-Reality-Gate.
- **ROOT_CAUSE:** Merge `149bf1dda` hat versehentlich zwei Gitlinks (`.carrier-wtv-20261007` und `.wt-evidence`) mit Modus 160000 eingecheckt, ohne dass ein korrespondierender Eintrag in `.gitmodules` existiert.
- **EVIDENCE:** GitHub PR #377 (`cursor/drop-stray-gitlinks-03ae`), `tests/test_repo_hygiene.py`, CI Runs 37900550554/66 @ `2cc9c89e`.
- **OWNER:** Lane L1 Integration / Human Operator (Dennis)
- **SEVERITY:** CRITICAL (Trunk Blocker)
- **DEPENDENCIES:** Keine
- **CHEAPEST_SAFE_FIX:** PR #377 von Draft auf Ready setzen und nach `integration/v1` mergen (Kosten: 0,00 €).
- **ALTERNATIVE:** Direkter L1-Commit auf `integration/v1` mit `git rm .carrier-wtv-20261007 .wt-evidence`.
- **AUTOMATABLE:** Ja (`gh pr merge 377 --squash`)
- **HUMAN_REQUIRED:** Ja (Merge-Genehmigung gem. Single-Writer-Regel)
- **ACCEPTANCE_TEST:** `git submodule foreach --recursive true` exits 0; `pytest tests/test_repo_hygiene.py` besteht 4/4.
- **STATUS:** ACTIVE_BLOCKED_WAITING_ON_HUMAN

---

### BLK-02
- **BLOCKER_ID:** BLK-02
- **HOST:** macOS (MacBook Pro 16GB)
- **PROVIDER:** Local Darwin Host
- **SYMPTOM:** Swap bei 8.437 MB / 9.216 MB (nur 778 MB frei). Launchd Service `com.couriersymphony.dev.muse-night` beendet sich mit Code 75 (`EX_TEMPFAIL`). Gefahr von Kernel Panics (Watchdog Timeout).
- **ROOT_CAUSE:** Unkontrollierte Terminal-/Fenster-Walls und speicherintensive Browser-Tabs haben RAM erschöpft und aggressiven Swap erzwungen.
- **EVIDENCE:** `sysctl vm.swapusage` (used=8437.75M), Datei `/Users/user/.courier/dev-night/RESOURCE_PAUSE` vorhanden.
- **OWNER:** Host Guardian / Mac Chief
- **SEVERITY:** HIGH (Systemstabilitätsrisiko)
- **DEPENDENCIES:** Host Memory Reclaim
- **CHEAPEST_SAFE_FIX:** Unnötige Programme/Tabs schließen; Marker `RESOURCE_PAUSE` unangetastet lassen, bis Swap < 4.000 MB ist. Max 1 Heavy-Job einhalten.
- **ALTERNATIVE:** Einmaliger geordneter Neustart des MacBooks zur Bereinigung des Swap-Bereichs.
- **AUTOMATABLE:** Teilweise (RESOURCE_PAUSE schützt automatisiert)
- **HUMAN_REQUIRED:** Ja (Apps schließen / Neustart)
- **ACCEPTANCE_TEST:** `sysctl vm.swapusage` zeigt used < 4000M; `python -m courier_runtime.surfaces wall-check 2` gibt 0 zurück.
- **STATUS:** RESOURCE_PAUSED

---

### BLK-03
- **BLOCKER_ID:** BLK-03
- **HOST:** Mac & Windows
- **PROVIDER:** UI / Chat Clients (Claude, Muse, Antigravity)
- **SYMPTOM:** Mac-Session meldet 14 queued messages, Windows Antigravity 15 queued messages. Chats dequeuen wiederholte Prompt-Duplikate (z. B. 5x identischer V24/V26 Prompt).
- **ROOT_CAUSE:** Automatisierte UI-Loops oder mehrfaches manuelles Absenden enqueuen identische Masterprompts, bevor der vorherige Turn abgeschlossen ist.
- **EVIDENCE:** Konversations-Transkript mit identischen V24/V26-Nachrichten; Screenshot-Befunde.
- **OWNER:** Operator / Admission Gate
- **SEVERITY:** MEDIUM (Token-Verschwendung, Kontextüberlastung)
- **DEPENDENCIES:** BLK-04 (Admission Gate)
- **CHEAPEST_SAFE_FIX:** Keine neuen Prompts einreihen; unprogressierte Turns durch `courier_runtime/admission_gate.py` abweisen (`BLOCKED_NO_PROGRESS`). Kosten: 0,00 €.
- **ALTERNATIVE:** Warteschlange im Chatfenster manuell bereinigen bzw. idempotent abarbeiten lassen.
- **AUTOMATABLE:** Ja (`WindowAdmissionGate` dedupliziert Turns)
- **HUMAN_REQUIRED:** Ja (Keine weiteren Copy-Paste-Schleifen starten)
- **ACCEPTANCE_TEST:** `WindowAdmissionGate.evaluate()` blockiert identischen Fingerprint zuverlässig.
- **STATUS:** ACTIVE_MITIGATED_BY_GATE

---

### BLK-04
- **BLOCKER_ID:** BLK-04
- **HOST:** macOS
- **PROVIDER:** Muse Runner
- **SYMPTOM:** Muse Night Runner meldet: `Workspace /Users/user/Downloads/2026-courier is not trusted; skipping skills and plugins from .agents`. Skills werden übersprungen.
- **ROOT_CAUSE:** Muse IDE Sicherheitsbarriere fordert einmalige Bestätigung der Workspace-Freigabe.
- **EVIDENCE:** `/Users/user/.courier/dev-night/runner.log`.
- **OWNER:** Operator / Mac Chief
- **SEVERITY:** HIGH (Autonome Loop-Skills werden ignoriert)
- **DEPENDENCIES:** Muse Einstellungen
- **CHEAPEST_SAFE_FIX:** In der Muse-Oberfläche einmalig auf "Trust Workspace" für den Pfad klicken. Kosten: 0,00 €.
- **ALTERNATIVE:** Runner-Skripte direkt über Shell aufrufen (`scripts/mac_worker/run_2_mac.sh`), ohne Skill-Discovery.
- **AUTOMATABLE:** Nein (Sicherheitsgrenze von Muse)
- **HUMAN_REQUIRED:** Ja (1 Klick in Muse UI)
- **ACCEPTANCE_TEST:** Muse-Start ohne "not trusted"-Warnung im Log.
- **STATUS:** HUMAN_REQUIRED

---

### BLK-05
- **BLOCKER_ID:** BLK-05
- **HOST:** Multi-Host
- **PROVIDER:** Anthropic / Google / OpenAI
- **SYMPTOM:** `model_stream_first_event_timeout` nach langen Wartezeiten; Claude Wochenlimit erreicht; temporäre RESOURCE_EXHAUSTED Meldungen.
- **ROOT_CAUSE:** Upstream Provider-Latenzspitzen zu Stoßzeiten; kostenlose bzw. feste Account-Limits erschöpft.
- **EVIDENCE:** `/Users/user/.courier/dev-night/runner.log` (3x Timeout in 26 Min); `OPEN_ITEMS_MASTER_CURRENT.md` (Claude Limit Reset Sa 03:00).
- **OWNER:** Provider Connector / Controller
- **SEVERITY:** MEDIUM-HIGH
- **DEPENDENCIES:** Provider-Quotas & Reset-Zyklen
- **CHEAPEST_SAFE_FIX:** Deterministisches Backoff (`BACKOFF_UNTIL`-Marker) nutzen; in der Wartezeit rein lokale 0-EUR-Aufgaben (Modus B Verifikation) ausführen. Kosten: 0,00 €.
- **ALTERNATIVE:** Scoped Failover auf autorisierten Zweitprovider (z. B. Gemini Flash) gem. `PROVIDER_SESSION_HANDOVER_RULE.md`.
- **AUTOMATABLE:** Ja
- **HUMAN_REQUIRED:** Nein
- **ACCEPTANCE_TEST:** `test_stream_timeout_retry_backoff` verifiziert sanftes Schlafen statt Absturz.
- **STATUS:** ACTIVE_HANDLED_BY_BACKOFF

---

### BLK-06
- **BLOCKER_ID:** BLK-06
- **HOST:** Windows CI
- **PROVIDER:** GitHub Actions
- **SYMPTOM:** PR #365 Windows-CI rot — alle 3 Golden-Tests scheitern an Byte-Count-Differenzen.
- **ROOT_CAUSE:** Git CRLF-Translation wandelt unter Windows Zeilenenden von `\n` in `\r\n`, wodurch Byte-Zähler in Assertions abweichen.
- **EVIDENCE:** `MUSE_MAC_V23_RESULT_2026-10-09_MUSE.md` Zeile 7.
- **OWNER:** Lane L1 Integration / Lane L4 Verifier
- **SEVERITY:** MEDIUM (PR #365 blockiert)
- **DEPENDENCIES:** PR #365 Branch Update
- **CHEAPEST_SAFE_FIX:** Test-Fixtures im Binärmodus (`rb`) laden oder CRLF vor Byte-Count normalisieren. Kosten: 0,00 €.
- **ALTERNATIVE:** `.gitattributes` um `eol=lf` für `tests/golden/**` ergänzen.
- **AUTOMATABLE:** Ja
- **HUMAN_REQUIRED:** Nein
- **ACCEPTANCE_TEST:** `pytest tests/golden/` läuft grün auf Windows Runner.
- **STATUS:** WAITING_FOR_PR_UPDATE

---

### BLK-07
- **BLOCKER_ID:** BLK-07
- **HOST:** Multi-Host
- **PROVIDER:** Antigravity Bridge
- **SYMPTOM:** `scripts/run_antigravity_bridge.py:282-309` gibt bei bloßem Fixture-Lesen pauschal `verdict: "PASS"` zurück.
- **ROOT_CAUSE:** Veralteter Mock-Zweig aus der Prototypen-Phase wurde fälschlicherweise als Erfolgs-Pfad belassen.
- **EVIDENCE:** Quellcode `scripts/run_antigravity_bridge.py:286`, synthetische Receipt `deliv-887b5cbc.json` (1.07ms Dauer).
- **OWNER:** Lane L4 Verifier / Lane L1 Integration
- **SEVERITY:** HIGH (Täuschung der Verifikation, Assurance-Bruch)
- **DEPENDENCIES:** Keine
- **CHEAPEST_SAFE_FIX:** Synthetischen Zweig auf `verdict: "UNVERIFIED_MOCK"` umstellen oder echten Verifier-Aufruf erzwingen. Kosten: 0,00 €.
- **ALTERNATIVE:** Regressionstest `test_execute_bridge_rejects_synthetic_fixture_summary_as_verified_product_pass` vorschalten.
- **AUTOMATABLE:** Ja
- **HUMAN_REQUIRED:** Nein
- **ACCEPTANCE_TEST:** `pytest tests/test_run_antigravity_bridge.py` scheitert bei synthetischem PASS.
- **STATUS:** ACTIVE_FIX_DESIGNED

---

### BLK-08
- **BLOCKER_ID:** BLK-08
- **HOST:** macOS
- **PROVIDER:** Local Darwin Host
- **SYMPTOM:** Unklare Prozess-Custody: 7-8 Peer-Builder und Runner laufen parallel, Agenten wissen nicht, ob sie fremd oder verlassen sind.
- **ROOT_CAUSE:** Fehlende PID-/Session-Registrierung in dauerhaften Lock-Dateien.
- **EVIDENCE:** Screenshot-Befunde, `GROK_CHIEF_V7_RESPONSE_CHECKPOINT_2026-10-09_MUSE_DRAFT.md`.
- **OWNER:** Lane L3 Worker Host / Lane L2 Controller
- **SEVERITY:** MEDIUM (Gefahr unbedachten Prozess-Kills; Verstoß gegen Custody Protocol)
- **DEPENDENCIES:** `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`
- **CHEAPEST_SAFE_FIX:** Strikte Regel anwenden: Unbekannte Custody = Niemals beenden/repurposen. Auslaufen lassen.
- **ALTERNATIVE:** PIDs mit Terminal-TTYs korrelieren und in `events/locks/worker_custody.json` protokollieren.
- **AUTOMATABLE:** Ja
- **HUMAN_REQUIRED:** Nein
- **ACCEPTANCE_TEST:** Custody-Validator verweigert das Beenden fremder PIDs.
- **STATUS:** MONITORED_PRESERVED

---

### BLK-09
- **BLOCKER_ID:** BLK-09
- **HOST:** Multi-Host
- **PROVIDER:** Python Verifier
- **SYMPTOM:** `scripts/courier_verifier.py:117` stürzt mit `TypeError: unhashable type: 'dict'` ab, wenn Task-Artefakte Dict-förmig sind.
- **ROOT_CAUSE:** Verifier hashte den Task-Pfad ohne Typ-Prüfung (`isinstance(..., str)`).
- **EVIDENCE:** `ops/ai/live/WALL_02_SONNET_BLOCKER_HEAD_CHECK.md`.
- **OWNER:** Central Writer / Lane L4 Verifier
- **SEVERITY:** MEDIUM (Task bleibt in `RESULT_RECEIVED` hängen)
- **DEPENDENCIES:** Branch `fix-cb1-new`
- **CHEAPEST_SAFE_FIX:** Typ-Guard einbauen: `isinstance(path, (str, bytes))` prüfen; bei Fehler sauberes `FAIL` statt Exception. Kosten: 0,00 €.
- **ALTERNATIVE:** Schema-Validierung am API-Intake (`POST /goals`).
- **AUTOMATABLE:** Ja
- **HUMAN_REQUIRED:** Nein
- **ACCEPTANCE_TEST:** Task mit `{"path": {"nested": 1}}` liefert FAIL ohne Crash.
- **STATUS:** WAITING_FOR_CENTRAL_WRITER

---

### BLK-10
- **BLOCKER_ID:** BLK-10
- **HOST:** Windows
- **PROVIDER:** Inno Setup (`ISCC.exe`)
- **SYMPTOM:** `CourierSetup-v1.exe` liegt noch nicht als verifiziertes Windows-Artefakt vor.
- **ROOT_CAUSE:** Inno Setup Compiler ist Windows-spezifisch und kann auf Mac nicht nativ ausgeführt werden.
- **EVIDENCE:** `scripts/windows_worker/courier_installer.iss`, `tests/test_win_clean_machine_harness.py`.
- **OWNER:** Lane L6 Packaging / Windows Chief
- **SEVERITY:** HIGH (Meilenstein-Blocker: Windows EXE -> Clean-Machine Acceptance)
- **DEPENDENCIES:** Windows-Host oder Windows-CI-Runner
- **CHEAPEST_SAFE_FIX:** `powershell -ExecutionPolicy Bypass -File scripts\windows_worker\build_package.ps1` auf Windows-PC oder Windows-Runner ausführen. Kosten: 0,00 €.
- **ALTERNATIVE:** Inno Setup in Wine auf Linux-CI-Runner kompilieren.
- **AUTOMATABLE:** Ja
- **HUMAN_REQUIRED:** Nein (Windows-Agent oder Actions-Workflow)
- **ACCEPTANCE_TEST:** `CourierSetup-v1.exe` existiert mit SHA256 und besteht `/VERYSILENT`-Installation.
- **STATUS:** READY_FOR_WINDOWS_EXECUTION
