# M3 — LOCAL_DIFF_FALSE_GREEN RESULT

## FLAGS
- **DIFF_CLEAN**: NO (Both `3c2aa516...` and `e575178...` fail `git diff --check` with 40+ lines of trailing whitespace). The statement in `PRE_CODEX_HANDOFF.md` that "All trailing whitespace errors have been resolved locally" is demonstrably false against the committed candidate.
- **SCOPE_MATCH**: NO (`tests/test_integration_contract.py` is modified and introduces trailing whitespace, but it is NOT listed in the allowed scope in `GOOGLE_PRE_CODEX_GATE_2026-09-27.md`).
- **DURABILITY**: READY (Candidate `3c2aa5160002bdb7e2647ab87a0cef2a6f2a3ec4` and current HEAD `e57517833c57eb3dd336c92e629e4a2db53da498` both exist on the remote canonical ref `origin/coordination/mac-handoff-20260928`).

## DIVERGENCE NOTE
- **Kandidat SHA**: `3c2aa5160002bdb7e2647ab87a0cef2a6f2a3ec4`
- **Eigener Checkout (HEAD)**: `e57517833c57eb3dd336c92e629e4a2db53da498` (chore: Windows->Mac-Handoff for PRE_CODEX)
- The local checkout has diverged from the candidate SHA due to a handoff commit, however both SHAs are successfully pushed to `origin`.
