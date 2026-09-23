# CLAUDE.md

Claude/Claude Code must read these files before changing Courier:

1. `AGENTS.md`
2. `docs/MASTERPLAN_COURIER.md`
3. `docs/STATUS.md`
4. `.agents/rules/00-courier-autonomy.md`
5. `docs/RELEASE_CANDIDATE.md` when release work is involved

## Authority and scope

- `docs/MASTERPLAN_COURIER.md` is the current strategic roadmap.
- `docs/STATUS.md` is the current operational checkpoint.
- No evidence = no PASS.
- Before code claims, report branch + full SHA, otherwise UNKNOWN.
- Do not invent completion from model self-reports.
- No merge, canonical push, release, publication, spending, account action, or secret handling without Dennis's explicit approval.
- Do not commit funding, Jobcenter, account, billing, customer-private, secret, or credential data.

## Current priority

**Cannon V1 freeze only.**

Work order:
1. Resolve the official `pre-yolo-patch` baseline with evidence.
2. Reproduce and identify the live-text failure.
3. Get Mac and Windows tests stably green.
4. Run the 5-run Cannon acceptance and evaluate the infinite run.
5. Prepare freeze evidence for tag `courier-cannon-v1` and bundle backup.

Do not add later-stage product features before this stage is accepted.

## Work-block output

End each meaningful work block with:

- STATUS: BELEGT | BEHAUPTET | VERMUTET | UNKNOWN
- BRANCH:
- FULL_SHA:
- CHANGED:
- TEST:
- EVIDENCE:
- NEXT_SINGLE_STEP:

Update `docs/STATUS.md` when the operational checkpoint materially changes.
