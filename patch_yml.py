with open(".github/workflows/courier_worker.yml", "r") as f:
    c = f.read()

c = c.replace("""          path: result_*.json""", """          path: |
            result_*.json
            courier_output_*.json""")

with open(".github/workflows/courier_worker.yml", "w") as f:
    f.write(c)
