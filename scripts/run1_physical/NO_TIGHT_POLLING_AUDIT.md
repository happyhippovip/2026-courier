# NO TIGHT POLLING AUDIT RULES

## Principle
Agent execution loops, synchronization loops, and physical test wrappers MUST NOT tight-poll. They must use exponential backoff, interrupt-driven events, or minimum sleep floors to prevent 100% CPU lockups.

## Auditable Guard
Any `while` loop waiting on state MUST include a minimum `sleep 1`.

```bash
#!/usr/bin/env bash
# Audit Script against Courier Runtime Source

TIGHT_LOOPS=$(grep -n -A 5 "while " scripts/run_physical*.py | grep -v "sleep" | grep -v "await" | grep -v "wait")
if [ ! -z "$TIGHT_LOOPS" ]; then
   echo "CRITICAL: Potential tight polling loops detected without sleep/wait mechanisms."
   echo "$TIGHT_LOOPS"
   # exit 1 (disabled until final binding logic)
fi
```
