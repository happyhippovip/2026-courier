with open("server/app.py", "r") as f:
    text = f.read()

text = text.replace(
'''    task["verification"] = {
        "verifier_id": verifier_id,
        "result_id": result["result_id"],
        "verdict": verdict,
        "artifacts": result["artifacts"],
    }''',
'''    task["verification"] = {
        "verifier_id": verifier_id,
        "result_id": result["result_id"],
        "verdict": verdict,
        "reason": data.get("reason"),
        "artifacts": result["artifacts"],
    }'''
)

with open("server/app.py", "w") as f:
    f.write(text)
