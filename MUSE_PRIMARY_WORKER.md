# Muse Primary Worker Policy

Status: standing project policy until the owner explicitly changes it.

## Roles

- **Muse is the primary execution worker** for Courier / AWS / project operations.
- **ChatGPT acts as manager/planner**: decides sequence, reviews evidence, and provides the next single prompt for Muse.
- Other agents (for example Google research) are secondary helpers and must not overlap with Muse's current live-write scope.

## Operating rule

Work step by step:

1. Give Muse exactly one bounded prompt.
2. Let Muse finish or return a concrete blocker.
3. Review the result/evidence.
4. Only then issue the next prompt.

Do not stack multiple live-change prompts at once.

## Live infrastructure

For AWS or other live systems:

- Muse owns the active live-change lane unless explicitly reassigned.
- Preserve known-good state.
- Prefer read-only verification before changes.
- Make the smallest required change.
- Fail closed when the current state cannot be verified.
- Never guess values, credentials, process ownership, or security settings.
- Do not broaden network access unnecessarily.
- Keep unrelated systems, processes, and repositories untouched.

## Courier runtime invariants

- MAX_ACTIVE_EXTERNAL=1
- MAX_UNANSWERED_PROMPTS_PER_LANE=1
- One task -> result -> persist -> verify -> reconcile -> DONE -> cooldown -> next task.
- If outcome is UNKNOWN, do not start the next task.
- No human "weiter" should be required during the proven unattended path.
- Reuse known-good checkpoints and backups; do not redesign working core behavior without an explicit reason.

## Persistence

Important proven states should be documented in Git/GitHub with recovery information and without committing secrets.

Never commit unencrypted:
- passwords
- private keys
- AWS access keys
- API tokens
- provider/session secrets



## Competitive intelligence

For product, market, infrastructure, website, funding, and UX research, follow:

`docs/COMPETITIVE_ADVANTAGE_RULEBOOK.md`

Standing rule:
- study strong public products and public evidence;
- extract the useful principle;
- rebuild it in an original Courier-specific form;
- improve it where measurable;
- preserve provenance;
- never copy proprietary code, non-public information, trade secrets, protected assets, or credentials.

Confidential strategy is never stored in this public repository. Use only ignored/encrypted local confidential storage for genuinely sensitive material.
