import sys

def main():
    path = "scripts/integration_contract.py"
    with open(path, "r") as f:
        content = f.read()

    to_replace = """    if "run_attempt" in result:
        required.add("run_attempt")"""
    replacement = """    if "run_attempt" in result:
        required.add("run_attempt")
    if "result_data" in result:
        required.add("result_data")"""

    new_content = content.replace(to_replace, replacement)
    with open(path, "w") as f:
        f.write(new_content)

if __name__ == "__main__":
    main()
