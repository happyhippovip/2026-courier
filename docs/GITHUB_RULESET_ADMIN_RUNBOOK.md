# GitHub protected-review ruleset administration

This repository artifact documents the external settings required to make the
workflow proposal path human-reviewable. It is **not evidence** that any
GitHub ruleset or branch-protection setting has been applied.

## Required administrator actions

1. In the GitHub repository, create a repository ruleset targeting the default
   branch (`main`) and any future default-branch aliases.
2. Require a pull request before merging; require at least one approving human
   review and dismiss stale approvals when new commits are pushed.
3. Require the `Process safety guard / github-actions-policy` check to pass
   before merging. Do not permit bypass by GitHub Actions, bots, or the
   repository administrator unless a separately recorded emergency procedure
   is approved.
4. Block direct pushes to `main`, including pushes made with
   `github-actions[bot]` credentials. Do not grant Actions a ruleset bypass.
5. Require conversation resolution and prohibit force pushes and branch
   deletion on `main`.
6. In Actions settings, allow only GitHub-hosted runners for this repository;
   do not attach self-hosted, personal Mac, or personal Windows runners.
7. Set the repository Actions default `GITHUB_TOKEN` permission to read-only.
   The narrowly scoped `propose-result` job requests its own `contents` and
   `pull-requests` write permission solely to create a reviewable proposal
   branch and PR.

## Evidence required before claiming enforcement

Record an administrator-visible ruleset URL or screenshot, its ruleset ID,
the exact target branches, enabled required-review and required-check rules,
the bypass actor list, and the Actions runner/token settings. Without that
observable evidence, report external ruleset status as `NO_UNLESS_OBSERVABLY_PROVEN`.
