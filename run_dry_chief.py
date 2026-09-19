from scripts.run_chief_commander import ChiefCommander
import json

chief = ChiefCommander()
res = chief.execute_human_idea("Ich möchte eine Website für mein Produkt.", "GOAL", dry_run=True)
print(json.dumps(res, indent=2))
