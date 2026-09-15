import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from run_live_production_goal import process_one_idea

goal = "Inspect the current Courier repository and produce a verified AUTONOMY_LIVE_REPORT.md that summarizes the actual current autonomous worker architecture, identifies the Windows, Codex and Google worker paths from current repository evidence, and records that the report was produced through the autonomous Courier workflow."
process_one_idea(goal)
print("Goal injected.")
