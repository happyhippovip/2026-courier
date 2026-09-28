# Family 15: Manual Pilot Onboarding & First-Start Checklist

Status: READY FOR TRIAL
Target Setup Time: Under 10 minutes. No complex installer required.

---

## 1. Step-by-Step Pilot Onboarding Flow

```
Step 1: Check Prerequisites (Python 3.9+, Git, 2GB free RAM)
   |
Step 2: Clone or Unpack Courier Directory
   |
Step 3: Export 2 Environment Variables (COURIER_API_KEY, LLM Provider Key)
   |
Step 4: Launch Staging Coordinator (`python -m server.app`)
   |
Step 5: Submit Initial Goal via CLI or Webhook (`python scripts/submit_goal.py`)
   |
Step 6: Confirm Goal Contract (Review Plain English Tasks & Bounds)
   |
Step 7: Observe Execution State (Transitions from QUEUED -> DISPATCHED -> RECONCILED)
   |
Step 8: Close Terminal / Sleep Laptop (Simulate Overnight Run)
   |
Step 9: Next Day Return: Open Terminal, Check Status -> Resumed exactly where left off!
   |
Step 10: Tally Pilot Metrics & Collect Feedback
```

---

## 2. Copy-Paste Rapid Setup Script

```bash
# 1. Enter repository
cd /path/to/2026-courier

# 2. Configure environment (replace with your keys)
export COURIER_API_KEY="pilot-secret-token"
export COURIER_VERIFIER_API_KEY="pilot-verifier-token"
export GEMINI_API_KEY="your-llm-api-key"

# 3. Verify health
python3 -c "from server.app import app; print('Courier Core Ready')"

# 4. Start isolated coordinator in background
PORT=8080 python3 -m server.app &

# 5. Check UI status
curl -s http://127.0.0.1:8080/health
```
