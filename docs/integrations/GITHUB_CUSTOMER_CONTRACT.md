# GitHub Customer Contract

## Core Philosophy
Make Courier's future GitHub connection safe and boring for normal customers. Courier strictly acts within explicit boundaries, maintaining absolute clarity on authority, failure states, and credential handling.

## User Journey
1. **CONNECT GITHUB** - The customer initiates the connection.
2. **SELECT / AUTHORIZE REPOSITORY** - The customer explicitly scopes the authorization to specific repositories.
3. **READ ALLOWED REPO DATA** - Courier accesses the repository context read-only where permitted.
4. **CREATE AUTHORIZED WORK** - Courier dispatches bounds-checked actions to the repository.
5. **OBSERVE RESULT** - Courier monitors the work asynchronously and reports safely back to the user.
6. **REVOKE / DISCONNECT** - The customer can sever the connection at any time.
7. **CONTINUE SAFELY** - Courier gracefully degrades, reporting disconnected state without crashing.

## Authority & Boundaries
Courier must **never** silently expand GitHub permissions. 

A user-authorized repository does **NOT** imply authorization for:
- Every repository in the user's account or organization.
- Organization administration.
- Access to secrets.
- Destructive branch operations.
- Direct merges or force pushes.
- Deleting repositories.

Read and write authority must remain explicit and verifiable at all times.

## Privacy & Security
Courier will **never** log:
- Access tokens (PATs, installation tokens).
- OAuth secrets.
- Private credentials.
- Raw authorization headers.

## Customer Error UX
Errors must never expose stack traces or internal lane/model jargon to the customer. Errors are grouped into these user-facing categories:

* **NEEDS YOU**: Setup incomplete, authorization revoked, or explicit action required.
* **RETRYING SAFELY**: Transient network or API availability issues.
* **PERMISSION REQUIRED**: Attempted action exceeds current granted authority.
* **GITHUB UNAVAILABLE**: GitHub API is down, rate limited, or unreachable.
* **ACTION NOT AUTHORIZED**: A strictly forbidden action was blocked locally before transmission.
* **ACTION MAY HAVE HAPPENED / VERIFY**: Network timeout during a state-mutating operation where completion is uncertain.

## Expected Failure Modes
Courier handles the following scenarios robustly, categorizing them into the UX groups above:
- No GitHub account connected
- Authorization denied
- Expired/revoked credential
- Insufficient repository permission
- Private repository restrictions
- Repository deleted/renamed
- Branch deleted
- Default branch changed
- Branch protection violations
- PR already exists
- Duplicate request
- Network timeout
- GitHub 401 (Unauthorized)
- GitHub 403 (Forbidden / Secondary Rate Limit)
- GitHub 404 (Not Found, handled without leaking private-resource existence)
- GitHub 409/422 (Conflict / Unprocessable)
- API rate limit exceeded
- Partial API failure
- Webhook/event duplication
- Stale event detection
- User disconnects while work is running
