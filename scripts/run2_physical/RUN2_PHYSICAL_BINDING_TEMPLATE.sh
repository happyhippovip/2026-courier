#!/usr/bin/env bash
set -eou pipefail

# MAC HNI 11: RUN 2 (RESTART) COMMAND BINDER TEMPLATE
# Must bind to the same {{FINAL_SHA}} and point to the completed RUN 1's durable ledger/state.

FINAL_SHA="{{FINAL_SHA}}"
RUN1_DIR="/tmp/courier_run1_${FINAL_SHA}"
TARGET_DIR="/tmp/courier_run2_${FINAL_SHA}"

echo "Starting RUN 2 restart binding template script"
echo "Target SHA: ${FINAL_SHA}"
echo "Run 1 Source Dir: ${RUN1_DIR}"
echo "Run 2 Target Dir: ${TARGET_DIR}"

mkdir -p "${TARGET_DIR}/evidence"

# Confirm RUN 1 PASS before proceeding
if [ ! -f "${RUN1_DIR}/evidence/run1_exit_code.txt" ] || [ "$(cat ${RUN1_DIR}/evidence/run1_exit_code.txt)" != "0" ]; then
    echo "ERROR: RUN 1 did not PASS. Aborting RUN 2."
    exit 1
fi

echo "Executing proof restart run command..."
python3 scripts/run_physical_restart.py --sha "${FINAL_SHA}" --state-dir "${RUN1_DIR}" --evidence-dir "${TARGET_DIR}/evidence" > "${TARGET_DIR}/evidence/run2_stdout.log" 2> "${TARGET_DIR}/evidence/run2_stderr.log"

echo "Command completed."
echo "Artifacts stored in ${TARGET_DIR}/evidence/"
