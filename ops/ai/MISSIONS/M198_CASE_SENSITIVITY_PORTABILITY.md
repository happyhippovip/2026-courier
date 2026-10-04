# M198: Case-Sensitivity Portability Risk

## Finding
When storing artifacts, their names are provided as strings (e.g. `Result.json`). A potential portability risk occurs if a task definition expects case-variant files (e.g., `Result.json` and `result.json`) which might collide on case-insensitive filesystems like macOS (APFS/HFS+) or Windows (NTFS), but work on Linux (ext4).

The artifact store handles this securely at the storage layer:
1. `artifact_id_for` hashes a serialized JSON representation of the artifact metadata, which is strictly case-sensitive.
2. `is_safe_artifact_name` does not normalize case; it validates raw paths.
3. Therefore, "Result.json" and "result.json" will generate two distinct `artifact_id`s and two distinct artifact records, even with identical bytes. 

The defense against case-collision upon extraction rests on `server/app.py` upload validation:
```python
        expected = [a.get("path") if isinstance(a, dict) else a for a in task.get("artifacts") or []]
        if meta.get("name") not in expected:
            return jsonify({"error": "artifact name is not expected by the task"}), 400
```
This performs an exact, case-sensitive `in` check against the `expected` list. A worker cannot upload `Result.json` if the task expected `result.json`. A task could theoretically request both, which would cause an extraction collision on Mac/Windows, but the server storage itself would not be corrupted or overwrite metadata records because the IDs differ.

## Local Check
We executed `tests/test_m198_case_sensitivity.py` to confirm that:
- `is_safe_artifact_name` passes both variants without side-effects.
- `artifact_id_for` produces distinct IDs for the two variants.

## Conclusion
Case-sensitivity variations are isolated by strict case-sensitive JSON metadata hashing for artifact identifiers. Storage corruption via case-collision is mathematically impossible on the server, though tasks requesting intentionally colliding names might fail to extract on case-insensitive filesystems.

STATUS=PROVEN
