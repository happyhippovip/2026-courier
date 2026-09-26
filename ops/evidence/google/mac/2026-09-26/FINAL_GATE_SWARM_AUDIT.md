# FINAL_GATE_SWARM_AUDIT — Courier Mac Physical-Proof Runner

**DATE:** 2026-09-26T20:10:00+02:00  
**HOST:** MAC (`Darwin 25.6.0 x86_64`, `MacBook-Pro-von-user.local`)  
**ROLE:** `PHYSICAL_CANARY_PREPARATION_OWNER`  
**MODE:** `STRICT_READONLY` (No source writes, no runtime touches)  
**GATE:** `FINAL_GATE_IDLE_SAFE=YES`

---

## 1. Candidate SHA Consistency & Lineage

| Candidate Ref | SHA | Status | Evidence / Notes |
| :--- | :--- | :--- | :--- |
| `origin/candidate-b-1` | `4c1e24ccc522042af826bc4c2b595daf85d097f9` | **ACCEPTED BASE** | Clean base verified locally via `git rev-parse`. |
| `origin/candidate-b-2` | `83940de3d7d33776a712e7506aa76726d16f8587` | **REJECTED** | Single-line commit dropping `"status"` from `ACK_DUPLICATE` check in `server/app.py:366`. Opens over-ACK vulnerability (Codex F3). |
| `candidate-b-3` | `PENDING_AUTHORING` | **AWAITING WRITER** | Scoped to: trusted `record.sha256` verifier link, contract rejection of worker-expected hash, duplicate ACK status check restoration, and CLI reasoning effort fix. |
| `origin/finish-cb3` | `dc03c250` / `9f45fa9c` | **UNRELATED / STALE** | False-name collision. 112 files changed; predates candidate series (child process/credential workstream). Excluded. |
| Canonical Wall HEAD | `332a42f9edcf1de1535870592da34a7961880991` | **TRACKED** | Minimal canonical wall supervisor with Muse feeder. |
| Writer Worktree | `f7e1acb677eb673d6d4bdeff703b427333ba4cc0` | **LOCAL WRITER WORKTREE** | Writer lock `MAC-01` held by PID 61758. |

---

## 2. Exact Five-File b-3 Scope (Derived & Pinned)

1. `scripts/courier_verifier.py`: Compare server bytes against server-side minted `record.sha256`, eliminating worker-supplied hash dependence (`:74-76`).
2. `scripts/artifact_store.py`: `check_reference()` raises `ArtifactError` on worker `expected_sha256` mismatch with stored record hash (intake HTTP 400).
3. `server/app.py`: Maintain HTTP 400 propagation for `ArtifactError`; restore `"status"` in `ACK_DUPLICATE` comparison (`:366`).
4. `scripts/integration_contract.py`: Pin T2b semantics (`expected_sha256` admitted in key set with non-authoritative worker value).
5. `tests/test_artifact_upload_flow.py`: Update `test_verifier_checks_expected_sha256` and add deterministic tests T1a-c / T2a-c.
*(Plus single-writer supervisor CLI fix in `scripts/muse_wall_supervisor.py:40` replacing invalid `--reasoning-effort auto` with valid parameter).*

---

## 3. Trusted Task-Owned Hash Path Audit

- **Minting (Server-Side):** `scripts/artifact_store.py:94` computes `sha256 = hashlib.sha256(data).hexdigest()` directly from byte payload. Mismatch with claimed hash raises `ArtifactError` immediately at upload.
- **Intake Validation:** `server/app.py:355+` validates format and calls `ARTIFACT_STORE.check_reference`.
- **Verifier Fetch:** `scripts/courier_verifier.py:fetch_artifact` fetches bytes only from the authoritative server endpoint (`/artifacts/<id>`).
- **Resolution:** Verifier must use `record.sha256` (task/server owned) rather than `art.get("expected_sha256")` (worker owned).

---

