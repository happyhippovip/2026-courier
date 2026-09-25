import re

with open("scripts/courier_control_plane.py", "r") as f:
    content = f.read()

verify_block = """            if res.get("status") == "SUCCESS":
                # TASK-SPECIFIC VERIFICATION
                # Extract expected artifact from instruction if it matches our observable effect pattern
                import re
                m = re.search(r'(canary_[A-Za-z0-9_]+\.txt)', task["description"])
                if m:
                    import os
                    artifact = m.group(1)
                    if os.path.exists(artifact):
                        print(f"Verification PASS: Found expected artifact {artifact}")
                        task["status"] = "RECONCILED"
                    else:
                        print(f"Verification FAIL: Missing expected artifact {artifact}")
                        task["status"] = "FAILED_VERIFICATION"
                else:
                    # Fallback if no specific artifact found in description, we just assume it was a reading/analysis task.
                    # But for the canary, we specifically provide observable artifacts.
                    task["status"] = "RECONCILED"
            else:
                task["status"] = "FAILED_TERMINAL"
"""

content = re.sub(
    r'            if res\.get\("status"\) == "SUCCESS":\n                task\["status"\] = "RECONCILED"\n            else:\n                task\["status"\] = "FAILED_TERMINAL"',
    verify_block,
    content,
    flags=re.MULTILINE
)

with open("scripts/courier_control_plane.py", "w") as f:
    f.write(content)
