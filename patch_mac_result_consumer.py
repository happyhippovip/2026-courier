from pathlib import Path

p = Path("scripts/mac_result_consumer.py")
lines = p.read_text().splitlines()

new_lines = []
skip = False
for line in lines:
    if "from next_safe_work_router import NextSafeWorkRouter" in line:
        skip = True
    if skip and "req_file = REQUESTS_DIR" in line:
        skip = False
        new_lines.append("                    try:")
        new_lines.append(line)
        continue
    if not skip:
        new_lines.append(line)

p.write_text("\n".join(new_lines) + "\n")
print("Patched cleanly!")
