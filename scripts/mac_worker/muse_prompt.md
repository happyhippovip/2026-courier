Execute only the bound Courier task in the explicitly supplied workspace.
Do not invent task IDs, session references, commits or completed work.
Do not run a different task merely because a prior checkpoint exists.
When finished, emit one fenced json object with status SUCCESS or FAILED.
Include branch, last_commit and next_task only when supported by actual evidence.
Session identity is transport metadata, not a value the model should invent.
