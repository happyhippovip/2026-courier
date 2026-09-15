import hashlib, json

req_id = "../../../test_traversal"
status = "SUCCESS"
obs = "did a thing"
calc = hashlib.sha256(f"{req_id}{status}{obs}".encode("utf-8")).hexdigest()

data = {
  "request_id": req_id,
  "status": status,
  "observed_behavior": obs,
  "result_fingerprint": calc,
  "schema_version": "2.0"
}
with open("coordination/windows_to_mac/results/REQ-TRAVERSAL.json", "w") as f:
    json.dump(data, f)
