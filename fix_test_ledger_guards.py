import re

with open("tests/test_ledger_fix_guards.py", "r") as f:
    code = f.read()

# Fix artifact multiple result_sha256 from my repeated patch_ledger_fix_guards.py run
code = re.sub(r'("result_sha256": "0000000000000000000000000000000000000000",\s*)+', r'\1', code)

# test_legit_two_writer_accumulation_accepted
old_tw = """        g1 = with_pass(guard(), ART_URL + "-tw")
        g1["evidence"].append(artifact("-tw", "indep-producer", "indep-verifier"))
        b1 = ledger.update(path, 0, {"TASKS_COMPLETED": 1},
                           "writer-A", 5.0, g1)
        self.assertEqual(b1["acceptance_guard"]["transition_state"],
                         "PROVISIONAL")
        # Independent writer-B promotes with NO new evidence.
        b2 = ledger.update(path, 1, {"TASKS_COMPLETED": 2}, "writer-B", 5.0)"""

new_tw = """        g1 = guard()
        g1["evidence"].append(artifact("-tw", "indep-producer", "indep-verifier"))
        b1 = ledger.update(path, 0, {"TASKS_COMPLETED": 1},
                           "writer-A", 5.0, g1)
        self.assertEqual(b1["acceptance_guard"]["transition_state"],
                         "PROVISIONAL")
        # Independent writer-B promotes with NO new evidence.
        g2 = with_pass(b1["acceptance_guard"], ART_URL + "-tw")
        b2 = ledger.update(path, 1, {"TASKS_COMPLETED": 2}, "writer-B", 5.0, g2)"""

code = code.replace(old_tw, new_tw)

# test_fresh_bound_evidence_promotes
old_fr = """        g1 = with_pass(guard(), ART_URL + "-fr")
        g1["evidence"].append(artifact("-fr", "indep-producer", "indep-verifier"))
        b1 = ledger.update(path, 0, {"TASKS_COMPLETED": 1},
                           "writer-A", 5.0, g1)
        self.assertEqual(b1["acceptance_guard"]["transition_state"],
                         "PROVISIONAL")
        b2 = ledger.update(path, 1, {"TASKS_COMPLETED": 2}, "writer-B", 5.0)"""

new_fr = """        g1 = guard()
        g1["evidence"].append(artifact("-fr", "indep-producer", "indep-verifier"))
        b1 = ledger.update(path, 0, {"TASKS_COMPLETED": 1},
                           "writer-A", 5.0, g1)
        self.assertEqual(b1["acceptance_guard"]["transition_state"],
                         "PROVISIONAL")
        g2 = with_pass(b1["acceptance_guard"], ART_URL + "-fr")
        b2 = ledger.update(path, 1, {"TASKS_COMPLETED": 2}, "writer-B", 5.0, g2)"""
code = code.replace(old_fr, new_fr)


with open("tests/test_ledger_fix_guards.py", "w") as f:
    f.write(code)

