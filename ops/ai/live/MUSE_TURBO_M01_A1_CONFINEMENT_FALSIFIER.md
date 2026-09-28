# MUSE TURBO A — M01 A1_CONFINEMENT_FALSIFIER (Post-Codex packet)

BASE_SHA=ae0030c81be5b859daf96d2fe4a576e82ccd9e2f
MODE=READ_ONLY_C2, LEDGER=FROZEN
CODEX_GATE=ABSENT (ops/ai/live/CODEX_HIGH_RESULT_CURRENT.md missing; live dir lists only CORE_FREEZE/MAC/MUSE shards)
TREE=dirty by peers, untouched — all evidence via `git show HEAD:...` / `git grep`, zero executions, zero suite, zero source edits.

## S1 — adapter absolute-path escape
CLAIM= `verify_result` in `scripts/github_worker_adapter.py` opens worker-controlled absolute paths outside `directory`.
SOURCE_TRUTH= line 98: `evidence_file = directory / artifact.get("path", "")`; line 99 hashes/reads it. Imports (1-20): hashlib/base64/json/os/shutil/subprocess/sys/time/Pathlib/requests — no `is_safe_artifact_name`, no `Pure*`, no `artifact_store` (grep NO_GUARD_HIT).
FALSE_GREEN_PATH= "hash check saves us" — false: `pathlib.Path("/base") / "/etc/passwd"` discards left side, so an absolute `path` reads outside `directory` and its matching sha256 still verifies.
INDEPENDENT_EVIDENCE= git-show lines 80-99 + import block + `test_github_worker_adapter.py` grep: 10 tests, zero hits for absolute/travers/confin/evidence_file.
MINIMUM_FIX_OR_GUARD= gate before line 98 with in-repo template: `from scripts.artifact_store import is_safe_artifact_name`; `if not is_safe_artifact_name(artifact.get("path","")): raise ValueError("unsafe artifact path")` (mirrors `integration_contract.validate_durable_result` + `verify_artifacts` local branch).
MINIMUM_TEST= `verify_result` rejects `path="/etc/passwd"` and `path="C:\\Windows\\x"` without filesystem access (raises before `is_file`).
DISPROVEN_OR_CONFIRMED=CONFIRMED

## S2 — adapter `..` traversal escape
CLAIM= same sink allows `../` escape from `directory`.
SOURCE_TRUTH= same lines 98-99; no `".." in Path(...).parts` check anywhere in adapter file.
FALSE_GREEN_PATH= "download dir is trusted" — false: `path` comes from worker-supplied `result["artifacts"][0]`, not from local download listing; `download_result` only globs `result_{dispatch}.json`, never constrains `artifacts[0].path`.
INDEPENDENT_EVIDENCE= same grep NO_GUARD_HIT; contract positive control exists (`"..\" in Path(path).parts` + PureWindowsPath drive/root check) proving the check was known and omitted here.
MINIMUM_FIX_OR_GUARD= same S1 gate (single fix covers both).
MINIMUM_TEST= rejects `path="../secret.txt"` and `path="a/../../b"` pre-read.
DISPROVEN_OR_CONFIRMED=CONFIRMED

## S3 — verifier raw `verify_artifact` unconfined (defense-in-depth)
CLAIM= bare `verify_artifact(path, hash)` in `scripts/courier_verifier.py:20-32` opens any path (`os.path.exists` + `open(path,"rb")`) with no confinement.
SOURCE_TRUTH= lines 20-32: no `is_safe`, no absolute/`..` check inside the function.
FALSE_GREEN_PATH= "wrapper always guards" — true today (S4) but the primitive itself is exported and used as default `local_verify`; any direct/future caller bypasses confinement silently.
INDEPENDENT_EVIDENCE= function body via git-show; only in-file caller is the default arg at line 70 (`local_verify or verify_artifact`); `git grep verify_artifact` shows no other script/server caller — bounded blast radius, still a latent primitive defect.
MINIMUM_FIX_OR_GUARD= add `is_safe_artifact_name` guard inside `verify_artifact` itself (fail-closed `return False` + log) so the primitive is safe by default, not by caller discipline.
MINIMUM_TEST= unit: `verify_artifact("/etc/passwd", <real hash>) is False` and `verify_artifact("../x", h) is False` without reading.
DISPROVEN_OR_CONFIRMED=CONFIRMED (low severity, defense-in-depth)

