# Google IDE Known-Good Direct Path — 2026-09-28

Status: ACTIVE

Environment:
- Windows
- Google/Antigravity IDE with the 2026-courier repository already open

Use:
- direct natural-language task instructions;
- local repo files;
- terminal commands only when the task needs them;
- save concrete outputs under ops/ai/, docs/, tests/, or other task-authorized repo paths.

Do not require:
- git show
- a prompt file loader
- google_cli_worker_adapter.py
- an external claim service
- a second model window

Remote Git is used only when the task itself requires remote durability.

Current project order after Ledger completion:
1 PRE_CODEX durability support
2 PRE_CODEX handoff
3 Codex HIGH once
4 Mac exact binding
5 RUN_1
6 RUN_2
7 Core Freeze
8 minimum real pilot
9 Product Shell after positive pilot signal

Google IDE default authority:
- read
- analyze
- create/update ops/docs/test-support artifacts
- targeted deterministic checks
- no final application-source mutation unless an explicit durable task grants it
- no physical RUN_1/RUN_2 ownership
