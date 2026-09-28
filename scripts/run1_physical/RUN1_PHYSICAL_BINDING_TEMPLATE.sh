#!/usr/bin/env bash
set -eou pipefail

# MAC HNI 01: RUN 1 COMMAND BINDER TEMPLATE
# Do not hardcode FINAL_SHA yet, use the {{FINAL_SHA}} placeholder.
# This script executes the physical run, capturing stdout/stderr and saving artifacts.

FINAL_SHA="{{FINAL_SHA}}"
TARGET_DIR="/tmp/courier_run1_${FINAL_SHA}"

echo "Starting RUN 1 binding template script"
echo "Target SHA: ${FINAL_SHA}"
echo "Target Dir: ${TARGET_DIR}"

mkdir -p "${TARGET_DIR}/evidence"

# Setup command packet
echo "Executing proof run command..."
python3 scripts/run_physical.py --sha "${FINAL_SHA}" --evidence-dir "${TARGET_DIR}/evidence" > "${TARGET_DIR}/evidence/run1_stdout.log" 2> "${TARGET_DIR}/evidence/run1_stderr.log"

echo "Command completed."
echo "Artifacts stored in ${TARGET_DIR}/evidence/"
