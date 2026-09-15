from pathlib import Path

fpath = Path("/Users/user/Downloads/2026-courier/events/reports/fault_test_999.txt")
pre_content = fpath.read_text(encoding="utf-8").strip()
req_content = "HELLO"

print(f"pre_content: {repr(pre_content)}")
print(f"req_content: {repr(req_content)}")
print(f"Match: {pre_content == req_content}")
