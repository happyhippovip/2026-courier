import re

with open("scripts/courier_real_worker_adapters.py", "r") as f:
    text = f.read()

# Fix duplicated mission_id
text = re.sub(r'[ \t]*"mission_id": mission_id,\n[ \t]*"mission_id": mission_id,', '                "mission_id": mission_id,', text)

# Fix empty if target_agent != "CODEX":
text = text.replace('        if target_agent != "CODEX":\n\n        # Derive instruction', '        if target_agent != "CODEX":\n            return {"status": "FAIL_CLOSED"}\n\n        # Derive instruction')

# Fix empty if target_agent != "GEMINI":
text = text.replace('        if target_agent != "GEMINI":\n\n        expected_identity', '        if target_agent != "GEMINI":\n            return {"status": "FAIL_CLOSED"}\n\n        expected_identity')

# Fix payload_out in gemini gate
bad_gate = """                        "payload": payload_gate,
                        "result_fingerprint": canonical_hash(payload_gate),

        verdict = agy_res.get("verdict")"""
good_gate = """                        "payload": payload_gate,
                        "result_fingerprint": canonical_hash(payload_gate),
                    }
                }

        verdict = agy_res.get("verdict")"""
text = text.replace(bad_gate, good_gate)

# Fix payload_out in gemini_worker
bad_payload = """            "status": result_status,

        if task_type == "DISCOVERY":"""
good_payload = """            "status": result_status,
        }

        if task_type == "DISCOVERY":"""
text = text.replace(bad_payload, good_payload)

# Fix return block in gemini_worker
bad_return = """                "payload": payload_out,
                "result_fingerprint": canonical_hash(payload_out),

    return gemini_worker"""
good_return = """                "payload": payload_out,
                "result_fingerprint": canonical_hash(payload_out),
            }
        }

    return gemini_worker"""
text = text.replace(bad_return, good_return)

# Fix get_real_worker_adapters return
bad_final = """        "GEMINI": create_real_gemini_adapter(root, model=gemini_model),

"""
good_final = """        "GEMINI": create_real_gemini_adapter(root, model=gemini_model),
    }
"""
text = text.replace(bad_final, good_final)


with open("scripts/courier_real_worker_adapters.py", "w") as f:
    f.write(text)

