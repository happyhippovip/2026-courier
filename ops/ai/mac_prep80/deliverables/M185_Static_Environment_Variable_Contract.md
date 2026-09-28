# M185 — Static Environment Variable Contract

## 1. Overview & Authority
- **Task ID**: M185
- **Area**: ENV_CONTRACT
- **Status**: COMPLETE

## 2. Canonical Variable Contract
- `PORT`: Fixed to `8081` for isolated verification run.
- `STATE_DIR`: Isolated directory path (`server/state/isolated_run1`).
- `COURIER_AUTH_TOKEN`: Static pre-shared token for worker authentication.
- `COURIER_VERIFIER_API_KEY`: Static cryptographic key for verifier attestation.
- `PYTHONUNBUFFERED`: `1` for deterministic stdout flush.
