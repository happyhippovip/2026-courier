# Contributing to Courier Symphony

Thank you for looking. The project is pre-release and moves fast, so a few rules keep it stable.

## Before you write code

- Open an issue first and say what you want to change and why. One issue, one problem.
- No license has been chosen yet (see the README). Until one is, the project can take issues, bug reports, reproductions and test ideas, but not code from outside the project.

## How changes land

- The trunk is `integration/v1`. Nobody commits to it directly.
- Every change is a pull request into `integration/v1` with one purpose. Its title starts with the lane it belongs to, for example `[L3] Worker releases its socket on stop`.
- A pull request lands when CI is green on Windows and Linux for its exact commit and someone other than the author has reviewed it.
- A fix comes with the smallest test that fails without it. Tests are not weakened to get a green run.

## Lanes

| Lane | Area |
|---|---|
| L1 | Integration, CI and the golden tests |
| L2 | Journal, controller and API |
| L3 | Bounded worker host |
| L4 | Verifier and synthetic adapter |
| L5 | Desktop hub and replay |
| L6 | Packaging, launcher, paths, logging and diagnostics |

There are no other lanes. [AGENTS.md](AGENTS.md) and [docs/V1_RULE_0.md](docs/V1_RULE_0.md) describe the route to V1 and are binding for people and for AI agents alike.

## Running the tests

Requires Python 3.12, the version CI uses.

```bash
python -m pip install -e ".[test]"
python -m pytest -q tests
```

## What does not belong in the repository

- Secrets, tokens and personal data.
- Temporary files, logs and test output.
