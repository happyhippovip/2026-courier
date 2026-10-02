# OpenAPI Drift Report

**Date:** 2026-09-29
**Finding:** Critical specification drift between actual `server/app.py` endpoints and `static/openapi.json`.

## Summary
The OpenAPI spec intended for external integrations (ChatGPT Custom Actions, Claude) only documents 2 routes, while the backend server actively exposes 21 routes.

## Unmapped Critical Routes
The following endpoints exist in the system but are completely invisible to external AIs because they are missing from the OpenAPI spec:
* `/tasks/claim`
* `/tasks/result`
* `/tasks/verify`
* `/workers/register`
* `/workers/heartbeat`
* `/goals`
* `/goals/{goal_id}`
* `/ledger/stream`

## Impact
Any external GPT configured with the current `openapi.json` cannot participate in the Ledger loop because it cannot claim tasks or submit results.

## Recommended Action
Re-generate the OpenAPI spec directly from the Flask AST or using a tool like `apispec` to ensure 100% route coverage before multi-window rollout.
