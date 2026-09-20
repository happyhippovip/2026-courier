#!/usr/bin/env bash
# Courier Symphony Muse — AI operating system bootstrap.
# Idempotent: creates missing artifacts under <target>/ops/ai, NEVER
# overwrites existing files. Safe to run twice.
set -euo pipefail

TARGET="${1:-.}"
AI_DIR="$TARGET/ops/ai"
mkdir -p "$AI_DIR"

put() {
  # put <filename> : writes stdin to $AI_DIR/<filename> only if absent.
  local name="$1"
  local dest="$AI_DIR/$name"
  if [[ -e "$dest" ]]; then
    echo "KEEP  $name"
  else
    cat > "$dest"
    echo "CREATE $name"
  fi
}

put START_HERE.md <<'EOF'
# START_HERE — Courier Symphony Muse AI Operating System
BOUND_TO_CODE_HEAD: UNKNOWN
UPDATED_AT: UNKNOWN

Permanent short rule: PACKET FIRST. ONE WRITER. T0 → T1 → T2.
T3 BEFORE CODEX. CODEX ONLY WHEN INDEPENDENCE MATTERS. T4 ONLY AT BOUNDARIES.
BLOCKED TASK != BLOCKED PROJECT. LEDGER LAST. NO FAKE GREEN.

Read order: ARCHITECTURE_BASELINE.md → OWNERSHIP_MAP.yaml → SOURCE_MAP.md
→ DEFERRED_LEDGER_QUEUE.yaml → TEST_MAP.yaml → MORNING_REVIEW.md.
EOF

put ARCHITECTURE_BASELINE.md <<'EOF'
# ARCHITECTURE BASELINE
BOUND_TO_CODE_HEAD: UNKNOWN
UPDATED_AT: UNKNOWN

Metrics are UNKNOWN until measured. Never enter fake zeros.
GOOGLE_TASKS_PER_HOUR: UNKNOWN
MEAN_T1_SECONDS: UNKNOWN
MEAN_T2_SECONDS: UNKNOWN
T3_SECONDS: UNKNOWN
T4_SECONDS: UNKNOWN
FULL_SUITE_RUNS_PER_DAY: UNKNOWN
CODEX_PERCENT_USED_TODAY: UNKNOWN
CODEX_BOUNCE_RATE: UNKNOWN
PACKET_STARVATION_SECONDS: UNKNOWN
OWNERSHIP_COLLISIONS: UNKNOWN
HANGING_TESTS: UNKNOWN
ORPHAN_PROCESSES: UNKNOWN
EOF

put DAILY_REMINDER.md <<'EOF'
# DAILY REMINDER
PACKET FIRST. ONE WRITER. T0 → T1 → T2. T3 BEFORE CODEX.
BLOCKED TASK != BLOCKED PROJECT. LEDGER LAST. NO FAKE GREEN.

ZERO-HANG POLICY (status: POLICY unless noted IMPLEMENTED/VERIFIED):
- No generic killall. Every test-created process has owner_test_id,
  tracked PID, bounded lifetime, targeted cleanup.
- Target invariant: OWNED_CHILD_PROCESSES=0 after test completion.
EOF

put MORNING_REVIEW.md <<'EOF'
# MORNING REVIEW
BOUND_TO_CODE_HEAD: UNKNOWN
UPDATED_AT: UNKNOWN

## Current truth (populated by operator, never blind history)
LEDGER_STATE: UNKNOWN
GUARD_STATE: UNKNOWN
NEXT_ACTION: UNKNOWN
BLOCKERS: UNKNOWN
OVER_NIGHT: UNKNOWN
EOF

put CODEX_BUDGET.md <<'EOF'
# CODEX BUDGET — weekly controller
Codex is scarce independent verification. Optimize VERIFIED_OUTPUT /
CODEX_PERCENT, not raw usage. USER_REPORTED remaining percent only;
never fabricate usage telemetry. Missing review packet means
PACKET_INCOMPLETE: repair packet first, do not burn Codex on archaeology.
CODEX_PERCENT_REMAINING: USER_REPORTED UNKNOWN
EOF

put SOURCE_MAP.md <<'EOF'
# SOURCE_MAP — verified component locations
BOUND_TO_CODE_HEAD: UNKNOWN
UPDATED_AT: UNKNOWN
Populated by operator from current executable reality. UNKNOWN if unverified.
EOF

put OWNERSHIP_MAP.yaml <<'EOF'
# OWNERSHIP_MAP — who owns what (populated by operator)
bound_to_code_head: UNKNOWN
updated_at: UNKNOWN
owners: {}
EOF

put TEST_MAP.yaml <<'EOF'
# TEST_MAP — lanes (populated by operator)
bound_to_code_head: UNKNOWN
updated_at: UNKNOWN
lanes:
  T0: {purpose: syntax/import/isolation sanity, command: UNKNOWN}
  T1: {purpose: exact regression, command: UNKNOWN}
  T2: {purpose: affected component, command: UNKNOWN}
  T3: {purpose: fast adversarial truth suite, command: UNKNOWN}
  T4: {purpose: integration/full suite boundary, command: UNKNOWN}
package_candidates:
  pytest-timeout: USE_NOW
  pytest-xdist: TEST_FIRST
  pytest-testmon: TEST_FIRST
  pytest-picked: NOT_NEEDED
EOF

put FAILURE_SIGNATURES.yaml <<'EOF'
# FAILURE_SIGNATURES — observed failure shapes (populated by operator)
bound_to_code_head: UNKNOWN
updated_at: UNKNOWN
signatures: []
EOF

put DEFERRED_LEDGER_QUEUE.yaml <<'EOF'
# DEFERRED_LEDGER_QUEUE — real findings only, each with evidence
bound_to_code_head: UNKNOWN
updated_at: UNKNOWN
tasks: []
EOF

put WINDOWS_RUNTIME_MAP.md <<'EOF'
# WINDOWS RUNTIME MAP
BOUND_TO_CODE_HEAD: UNKNOWN
UPDATED_AT: UNKNOWN
WINDOWS_RUNTIME_SHA: UNKNOWN
WINDOWS_HEALTH: UNKNOWN
WINDOWS_DIRTY_STATE: UNKNOWN (Mac lane does not touch Windows)
EOF

put PHYSICAL_ACCEPTANCE_PLAN.md <<'EOF'
# PHYSICAL ACCEPTANCE PLAN
Software completion != physical acceptance. Physical claims require
observed process transitions, never mocks. Steps: UNKNOWN (populated).
EOF

put CUSTOMER_GATES.md <<'EOF'
# CUSTOMER GATES
Agreed order: safe preparation may proceed; preparation is never
completion of payment, customer contact, publication, public deployment,
pilot onboarding, or irreversible business action. Ledger remains last.
EOF

echo "bootstrap complete: $AI_DIR"