## S4 — verifier wrapped local branch is guarded (not vulnerable)
CLAIM= `verify_artifacts` local path opens arbitrary files.
SOURCE_TRUTH= lines 97-101: `elif not is_safe_artifact_name(art.get("path")) or not local_verify(...): return "FAIL"` — short-circuit rejects before open; `is_safe` (artifact_store.py) rejects absolute/drive/UNC/`..`/empty/>255/NUL via both PureWindowsPath+PurePosixPath.
FALSE_GREEN_PATH= reading S3 alone and concluding the live verifier path is exploitable — wrong branch: the live `run_loop` calls `verify_artifacts`, not bare `verify_artifact`.
INDEPENDENT_EVIDENCE= guard lines 97-101 + `is_safe` def + `test_artifact_upload_flow.py` local-verify tests (PASS/FAIL matrix, omitted-expected FAIL).
MINIMUM_FIX_OR_GUARD= none needed on this branch (keep).
MINIMUM_TEST= existing coverage suffices; add one unsafe-name → FAIL case through `verify_artifacts` with `local_verify` spy asserting spy NOT called.
DISPROVEN_OR_CONFIRMED=DISPROVEN (as active vuln)

## S5 — verifier remote path never opened (not vulnerable)
CLAIM= verifier opens Mac/Windows worker local paths.
SOURCE_TRUTH= lines 83-99: `artifact_id` branch re-hashes server bytes via `verify_uploaded_artifact`; `elif remote: ... not opening remote paths → FAIL`; only non-remote falls to S4.
FALSE_GREEN_PATH= old V1 narrative ("verifier opens worker path") applied to current HEAD — stale; upload-based design + docstring ("never opens a remote worker's local path") + fail-closed remote branch refute it.
INDEPENDENT_EVIDENCE= lines 64-99 + `test_artifact_upload_flow.py:192` (remote artifact with failing fetch → FAIL) + upload-flow PASS/FAIL matrix.
MINIMUM_FIX_OR_GUARD= none.
MINIMUM_TEST= existing remote-not-uploaded → FAIL test; keep.
DISPROVEN_OR_CONFIRMED=DISPROVEN (as active vuln)

## S6 — contract/store positive controls (fix template in-repo)
CLAIM= no in-repo confinement pattern exists (would force new design).
SOURCE_TRUTH= `integration_contract.verify_result` (~line 98) and `validate_durable_result` (tail): `Path(path).is_absolute() or ".." in parts` + `PureWindowsPath drive/root` → `ContractError`; `artifact_store.is_safe_artifact_name` + `put`/`check_reference` enforce same server-side.
FALSE_GREEN_PATH= "adapter needs novel design" — false: copy the one-line gate.
INDEPENDENT_EVIDENCE= contract head/tail via git-show; artifact_store `is_safe` + `put` unsafe-name reject.
MINIMUM_FIX_OR_GUARD= port, not invent (see S1).
MINIMUM_TEST= adapter tests mirror contract unsafe-path cases.
DISPROVEN_OR_CONFIRMED=DISPROVEN (claim of "no template"); confirms S1/S2 are outliers.

---
CONFIRMED=S1 (adapter absolute escape), S2 (adapter .. traversal), S3 (raw verifier primitive, defense-in-depth)
DISPROVEN=S4 (wrapped local branch guarded), S5 (remote open), S6 (no-template claim)
MISSING_EVIDENCE=none for verdicts (code-grounded); no execution proof by design (READ_ONLY, no runs); adapter exploit end-to-end unexecuted deliberately.
OWNER_PACKET=WINDOWS_CENTRAL_WRITER (adapter owner lane; HEAD is WINDOWS_CENTRAL_WRITER_FINAL_COMMIT_8) — minimal 1-gate port + 2-3 reject-tests.
BEFORE_RUN1=S1+S2 adapter gate + reject-tests (worker-controlled read outside download dir breaks RUN1 trust).
BEFORE_RUN2=S3 harden raw `verify_artifact` (cheap, prevents regression via new callers).
BEFORE_FREEZE=S4-spy test (unsafe name never reaches `local_verify`) — documents guard, not a behavior change.
DEFER=server-side `check_reference` already covers uploaded refs; no new infra.
DO_NOT_REPEAT=A1-confinement on this SHA; re-open only on adapter/verifier diff.

C2_MAP: FILES=scripts/github_worker_adapter.py:98-99 (defect), scripts/courier_verifier.py:20-32 (latent primitive); CAUSAL_BUG=pathlib `/` with unvalidated worker `artifact["path"]` (absolute discards base; `..` escapes); MIN_FIX=`is_safe_artifact_name` gate pre-read (S1); MIN_TEST=absolute + `..` reject pre-read + spy-not-called; OWNER=WINDOWS_CENTRAL_WRITER; CLASS=CONFIRMED_SOURCE_DEFECT (S1/S2), DISPROVEN (S4/S5).
FAMILY_COMPLETE=YES
