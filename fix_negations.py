with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

content = content.replace(
    r"text = re.sub(negations + r'(?:\s*(?:,|\band\b|\bor\b)?\s*' + gates_pattern + r')+', '', text)",
    r"text = re.sub(negations + r'(?:\s*(?:requires?|needs?|use|using)?\s*(?:,|\band\b|\bor\b)?\s*' + gates_pattern + r')+', '', text)"
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)
