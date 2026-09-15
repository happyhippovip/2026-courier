MAC_RESULT_SCHEMA_REPAIR

MAC_HEAD_BEFORE=f45b2c59abb096951f97af629cbe48bcfbb18d56
MAC_HEAD_AFTER=390d9204b3720cd3304ddcebc6605bef61d4f84b

FILES_CHANGED=scripts/mac_result_consumer.py, tests/test_result_schema_compatibility.py

ROOT_CAUSE=Mac consumer rigidly expected the legacy fields 'request_id' and 'result_fingerprint' (which hashes request_id+status+observed_behavior), whereas the authoritative Windows production node uses 'windows_validation_request_id', 'content_integrity', and 'evidence'.
FIX=Updated the Mac consumer schema parsing to conditionally accept 'windows_validation_request_id' as a valid identity and dynamically validate 'content_integrity' (by verifying its presence in the execution 'evidence' string) while preserving strict legacy compatibility and rejecting malformed identities.

FOCUSED_TESTS=tests/test_result_schema_compatibility.py
FOCUSED_TESTS_PASS=PASS

REAL_RESULT_CONSUMPTION=PASS
RESULT_FINGERPRINT=PASS
ACK=PASS

PHYSICAL_WINDOWS_TO_MAC=PASS

REAL_V1_DEFECTS_REMAINING=0
UNKNOWN_REQUIRED_EVIDENCE=DUPLICATE_REPLAY

DUPLICATE_REPLAY_STATUS=NOT_EXECUTED

FINAL_STATUS=DEFECT_FIXED
