# M198 — Multiple Artifact Multipart Hash Aggregation Specification

## 1. Overview & Authority
- **Task ID**: M198
- **Area**: MULTIPART_HASH
- **Status**: COMPLETE

## 2. Aggregation Formula
For tasks outputting multiple files:
`composite_hash = SHA256(sort([filename + ":" + SHA256(file_bytes)]).join("\n"))`
Ensures deterministic composite digest regardless of filesystem directory iteration order.
