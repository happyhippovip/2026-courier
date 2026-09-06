with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

old_regex = r'        match = re.search(r"file named (\\S+) containing exactly:\\s*(.*)", goal_text, re.IGNORECASE)'
new_regex = r'        match = re.search(r"(?:file named|file:)\\s*(\\S+)\\s*(?:containing exactly:|with exact content:)\\s*(.*)", goal_text, re.IGNORECASE | re.DOTALL)'

content = content.replace(old_regex, new_regex)
content = content.replace('return {"file_exists": match.group(1), "content_matches": match.group(2)}', 'return {"file_exists": match.group(1), "content_matches": match.group(2).strip()}')

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
