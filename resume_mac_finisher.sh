#!/bin/bash
set -u

echo "================================================="
echo " Resuming MAC_AFTER_LEDGER_CONTINUOUS_FINISHER "
echo "================================================="

# Start daemon again using relaunch script
PROMPT_FILE="/tmp/courier-noidle/mac-after-ledger-prompt.txt"

# If it doesn't exist, try to recreate it
if [ ! -f "$PROMPT_FILE" ]; then
  mkdir -p /tmp/courier-noidle
  git show origin/coordination/autofill-task-seed-20260926:ops/ai/MAC_AFTER_LEDGER_CONTINUOUS_FINISHER_PROMPT.txt > "$PROMPT_FILE" || echo "Warning: failed to fetch prompt from git"
  git show origin/coordination/autofill-task-seed-20260926:scripts/relaunch_agy_prompt_loop.sh > /tmp/courier-noidle/relaunch.sh || echo "Warning: failed to fetch relaunch script"
  chmod +x /tmp/courier-noidle/relaunch.sh
fi

echo "Starting agy daemon in the background..."
nohup bash /tmp/courier-noidle/relaunch.sh "$PROMPT_FILE" > /tmp/courier-noidle/nohup.out 2>&1 &
echo "Done! The daemon is polling for PRE_CODEX readiness."
echo "You can monitor the logs at: logs/agy-relauncher/"
