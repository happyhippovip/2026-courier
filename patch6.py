import re
with open("tests/test_courier_complete_lifecycle.py", "r") as f:
    content = f.read()

run_method = """    def _run(self, goal: str):
        runtime = FounderModeMVP(str(self.workspace), self.dispatcher)
        runtime.intake.ingest_goal("test", goal, "system")
        runtime.run_autonomous_loop()
        return runtime

    def test_complete_lifecycle_retries_once_then_satisfies_goal(self) -> None:"""

content = content.replace("    def test_complete_lifecycle_retries_once_then_satisfies_goal(self) -> None:", run_method)

with open("tests/test_courier_complete_lifecycle.py", "w") as f:
    f.write(content)
