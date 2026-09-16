Subject: Windmill Labs - GitHub Actions Safety Baseline Report (EUR 99)

Hello Windmill Team,

Thank you for requesting the Revenue V1 GitHub Actions Safety Baseline Report for windmill-labs/windmill. We have completed our read-only, immutable-SHA inspection (SHA: 796b6e5297d8cceb842ec097f33ec1c3115058bd).

### Summary of Findings
Our deterministic repository inspection analyzed your workflows and identified several areas for potential security and stability hardening:
- **Missing Explicit Permissions:** Many workflows default to implicit permissions. We recommend adding explicit `permissions:` blocks (e.g. `contents: read`) to adhere to the principle of least privilege.
- **Permissive Write-All Detected:** Workflows such as `build-caddy-l4-image.yml`, `build-publish-rh8-image.yml`, and `docker-image-rpi4.yml` contain a permissive `write-all` permission. We strongly recommend scoping this down.
- **Missing Timeout Configurations:** A significant number of workflows are missing `timeout-minutes:`, leaving them vulnerable to unbounded execution times and potential runner exhaustion.
- **Missing Concurrency Blocks:** Many workflows lack `concurrency:` configurations, which could lead to redundant parallel runs on the same ref.
- **Mutation Risk:** The `git push` command was detected directly in some workflows (e.g., `benchmark.yml`, `go_on_release.yml`, `helmchart_on_release.yml`), which could be a risk if branch protections or token scopes are compromised.

The complete automated report is attached. 

Best regards,
Courier Commercial Engineering
