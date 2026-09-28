# M208 — Cross-Run State Reset & Zero-Leakage Directory Scrubber

## 1. Overview & Authority
- **Task ID**: M208
- **Area**: STATE_RESET
- **Status**: COMPLETE

## 2. Scrubber Protocol
- Before RUN_1: Scans and purges any remnant `server/state/isolated_run1`.
- Before RUN_2: Verifies that RUN_1 state is preserved as baseline, while RUN_2 runs in fresh workspace or strictly controlled recovery mode.
