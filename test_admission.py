from scripts.courier_founder_mode import MultiChatGoalIntake
from pathlib import Path
import os
import shutil

test_dir = Path("test_workspace")
if test_dir.exists():
    shutil.rmtree(test_dir)
test_dir.mkdir()
(test_dir / "events" / "founder-mode").mkdir(parents=True)
with open(test_dir / "events" / "founder-mode" / "goals.json", "w") as f:
    f.write("[]")

intake = MultiChatGoalIntake(test_dir)

# 1. 100 Duplicate Submissions
goal_text = "V1 Finish Tests"
for i in range(100):
    res = intake.submit_goal("CLI", goal_text)

# Check active / pending
goals = intake._read_no_lock()
print(f"Total goals after 100 duplicates: {len(goals)}")
print(f"Goal statuses: {[g['status'] for g in goals]}")

# 2. 100 Distinct Submissions
for i in range(100):
    res = intake.submit_goal("CLI", f"Distinct task {i}")

goals = intake._read_no_lock()
print(f"Total goals after 100 distinct: {len(goals)}")

# 3. Post-V1 Parked
res = intake.submit_goal("CLI", "Run V2 Revenue Engine")
goals = intake._read_no_lock()
print(f"Post V1 status: {goals[-1]['status']}")

