import sys

content = open("scripts/courier_continue.py").read()

content = content.replace(
    'proven = record.get("PROVEN_EDGES", [])\n    unproven = record.get("UNPROVEN_EDGES", [])',
    'proven = list(record.get("PROVEN_EDGES", []))\n    unproven = list(record.get("UNPROVEN_EDGES", []))'
)
open("scripts/courier_continue.py", "w").write(content)
