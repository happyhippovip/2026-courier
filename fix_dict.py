import re

with open("scripts/courier_real_worker_adapters.py", "r") as f:
    text = f.read()

bad = """                    "mission_id": mission_id,
            "mission_id": mission_id,
                "payload": payload_out,
                "result_fingerprint": canonical_hash(payload_out),

    return cli1_worker"""

good = """                "mission_id": mission_id,
                "payload": payload_out,
                "result_fingerprint": canonical_hash(payload_out),
            }
        }

    return cli1_worker"""

new_text = text.replace(bad, good)
if new_text != text:
    with open("scripts/courier_real_worker_adapters.py", "w") as f:
        f.write(new_text)
        print("Fixed dictionary")
else:
    print("Could not find bad dict")
