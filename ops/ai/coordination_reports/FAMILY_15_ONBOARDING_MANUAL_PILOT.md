# Family 15: Manual Pilot Onboarding Checklist (<15 Minutes)

**Target Audience**: First Cohort Friendly Pilot Users (Developers / Power Users)  
**Requirement**: Zero Installer Requirement; Pure Local Shell Setup

---

## 1. Step-by-Step Onboarding Protocol

### Step 1: Pre-requisites Check (2 mins)
- Python 3.9+ installed (`python3 --version`).
- Git installed (`git --version`).
- 1 API Key for designated LLM provider (`OPENAI_API_KEY` or `GEMINI_API_KEY`).

### Step 2: Local Repo & Environment Setup (3 mins)
```bash
git clone <pilot-repo-url> 2026-courier && cd 2026-courier
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Configure Local Environment Secrets (2 mins)
Create `.env` file with minimal variables:
```bash
COURIER_SERVER=http://127.0.0.1:8080
COURIER_API_KEY=pilot-secret-user-token
COURIER_VERIFIER_API_KEY=pilot-secret-verifier-token
```

### Step 4: Launch Local Services (3 mins)
In terminal 1 (Coordinator):
```bash
python3 server/app.py
```
In terminal 2 (Independent Verifier):
```bash
python3 scripts/courier_verifier.py
```
In terminal 3 (Local Worker Daemon):
```bash
python3 scripts/mac_worker/daemon.py  # (or windows equivalent)
```

### Step 5: Input First Goal & Confirm Contract (3 mins)
```bash
python3 scripts/courier_cli.py goal submit "Run integration test suite and output summary"
```
The CLI renders the Goal Contract, displays acceptance criteria, and waits for single `[Y]` confirmation.

### Step 6: Next-Day Resume Test (2 mins)
1. Close all terminals / shut down laptop overnight.
2. Next morning: reopen terminals, restart services.
3. Observe CLI: status reads `RESUMED`, displays previous day's progress, and continues without prompting `continue`.

---

## 2. Tear-Down & Cleanup (1 min)
```bash
python3 scripts/courier_cli.py goal clean --all
```
Removes local state database and temporary artifact blobs completely.
