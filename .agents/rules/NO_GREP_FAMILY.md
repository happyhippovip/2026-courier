# Antigravity Search Rule — No Grep Family

This rule is persistent for Courier Symphony Antigravity work.

## Hard prohibition

Do not invoke shell search commands from the grep family in this repository.

Prohibited commands include:
- grep
- egrep
- fgrep
- git grep
- rg
- ripgrep

Do not wrap, alias, pipe, shell-expand, or indirectly invoke those commands.

Do not use recursive whole-repository text scans merely to discover where something is.

## Preferred search order

1. Use the editor/agent's indexed workspace search or code-search capability.
2. If the exact file/path is already known, read that file directly.
3. If remote repository search is appropriate, use GitHub code/file APIs.
4. If a local shell fallback is unavoidable, enumerate tracked paths with `git ls-files` and perform a bounded read-only search without grep-family binaries.

Any local fallback must be bounded:
- tracked files only;
- no symlink traversal;
- skip binary files;
- skip files larger than 2 MiB unless the exact file is explicitly required;
- stop after 200 matches;
- stop after 20 seconds;
- never scan `.git`, build artifacts, caches, dependency/vendor trees, generated outputs, logs, or unrelated worktrees.

## Stuck-task rule

If a grep-family command is already running:
- stop/cancel that command;
- do not retry it with broader flags;
- do not queue another grep-family replacement;
- switch immediately to indexed/code search or a bounded tracked-file fallback.

## Scope

This is a development-orchestration safety/performance rule.
It does not change Courier product behavior.

Current repository truth and higher-priority safety rules still apply.
