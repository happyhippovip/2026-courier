# WEBSITE_05: DOWNLOAD, INSTALLATION, SUPPORT & DEMO STORYBOARD

**MISSION**: `COURIER_WEBSITE_LAUNCH_PREP`  
**MODE**: `LONG_RUNNING_PREP` · `HOST=MAC`  
**STATUS**: Evidence-Gated Launch Preparation Artifact  
**OUTPUT FILE**: `/Users/user/Downloads/courier_work/muse_mac_wall/reports/WEBSITE_05_DOWNLOAD_AND_INSTALL.md`  
**GOVERNING PRINCIPLE**: Honest packaging. Do not promise 1-click installers where manual developer setup is currently required.

---

## 1. Download Page Structure (`/download`)

The download page presents a clean, honest setup guide for technical pilot participants. It avoids fake "Install App.dmg" buttons and provides exact, reproducible CLI instructions.

```
+──────────────────────────────────────────────────────────────────────────+
| COURIER SYMPHONY — PILOT DOWNLOAD & RUNNER SETUP                         |
+──────────────────────────────────────────────────────────────────────────+
| CURRENT RELEASE: v0.4.2-canary (macOS Apple Silicon & Intel)             |
| RELEASE DATE:    September 2026                                          |
| INTEGRITY:       SHA-256 Digest Verified                                 |
+──────────────────────────────────────────────────────────────────────────+
| 1. SYSTEM PREREQUISITES                                                  |
| 2. QUICKSTART INSTALLATION (VIRTUALENV / CLI)                            |
| 3. VERIFY LOCAL RUNNER HEALTH                                            |
| 4. LAUNCH FIRST SCOPED PILOT TASK                                        |
+──────────────────────────────────────────────────────────────────────────+
```

---

## 2. Installation Prerequisites & Verification

### 2.1 System Prerequisites
- **Operating System**: macOS 13.0 (Ventura) or newer (Apple Silicon M1/M2/M3/M4 or Intel x86_64).
- **Runtime**: Python 3.11 or Python 3.12 (standard official distribution).
- **Version Control**: Git 2.38+ installed and available in `$PATH`.
- **Disk Space**: 500 MB for local coordination state and execution worktrees.
- **Network**: Localhost access for local REST control plane (Port `8080` or designated canary port).

---

### 2.2 Quickstart Installation (Developer Pilot Mode)

```bash
# 1. Clone the pilot workspace runner
git clone https://github.com/courier-symphony/courier-runner.git
cd courier-runner

# 2. Create and activate a hermetic Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install core runner dependencies
pip install --upgrade pip
pip install -r requirements-core.txt

# 4. Run the preflight health check
python scripts/courier_verifier.py --preflight
```

### Expected Preflight Output:
```
[PREFLIGHT] Checking Python version: 3.11.8 (OK)
[PREFLIGHT] Checking disk write access in WORKSPACE: (OK)
[PREFLIGHT] Checking cryptographic hashing engine: SHA-256 (OK)
[PREFLIGHT] Checking local REST control plane connectivity: (OK)
[PREFLIGHT] RESULT: System is ready for Courier Pilot Task Execution.
```

---

## 3. Support & Incident Reporting Flow (`/support`)

When an autonomous task encounters an unexpected error or an unresolvable conflict, Courier provides a structured support flow rather than stranding the user:

```
[ Error Occurs ] ──► [ Generate Incident Card ] ──► [ Safe Local Quarantine ] ──► [ Direct Engineer Triage ]
```

### 3.1 Automated Incident Card Generation
If a task fails or halts at a human gate, Courier creates an **Incident Card** (`events/incidents/INC-<id>.json`):
- `WHAT_WAS_RUNNING`: The specific task ID, attempt ID, and worker PID.
- `LAST_VERIFIED_STATE`: The last step that achieved independent verification `PASS`.
- `WHAT_FAILED`: Exact stderr traceback, exit code, or verifier rejection reason.
- `SIDE_EFFECT_RISK`: Clear statement on whether any partial file writes occurred.
- `SAFE_TO_RETRY`: Boolean assessment of whether the failure is transient or fatal.
- `RESUME_POINT`: The exact checkpoint to restart from.

### 3.2 Human Support SLA (Pilot Customers)
- **Direct Slack/Discord Channel**: 1-on-1 private channel with core engineering team.
- **1-Click Diagnostics Export**: `courier report bundle --incident <id>` packages the sanitized incident card and state snapshot (scrubbed of confidential code bytes) for rapid debugging.

---

## 4. 60-Second Demo Storyboard (Video / Interactive Embed)

For the website homepage and product page, this storyboard outlines the 60-second video demo:

```markdown
### 00:00 - 00:10 | Act 1: The Setup
- **Visual**: Screen shows clean VS Code workspace with terminal.
- **Narration**: *"You give Courier one task in your project folder, and you step away from the keyboard."*
- **Action**: User types `courier run "Analyze API contracts and build mock fixtures"` and hits Enter.

### 00:10 - 00:25 | Act 2: Step A Execution & Verification
- **Visual**: Worker MAC-01 claims task; terminal logs code inspection; file `fixtures/mocks.json` appears on disk.
- **Narration**: *"Step A completes. But Courier doesn't assume it worked. An independent verifier reads the raw bytes from disk and recomputes the SHA-256 hash."*
- **Visual Overlay**: Proof Card flashes `VERIFY: PASS (sha256: 7f8a...33b1)`.

### 00:25 - 00:40 | Act 3: Autonomous Continuation ($A \rightarrow B$)
- **Visual**: Hand leaves mouse completely visible off camera.
- **Narration**: *"Watch the cursor: zero human clicks. The moment verification passes, Step B starts automatically."*
- **Visual**: Step B claims instantly; starts compiling TypeScript type definitions against verified mocks.

### 00:40 - 00:52 | Act 4: The Simulated Crash Test
- **Visual**: User deliberately opens Activity Monitor and kills the server process (`kill -9`).
- **Narration**: *"What if your computer crashes? Let's kill the process mid-run. We restart the server..."*
- **Visual**: Server reboots; terminal reads `central_state.json`. Status: `RESULT_READY_NO_REEXEC`.
- **Narration**: *"Courier reloads the exact state hash. Step A is never re-run. Work continues seamlessly."*

### 00:52 - 01:00 | Act 5: The Delivery & Proof Card
- **Visual**: Full green Proof Card renders on screen.
- **Narration**: *"Two steps finished, independently verified, zero human relays, crash survived. That is Courier Symphony."*
```

---

## 5. Download & Support Claim Discipline Registry

| Claim Element | Public Claim Statement | Currently Proven? | Evidence Source | Safe to Publish Now? |
| :--- | :--- | :---: | :--- | :---: |
| **DS-01** | Python virtualenv / CLI setup procedure | **YES** | `RV11_INSTALLATION_PREP.md`, local environment reproduction | **YES** (for technical pilots) |
| **DS-02** | Automated Incident Card creation on failure | **YES** | `RV13_INCIDENT_CARD.md`, `events/incidents/` schema | **YES** |
| **DS-03** | 1-Click native macOS .app installer | **NO** | Packaging and app signing is locked at Gate 7 | **NO** (Do not advertise DMG/EXE) |
| **DS-04** | 60-Second A->Verify->B Demo sequence | **YES** | Validated in test runner `verify_restart_proof_deterministic.py` | **YES** (as scripted demo) |
| **DS-05** | 24/7 Enterprise phone support | **NO** | Team is focused on engineering pilots; direct Discord/Slack only | **NO** (Only offer dedicated engineer chat) |
