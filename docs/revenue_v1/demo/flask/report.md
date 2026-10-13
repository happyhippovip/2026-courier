# GitHub Actions Safety Baseline Report

**Target:** pallets/flask @ d086db856be187255b8ec61ef409357393020f32

## Findings
- **lock.yaml**: Missing timeout-minutes configuration (jobs: lock). (timeout)
- **pre-commit.yaml**: Missing timeout-minutes configuration (jobs: main). (timeout)
- **publish.yaml**: Missing timeout-minutes configuration (jobs: build, create-release, publish-pypi). (timeout)
- **tests.yaml**: Missing timeout-minutes configuration (jobs: tests, typing). (timeout)
- **zizmor.yaml**: Missing timeout-minutes configuration (jobs: zizmor). (timeout)
