import hashlib
import json
target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"
def test(s):
    if hashlib.sha256(s.encode('utf-8')).hexdigest() == target:
        print("MATCH:", s)
        exit(0)

# The legacy consumer hashed: request_id + status + observed_behavior
# Windows schema fields: windows_validation_request_id, status, decision, work_done, access_integrity

test("REQ-MAC-7B6D8CA4" + "PASS" + "ACCEPTED_VERIFIED")
test("REQ-MAC-7B6D8CA4" + "PASS" + "ACCEPTED_VERIFIED" + "Bounded validation for WINDOWS_COMPATIBILITY completed autonomously via WINDOWS_GOOGLE")
test("REQ-MAC-7B6D8CA4" + "PASS" + "WINDOWS_ALIVE_AND_READY")
test("REQ-MAC-7B6D8CA4" + "PASS" + "NTFS_ACL_CONTAINED_BORDER_GUARD_ENFORCED")
test("REQ-MAC-7B6D8CA4" + "PASS" + "EXECUTION_EXIT_0")
test("REQ-MAC-7B6D8CA4PASSWINDOWS_ALIVE_AND_READY")
test("REQ-MAC-7B6D8CA4PASSACCEPTED_VERIFIEDWINDOWS_ALIVE_AND_READY")

print("No match")
