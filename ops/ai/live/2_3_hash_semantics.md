Evidence for Restart-/Replay-Semantik & Trusted-Hash-/Artifact-Semantik:
- Bug in scripts/integration_contract.py: validate_durable_result did not verify the hash of result_id against the canonical payload. Replays or malicious mutations could spoof the result_id.
- Fixed: Added canonical hash verification to validate_durable_result.
