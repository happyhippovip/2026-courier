# Muse stdout contract result — 2026-09-26

Status: PHYSICALLY CONFIRMED / MATCH

Observed in one isolated Mac probe:
- Muse Code 1.4.0
- process exit code: 0
- final model response appeared directly on stdout as a plain JSON success object
- Muse diagnostic prefix lines appeared on stderr, not stdout
- no ANSI/TUI contamination was observed
- current Muse adapter was reported to parse the result successfully
- no adapter writer-scope change is required

Decision:
MUSE_OUTPUT_CONTRACT=MATCH

Do not repeat this probe unless the Muse binary/version, adapter parser, or relevant CLI invocation contract changes.

Local user/workspace paths are intentionally omitted from this public-safe record.
