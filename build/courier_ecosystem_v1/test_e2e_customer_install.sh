#!/usr/bin/env bash
# End-to-end Customer Install Qualification Test
set -e

echo "[*] Building final ZIP for testing..."
cd ..
rm -f courier_ecosystem_v1_final.zip
zip -q -r courier_ecosystem_v1_final.zip courier_ecosystem_v1 -x "*/.courier_state/*" "*/logs/*"

echo "[*] Preparing clean-room /tmp extraction..."
rm -rf /tmp/courier_customer_test
mkdir -p /tmp/courier_customer_test
unzip -q courier_ecosystem_v1_final.zip -d /tmp/courier_customer_test

cd /tmp/courier_customer_test/courier_ecosystem_v1

echo "[*] Starting Ecosystem via Watchdog..."
python3 start_courier.py > start_log_fresh.txt 2>&1 &
PID=$!
sleep 5

echo "[*] Injecting Sequential Goals..."
echo "MISSION_ID: GOAL_1. EXPECTED_EFFECTS: proof_A.txt" | (cd motor && python3 inbox_manager.py receive)
sleep 1
echo "MISSION_ID: GOAL_2. EXPECTED_EFFECTS: proof_B.txt" | (cd motor && python3 inbox_manager.py receive)
sleep 1
echo "MISSION_ID: GOAL_3. EXPECTED_EFFECTS: proof_C.txt" | (cd motor && python3 inbox_manager.py receive)

echo "[*] Waiting for autonomous execution (15s)..."
sleep 15
echo "[*] Shutting down Watchdog..."
kill -INT $PID || true
sleep 2
kill -9 $(lsof -t /tmp/courier_customer_test/courier_ecosystem_v1/motor/.courier_state/motor.db 2>/dev/null) 2>/dev/null || true
# Kill via PID files
echo "Cleaning up processes via pidfiles..."
for PID_FILE in /tmp/courier_*.pid; do
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            kill -9 $PID || true
        fi
        rm -f "$PID_FILE"
    fi
done

echo "[*] Verifying Output..."
DONE_COUNT=$(sqlite3 /tmp/courier_customer_test/courier_ecosystem_v1/motor/.courier_state/motor.db "SELECT COUNT(*) FROM goals WHERE status='SATISFIED';")
FAIL_COUNT=$(sqlite3 /tmp/courier_customer_test/courier_ecosystem_v1/motor/.courier_state/motor.db "SELECT COUNT(*) FROM goals WHERE status='FAILED';")

if [ "$DONE_COUNT" -ge 3 ]; then
    echo "[+] E2E TEST PASSED: 3 Goals completed autonomously!"
    exit 0
else
    echo "[-] E2E TEST FAILED: Expected 3 DONE goals, found $DONE_COUNT"
    sqlite3 /tmp/courier_customer_test/courier_ecosystem_v1/motor/.courier_state/motor.db "SELECT * FROM tasks;"
    exit 1
fi
