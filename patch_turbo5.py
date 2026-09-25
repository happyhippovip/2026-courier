with open("tests/test_turbo_queue_concurrency.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == "exec_times = {}":
        new_lines.append(line)
        new_lines.append("    thread_res_ids = {}\n")
    elif line.strip() == "completion_events[tid].set()":
        new_lines.append("                    thread_res_ids[tid] = result['result_id']\n")
        new_lines.append(line)
    elif "state[\"res_ids\"][tid]" in line:
        new_lines.append(line.replace('state["res_ids"][tid]', 'thread_res_ids[tid]'))
    elif "state[\"res_ids\"][\"A\"]" in line:
        new_lines.append(line.replace('state["res_ids"]["A"]', 'thread_res_ids["A"]'))
    else:
        new_lines.append(line)

with open("tests/test_turbo_queue_concurrency.py", "w") as f:
    f.writelines(new_lines)
