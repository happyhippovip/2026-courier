#!/bin/bash

echo "=========================================="
echo "   INITIALIZING LEDGER ENVIRONMENT        "
echo "=========================================="

echo "[1/4] Verifying Directory Structures..."
mkdir -p ops/ai/wall_ledger
mkdir -p ops/ai/wall_results
mkdir -p ops/ai/wall_claims
echo "✅ Directories ready."

echo "[2/4] Enforcing Git Pre-commit Hook..."
if [ -f ".git/hooks/pre-commit" ]; then
    echo "✅ Pre-commit hook active. Ledger breaks will block commits."
else
    echo "⚠️ Pre-commit hook missing! (Run git init if needed)"
fi

echo "[3/4] Running Cryptographic Auto-Repair..."
if [ -f "ledger_repair.py" ]; then
    ./ledger_repair.py
else
    echo "⚠️ ledger_repair.py not found!"
fi

echo "[4/4] Final Integrity Audit..."
if [ -f "ledger_integrity_check.py" ]; then
    ./ledger_integrity_check.py
else
    echo "⚠️ ledger_integrity_check.py not found!"
fi

echo "=========================================="
echo " ✅ ENVIRONMENT PREPARED FOR AI WORKERS   "
echo " Please ensure agents read ops/ai/LEDGER_HANDOFF_PROTOCOL.md"
echo "=========================================="
