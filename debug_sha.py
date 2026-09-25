with open("server/app.py", "r") as f:
    c = f.read()

c = c.replace(
    'return jsonify({"error": "wrong SHA rejected: worker runtime_sha does not match server SHA"}), 426',
    'return jsonify({"error": f"wrong SHA rejected: worker runtime_sha {worker_sha} does not match server SHA {SERVER_SHA}"}), 426'
)

with open("server/app.py", "w") as f:
    f.write(c)
