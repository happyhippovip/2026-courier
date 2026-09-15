#!/bin/bash
echo "Monitoring /tmp/overnight_final13.log for stop conditions..."
tail -f /tmp/overnight_final13.log | while read line; do
    echo "$line"
    if echo "$line" | grep -q "GOAL DEMONSTRABLY COMPLETE"; then
        echo "STOP CONDITION REACHED: GOAL_COMPLETE"
        exit 0
    fi
    if echo "$line" | grep -q "HUMAN_GATE_REQUIRED"; then
        echo "STOP CONDITION REACHED: HUMAN_GATE_REQUIRED"
        exit 0
    fi
    if echo "$line" | grep -q "CHIEF_QUOTA_EXHAUSTED"; then
        echo "STOP CONDITION REACHED: CHIEF_QUOTA_EXHAUSTED"
        exit 0
    fi
    if echo "$line" | grep -q "GLOBAL_SAFETY_OR_INVARIANT_BLOCKER"; then
        echo "STOP CONDITION REACHED: GLOBAL_SAFETY_OR_INVARIANT_BLOCKER"
        exit 0
    fi
    if echo "$line" | grep -q "NO_SAFE_USEFUL_WORK_ACROSS_ALL_FREE_SCOPES"; then
        echo "STOP CONDITION REACHED: NO_SAFE_USEFUL_WORK_ACROSS_ALL_FREE_SCOPES"
        exit 0
    fi
done
