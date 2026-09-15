import sys
path = "scripts/courier_safety_dispatcher.py"
data = open(path).read()
data = data.replace('if not self.canonical_validate_result(mission_id, task, result_data, state.get("route")):', 'if not self.canonical_validate_result(mission_id, task, result_data, state.get("route")):\n                        print("FAILED CANONICAL")')
data = data.replace('if prestate is None or type(prestate) is not dict or "exists" not in prestate:', 'if prestate is None or type(prestate) is not dict or "exists" not in prestate:\n                                    print("FAILED PRESTATE", prestate)')
data = data.replace('if not fpath.exists():', 'if not fpath.exists():\n                    print("FAILED FPATH EXISTS")')
data = data.replace('if result_data.get("result_fingerprint") != canonical_hash({"path": str(fpath), "content": post_content}):', 'if result_data.get("result_fingerprint") != canonical_hash({"path": str(fpath), "content": post_content}):\n                                    print("FAILED HASH", result_data.get("result_fingerprint"), canonical_hash({"path": str(fpath), "content": post_content}))')
data = data.replace('if prestate.get("exists") and prestate.get("content") == post_content:', 'if prestate.get("exists") and prestate.get("content") == post_content:\n                                    print("FAILED STALE")')
open(path, "w").write(data)
