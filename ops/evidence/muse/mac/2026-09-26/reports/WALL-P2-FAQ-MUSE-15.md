# WALL-P2-FAQ — draft (evidence-gated, PREP ONLY)

WORKER=MUSE-15 · HOST=MAC · MODE=READ_ONLY · 2026-09-26T15:50Z
TASK=WALL-P2-FAQ · feeds landing block 6 (see WALL-P2-LANDING-STRUCTURE-MAC02)
Forbidden claims honored: no unproven claims, no installer-exists, no fake
customers, no SLA. Each answer carries its evidence tag or PLACEHOLDER.

## Fresh evidence observed by this worker
- server.app PID 69407, elapsed 1d 03:20, LISTEN localhost:8080
  (`lsof -ti:8080` + `ps`; same PID as MMAC1/MAC-CORE-WORKER-001 — no restart).
- REPO HEAD=332a42f9 (`git rev-parse --short HEAD`).
- No pyproject.toml / uv.lock at repo root; README documents
  `python3 scripts/verify_autonomous_readiness.py` as readiness check.
  → No installer story exists; install answers stay aspirational/PLACEHOLDER.

## FAQ copy (draft)

**What does Courier actually do?**
It executes a task, checks the result, and continues with the next one —
in isolated test runs, without a human relay between steps.
[EVIDENCE: GM5 canary A→VERIFY→B, HUMAN_RELAY=0 — fixture-scoped.]

**How does it check its own result?**
By exact-hash comparison against a pre-declared expected result — not by
judgment. [EVIDENCE: hash-match verifier, PASS→RECONCILED — GM5 mapping.]

**What kind of tasks is it proven on?**
Only deterministic, byte-predictable tasks with checkable results — not on
open-ended work. [EVIDENCE: deterministic fixtures with expected_sha256 —
E04/E05, MMAC4. See HONEST LIMITS on the landing page.]

**Can I install it on my machine today?**
Not yet — there is no installer and no customer-machine story.
[FACT: no installer in repo; RV11 prep-only. PLACEHOLDER for install steps
until WALL-P2-DOWNLOAD-IA lands with a real path.]

**What do I need to run it? (prerequisites)**
PLACEHOLDER — pending WALL-P2-DOWNLOAD-IA. Do not publish until the
prereq list (Python version, git, disk) is verified against a real install.

**Who is a pilot for?**
One repeatable task with a checkable result, run in isolation, measured by:
done on first try, verified, continued alone, recovered from restart.
If any measure fails, the pilot fails — that is the deal.
[COPY from landing PILOT block; restart-recovery evidence owned by
WALL-P1-RESTART-MATRIX — do not pre-claim here.]

**How do I get support / contact you?**
PLACEHOLDER — pending WALL-P2-SUPPORT-FLOW. No support address is published
until that task lands commercial-safe wording.

**How much does it cost?**
PLACEHOLDER — no pricing exists; the payment path is not runnable
[EVIDENCE: E30 triple dead]. Never invent a price.

**Where is my data / what about privacy?**
See the privacy dataflow note (WALL-P2-PRIVACY-DATAFLOW-MAC-21). FAQ defers
to it; no independent claims made here.

STATUS=DRAFT_COMPLETE · 7 answered (4 evidence-backed, 3 labeled
PLACEHOLDER) · consistent with landing copy, no contradictions
