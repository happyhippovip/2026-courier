# FORENSICS REPORT

FILE: scripts/github_transport.py
SYMBOL: load_json / _update_registry_synchronized
INPUT: malformed registry (truncated JSON)
CURRENT_BEHAVIOR: load_json catches Exception and returns None. _update_registry_synchronized then silently reinitializes an empty registry.
WHY_UNSAFE: Destroys the deduplication ledger. Corrupted state becomes EMPTY and is silently overwritten, allowing all previous messages and deliveries to be re-processed (duplicate execution).
REQUIRED_FAIL_CLOSED_BEHAVIOR: If the registry file exists but is invalid, the transport must fail closed (raise an exception) rather than wiping the ledger.
MINIMAL_FIX_CONTRACT: Differentiate FileNotFoundError (return None) from json.JSONDecodeError (raise).
POSITIVE_TEST: Provide truncated registry.json, assert transport raises exception.
NEGATIVE_TEST: Provide valid registry.json, assert transport parses it.
HOST_OWNERSHIP: CROSS_HOST
CLASSIFICATION: REAL_DEFECT

FILE: scripts/mac_result_consumer.py
SYMBOL: consume_results
INPUT: result without canonical request
CURRENT_BEHAVIOR: ACKs any result that has a self-consistent fingerprint, without checking if the Mac actually issued the request_id.
WHY_UNSAFE: Allows orphaned, fabricated, or cross-environment results to be permanently ACKNOWLEDGED without being bound to a genuine local request.
REQUIRED_FAIL_CLOSED_BEHAVIOR: Verify that the canonical request file exists in the REQUESTS_DIR before ACKing the result.
MINIMAL_FIX_CONTRACT: Assert (REQUESTS_DIR / f"{req_id}.json").exists() before proceeding with validation.
POSITIVE_TEST: Supply result for nonexistent request, assert it is not ACKed.
NEGATIVE_TEST: Supply result for valid request, assert it is ACKed.
HOST_OWNERSHIP: MAC
CLASSIFICATION: REAL_DEFECT

FILE: scripts/mac_result_consumer.py
SYMBOL: consume_results
INPUT: wrong node / wrong attempt
CURRENT_BEHAVIOR: Does not validate the node_id, lease_id, or attempt_id of the result against the expected Mac request.
WHY_UNSAFE: A stale result from an expired lease or an incorrect worker node can be ACKNOWLEDGED, violating the exactly-once and exclusive execution guarantees.
REQUIRED_FAIL_CLOSED_BEHAVIOR: Validate that the result's node identity and lease epoch match the currently authorized executor for that request.
MINIMAL_FIX_CONTRACT: Compare result node/lease metadata with the request's expected recipient before ACKing.
POSITIVE_TEST: Supply result from unauthorized node, assert rejection.
NEGATIVE_TEST: Supply result from authorized node, assert ACK.
HOST_OWNERSHIP: MAC
CLASSIFICATION: REAL_DEFECT

M2_RESULT=REAL_DEFECT_FOUND
FAIL_OPEN_PATHS=3
IDENTITY_BINDING_GAPS=2
ATOMICITY_GAPS=1
REAL_DEFECTS=3
WINDOWS_PHYSICAL_TESTS_REQUIRED=1
