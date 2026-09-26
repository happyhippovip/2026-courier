#!/bin/bash
# IDE Task Cleanup Watchdog
# Kills background test scripts (run_*, test_*) that have been running for > 15 minutes (900 seconds)

echo "$(date): Running IDE Task Cleanup..."

# Find python scripts matching run_*.py or test_*.py that have been running for > 900 seconds
PIDS=$(ps -eo pid,etime,command | awk 'NR>1 {
  pid=$1; etime=$2;
  cmd=$3; for(i=4; i<=NF; ++i) cmd = cmd " " $i;
  
  n = split(etime, a, "-");
  if(n == 2) { days = a[1]; time_str = a[2]; } else { days = 0; time_str = a[1]; }
  
  m = split(time_str, b, ":");
  if (m == 3) { hrs = b[1]; mins = b[2]; secs = b[3]; }
  else { hrs = 0; mins = b[1]; secs = b[2]; }
  
  total_secs = days * 86400 + hrs * 3600 + mins * 60 + secs;
  
  if (total_secs > 900 && cmd ~ /python/ && (cmd ~ /run_/ || cmd ~ /test_/)) {
    print pid;
  }
}')

if [ -n "$PIDS" ]; then
    echo "Found stale IDE tasks. Killing PIDs: $PIDS"
    for pid in $PIDS; do
        kill -9 $pid 2>/dev/null
    done
else
    echo "No stale IDE tasks found."
fi
