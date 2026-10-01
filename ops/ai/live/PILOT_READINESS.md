# PILOT READINESS

## Goal Contract
The goal of the first physical pilot is to demonstrate that a naive user can run the `Courier` client, request a task, and return an artifact to the server, resulting in a verifiable state change, with zero manual setup of databases or state on their side.

## Permission / Privacy Boundaries
- **Server:** Has access to the `ledger.db` and the master artifact storage.
- **Client (Worker):** Has NO access to the server's ledger or artifact storage directly. It communicates strictly via the HTTP REST API.
- **Privacy:** Client artifacts must not leak external environment variables. The server must only accept artifacts requested by the dispatch.

## Onboarding
The onboarding process for the pilot must be minimal:
1. Provide the user with the client script/executable.
2. Provide a single API key or token (if required).
3. The user runs the script without complex environment configuration.

## Setup-Time Measurement
- Target setup time for the pilot user: < 5 minutes.
- The time begins when the user downloads the client and ends when the first task is successfully acquired.

## Issue Classification
- **Core Fault:** The server crashes or the ledger corrupts (P0).
- **Client Fault:** The worker script crashes on the user's machine (P1).
- **Network Fault:** Connectivity issues between client and server (P2).

## Success/Failure Evidence
- **Success:** The server logs a `RECONCILED` state for the pilot task, and the `artifact.json` matches the expected server-side hash.
- **Failure:** The worker fails to obtain the task, or the server rejects the artifact due to a hash mismatch or authorization failure.

Status: PREPARED
