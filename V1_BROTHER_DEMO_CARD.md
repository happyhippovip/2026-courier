COURIER / SYMPHONY — 5 MINUTE DEMO

RULE:
AFTER START, DO NOT TYPE "WEITER".

1. PRECHECK
Run this to ensure a clean slate and no stuck locks:
```bash
export PYTHONPATH=$(pwd)
rm -f events/founder-mode/goals.lock events/mission-queue/queue.lock
echo "[]" > events/founder-mode/goals.json
echo '{"missions":[]}' > events/mission-queue/queue.json
rm -f bouncing_ball.html courier_manifest.md
```
(Expected time: < 1 second)

2. START
Inject the goal and start the autonomous governor in the background:
```bash
python3 scripts/inject_demo_goal.py "Create a file named courier_manifest.md containing exactly: # Courier Manifest"
python3 scripts/run_overnight_governor.py > governor_demo.log 2>&1 &
```

3. HANDS OFF — WATCH
Watch Courier's autonomous brain execute transitions (Discover -> Plan -> Execute -> Verify):
```bash
python3 scripts/watch_symphony.py
```
(Press Ctrl+C to exit the watcher at any time, Courier continues working in the background).

4. SUCCESS
Success is reached when:
- The watcher shows GOAL STATUS: SATISFIED.
- Open the physical result using Finder or Terminal:
```bash
cat /Users/user/Downloads/2026-courier/courier_manifest.md
```
(It should contain exactly `# Courier Manifest`).

5. ONLY IF IT STOPS
If execution visibly hangs for > 3 minutes, do not type anything manually.
Instead, safely restart the motor:
```bash
killall python3
rm -f events/founder-mode/goals.lock events/mission-queue/queue.lock
python3 scripts/run_overnight_governor.py > governor_demo.log 2>&1 &
```
