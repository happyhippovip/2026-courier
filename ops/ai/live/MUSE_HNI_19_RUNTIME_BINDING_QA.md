# MUSE-HNI-19 checkpoint — RUNTIME_BINDING_QA (read-only)

TASK_ID=MUSE-HNI-19 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T14:12Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_19_RUNTIME_BINDING_QA.claim.json (atomic).
REUSED: MAC01_BINDING (FINAL_SHA UNBOUND, cited); gate REMOTE_NOT_FOUND (cited).
Reads this run: RUNTIME_SOURCE_BINDING.json, 4 shebangs, env-default grep,
bare-python grep (RUN1 mats), binding template:19.

SUBCASES (runtime binding; 0 executions, ledger untouched):
S1 Binding declares python3 + run_physical.py; all shebangs python3; template:19
  uses python3. NO_ISSUE in RUN1 materials.
S2 EVIDENCE_DOC_DEFECT (dispatcher prose, no file to fix — noted): wall order
  `python scripts/local_swarm_claim.py` assumes python==py3; on this MAC bare
  `python` = 2.7 (observed) AND the script is absent repo-wide. Double gap in
  the order text itself, not in repo runtime.
S3 Env defaults: STATE_FILE/ARTIFACT_DIR CWD-relative (repo-root start assumed);
  keys fail closed (503/401). NO_ISSUE with boundary (intake CWD-divergence
  already W-gated).
S4 candidate_sha {{FINAL_SHA}} unbound (known cite). target_remote is string-only
  binding; resolution status = gate (cited, not re-checked).
S5 Dual entrypoints (run_physical vs _restart) disambiguated by template (RUN1)
  vs restart flow; no shared-name collision. NO_ISSUE.

VERDICT=family not exhausted; 0 contradictions. NEXT=MUSE-HNI-20.
