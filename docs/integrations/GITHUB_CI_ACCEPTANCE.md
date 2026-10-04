# GitHub CI Acceptance Gate

## Purpose
This document outlines the technical boundaries and CI validations for Courier's GitHub integration path (`.github/workflows/github-ci.yml`). This gate runs on untrusted PRs and forks without requiring real credentials, proving that Courier safely interacts with the GitHub API during customer operations.

## What CI Proves
- **Deterministic Failure Handling:** The gate exercises deterministic mocked/fake GitHub responses for all expected failure modes (401, 403, 404, 409, 422, timeouts, stale events).
- **Secret Redaction:** Proves that representative tokens, OAuth secrets, and `Authorization` headers are sanitized and never exposed in logs.
- **Minimum Permissions:** The workflow uses `permissions: contents: read` to prove that it can validate the logic without needing write authority.
- **Cross-Platform Consistency:** Ensures the GitHub client and event analysis code behave identically on `ubuntu-latest` and `windows-latest`.

## What CI Deliberately Mocks
- We mock all actual network responses (using fakes or `requests` mocks) to guarantee determinism.
- Authentication tokens are dummied out (`gh_real_token`) to verify redaction logic.
- We do not trigger real GitHub Actions workflow runs (`workflow_dispatch`) during these tests.

## What Requires Real-Provider Acceptance
- Actual OAuth handshake and token persistence.
- E2E webhook delivery from GitHub to Courier's live intake plane.
- Verification of side-effects on live GitHub repositories (e.g., creating real PRs, observing real rate-limiting behavior).

## Customer Authorization Boundary
Courier enforces a strict boundary requiring a customer to actively authorize repository access. This CI gate validates that if those credentials are revoked, expired, or lack scope, Courier degrades gracefully (`NEEDS_YOU` or `PERMISSION_REQUIRED`) instead of crashing, leaking existence of private resources, or blindly retrying.
