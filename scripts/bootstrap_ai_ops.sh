#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
OPS="$ROOT/ops/ai"
mkdir -p "$OPS"

write_if_missing() {
  local file="$1"
  if [[ -e "$file" ]]; then
    echo "KEEP existing: $file"
    return
  fi
  cat > "$file"
  echo "CREATE: $file"
}

echo "Courier Symphony Muse AI ops bootstrap"
echo "Target: $OPS"
echo
echo "Canonical tracked templates live in ops/ai/."
echo "This bootstrap is intentionally non-destructive."
echo
echo "If files already exist, they are preserved."
echo "Use Git to review changes before staging."
echo
echo "Expected files:"
for name in   START_HERE.md MASTER_OPERATING_SYSTEM.md ARCHITECTURE_BASELINE.md   DAILY_REMINDER.md MORNING_REVIEW.md CODEX_BUDGET.md SOURCE_MAP.md   OWNERSHIP_MAP.yaml TEST_MAP.yaml FAILURE_SIGNATURES.yaml   DEFERRED_LEDGER_QUEUE.yaml WINDOWS_RUNTIME_MAP.md   PHYSICAL_ACCEPTANCE_PLAN.md CUSTOMER_GATES.md
do
  if [[ -e "$OPS/$name" ]]; then
    echo "OK   $OPS/$name"
  else
    echo "MISS $OPS/$name"
  fi
done

echo
echo "Next:"
echo "  git status --short"
echo "  git diff -- ops/ai scripts/bootstrap_ai_ops.sh"
echo
echo "Never auto-overwrite populated artifacts."
