V1 SYMPHONY DEMO

1. Run preflight:
export PYTHONPATH=$(pwd) && echo "[]" > events/founder-mode/goals.json && echo '{"missions":[]}' > events/mission-queue/queue.json && rm -f bouncing_ball.html

2. If PASS, run:
python3 scripts/inject_demo_goal.py "Create a file named bouncing_ball.html containing exactly: <html><body><h1>Hello Courier</h1></body></html>" && python3 scripts/run_overnight_governor.py

3. HANDS OFF

4. Watch Courier work.

5. Open result:
/Users/user/Downloads/2026-courier/bouncing_ball.html

6. Success means:
A webpage that says "Hello Courier" is autonomously created locally on this Mac.
