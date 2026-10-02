# RUN_1 Command Sheet (Mac)

This command sheet is designed for the Mac Physical Runner to execute `RUN_1` flawlessly and collect evidence.

## Prerequisites
1. Ensure `port 8080` is completely free.
2. Ensure you are on branch `coordination/mac-handoff-20260928`.
3. Ensure no stale `ledger_run1.db` exists.

## Step 1: Bootstrap Repository
```bash
git fetch origin coordination/mac-handoff-20260928
git checkout coordination/mac-handoff-20260928
```

## Step 2: Initialize RUN_1
```bash
bash scripts/mac_worker/run_1_mac.sh
```

## Step 3: Verify Processes
Ensure all three background processes started successfully:
```bash
ps aux | grep "server.app"
ps aux | grep "scripts.integration_contract"
ps aux | grep "scripts.courier_verifier"
```

## Step 4: Verify Exactly Once Execution
Check `logs/server_run1.log`, `logs/worker_run1.log` and `logs/verifier_run1.log` to ensure Task A executed EXACTLY once and achieved `RECONCILED` state.

## Step 5: Save State Evidence
```bash
cp ledger_run1.db artifacts/run1/
```
