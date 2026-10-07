# M194: Partial/Truncated Result File Detection

## Finding
When uploading artifacts (including result files) to the courier server, network interruptions or timeouts could theoretically result in truncated or partial files being saved.

The `ArtifactStore.put` method in `scripts/artifact_store.py` defends against this by enforcing cryptographic and size assertions *during* the upload:
1. The client must compute the exact `sha256` hash and `size` of the complete file and send this metadata via the `X-Courier-Artifact` header *before* uploading the body.
2. The server compares `len(request.get_data())` against the `claimed_size` (derived from the header or inferred limit) and raises `ArtifactError("uploaded bytes do not match the claimed size")` if they differ.
3. The server computes the true `sha256` of the received payload and compares it against the `claimed_sha256`. If they do not match, it raises `ArtifactError("uploaded bytes do not match the claimed sha256")`.

These conditions guarantee that a partial or corrupted upload is immediately rejected and never stored or linked to a task.

## Local Check
We executed `tests/test_m194_partial_artifact.py` to assert the upload validation logic inside `ArtifactStore.put`.
- A truncated byte payload matching the correct size header is caught by the SHA256 mismatch.
- A truncated byte payload simulating dropped connection is caught by either SHA256 mismatch or size mismatch.
- Corrupted payloads of identical size are caught by the SHA256 mismatch.
- Only a complete upload with correct size and correct SHA256 returns successfully.

## Conclusion
The artifact store prevents partial/truncated file persistence through explicit pre-upload hash and size binding.

STATUS=PROVEN
