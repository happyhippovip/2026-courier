from scripts.courier_safety_dispatcher import CourierSafetyDispatcher

def check(text):
    mission = {"goal": text}
    task = {}
    return CourierSafetyDispatcher._requires_human_gate(mission, task)

assert check("execute a real trade") == True, "POSITIVE_DANGEROUS_ACTION_GATE failed"
assert check("connect my real wallet and sign") == True, "POSITIVE_DANGEROUS_ACTION_GATE failed"
assert check("NO real trades") == False, "NEGATIVE_CONSTRAINT_NOT_GATE failed"
assert check("do not connect a real wallet") == False, "NEGATIVE_CONSTRAINT_NOT_GATE failed"
assert check("NO wallet signing") == False, "NEGATIVE_CONSTRAINT_NOT_GATE failed"
assert check("do not deploy production") == False, "NEGATIVE_CONSTRAINT_NOT_GATE failed"
assert check("NO real trades but execute a real trade") == True, "CONTRADICTORY_FAIL_CLOSED failed"
assert check("I might want to do a real trade later") == True, "AMBIGUOUS_FAIL_CLOSED failed"

print("All tests passed.")
