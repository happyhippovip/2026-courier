import re
with open("scripts/mac_worker/daemon.py", "r") as f:
    code = f.read()

replacement = """        combined_out = (out_clean + " " + stderr).lower()
        if any(kw in combined_out for kw in ["429", "too many requests", "quota", "rate limit", "resource exhausted", "provider unavailable", "500", "502", "503", "504", "timeout", "timed out", "internal server error", "service unavailable", "bad gateway", "401", "403", "unauthorized", "authentication failed", "invalid api key"]):
            write_log("DEBUG AGY OUTPUT: " + combined_out)
            res_json["status"] = "PROVIDER_WAIT"
            res_json["reason"] = "QUOTA_OR_RATE_LIMIT"
            return res_json"""

code = re.sub(r'        combined_out = \(out_clean \+ " " \+ stderr\)\.lower\(\).*?return res_json', replacement, code, flags=re.DOTALL)

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(code)
