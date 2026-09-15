import hashlib, json

req_id = "REQ-ROGUE-999"
status = "SUCCESS"
obs = "rogue actor did this"
calc = hashlib.sha256(f"{req_id}{status}{obs}".encode("utf-8")).hexdigest()

data = {
  "request_id": req_id,
  "status": status,
  "observed_behavior": obs,
  "result_fingerprint": calc,
  "schema_version": "2.0",
  "actor": "ROGUE_PROCESS_FROM_INTERNET"
}
with open("coordination/windows_to_mac/results/REQ-ROGUE-999.json", "w") as f:
    json.dump(data, f)