## 4. Worker Self-Authorization & Duplicate Replay Negatives Matrix

| Scenario / Resend Mutation | Current B-2 Behavior | Expected Safe Behavior | Verdict |
| :--- | :--- | :--- | :--- |
| Exact identical replay | `ACK_DUPLICATE` (`app.py:366`) | `ACK_DUPLICATE` | **PASS (Idempotent safe)** |
| Status omitted on resend | `ACK_DUPLICATE` (`app.py:366`) | `ACK_DUPLICATE` (if helper-minted) | **PASS (Intended by B-2)** |
| Status mutated (`SUCCESS` $\to$ `FAILED`) | `ACK_DUPLICATE` (B-2 dropped check) | `HTTP 409 Conflict` | **FAIL on B-2; Fix in B-3** |
| Worker ID mutated | `ACK_DUPLICATE` | `HTTP 409 Conflict` | **FAIL on B-2; Fix in B-3** |
| Attempt ID mutated | `ACK_DUPLICATE` | `HTTP 409 Conflict` | **FAIL on B-2; Fix in B-3** |
| Artifact list emptied/mutated | `ACK_DUPLICATE` | `HTTP 409 Conflict` | **FAIL on B-2; Fix in B-3** |
| Result ID mutated | `HTTP 409 Conflict` (`:369`) | `HTTP 409 Conflict` | **PASS (Rejection safe)** |
| Superseded attempt resend | `HTTP 400 Bad Request` | `HTTP 400 Bad Request` | **PASS (Fail-closed)** |

---

## 5. Fixture Hashes and Deterministic Acceptance

- **Canary A Payload:** `COURIER-A2B-A\n` (14 bytes)  
  $\to$ **SHA-256:** `575114332fb4ccd482dd9ca60dbaccc15b579afeb372f0c92b6f7eefe219049b`
- **Canary B Payload:** `COURIER-A2B-B\n` (14 bytes)  
  $\to$ **SHA-256:** `b9032958fc90e7380195fcc51eca5822d60bb31eb15d370a44c3c15e60942a50`
- **Negative Fixture:** `WRONG-PAYLOAD\n` (14 bytes)  
  $\to$ **SHA-256:** `5cfdae7fb8ff6e65123984e1fc20b704c7ebbb4ff51a44e5f7a26f0efb672728` $\to$ Verifier rejection verified.

---

## 6. Stale-Report and Invalid-Proof Detections

1. **Stale B-2 Status Claims:** Any report citing `origin/candidate-b-2` (`83940de3`) as the final verified candidate for production release is stale. Base remains `candidate-b-1` until `candidate-b-3` is authored.
2. **Branch Name Collision:** Branch `finish-cb3` (`dc03c250` / `9f45fa9c`) must not be confused with `candidate-b-3`. Evidence cards must cite full commit SHAs.

---

## 7. Mac Isolation & Physical Execution Checklist

- **Production Confinement:** Production Server (`PID 69407` on port 8080), Verifier (`PID 42002`), and Worker (`PID 46250`) untouched and running.
- **Canary Workspace:** Dedicated isolated directory at `/Users/user/Downloads/courier_canary`.
- **Canary Port:** Port 8081 verified 100% free and isolated from port 8080.
- **Canary Storage:** Dedicated artifacts directory `/Users/user/Downloads/courier_canary/artifacts` and state file `/Users/user/Downloads/courier_canary/server/state/central_state.json`.
- **Pre-execution Gate:** Physical execution on hardware is gated on Central Writer publishing candidate `b-3`.

---

## 8. Convergence Decision

All 17 final-gate swarm items have been completely analyzed, cross-verified, and documented against repository and hardware truth.

- **UNRESOLVED WORK REMAINING ON MAC:** NONE.
- **NEXT ACTION:** Standing by for Windows Central Writer release of `candidate-b-3`.
- **STATUS:** `FINAL_GATE_IDLE_SAFE=YES`.
