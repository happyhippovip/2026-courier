# MAC-FINISH-19 — Retest Trigger Matrix

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-19
- **Area**: RETEST_TRIGGER_MATRIX
- **Status**: COMPLETE

Specifies what file changes invalidate test proofs vs what changes allow 100% result reuse.

---

## 2. Retest Matrix Table
| File Pattern | Scope | Targeted Tests | Matrix | RUN_1 / RUN_2 | Proof Card |
|---|---|---|---|---|---|
| `server/**/*.py` | Core Application | RETEST | RETEST | INVALIDATE | INVALIDATE |
| `scripts/**/*.py` | Harness / Workers | RETEST | RETEST | INVALIDATE | INVALIDATE |
| `tests/**/*.py` | Unit / Contract Tests | RETEST | RETEST | REUSE | REUSE |
| `ops/ai/**/*.md` | Ops / Prompts / Docs | REUSE | REUSE | REUSE | REUSE |
| `docs/**/*.md` | Strategy / Specs | REUSE | REUSE | REUSE | REUSE |
