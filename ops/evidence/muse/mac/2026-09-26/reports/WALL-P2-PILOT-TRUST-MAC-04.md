# WALL-P2-PILOT-TRUST — agreement inputs, boundaries, privacy (MAC-04)

TASK_ID=WALL-P2-PILOT-TRUST · STATUS=DONE · WORKER=MAC-04 · HOST=MAC ·
MODE=READ_ONLY · 2026-09-26T15:51Z. Design inputs for a real agreement, not
legal text. Pairs with WALL-P2-PRIVACY-DATAFLOW-MAC-21 + SUPPORT-FLOW-MAC-21.

## PILOT_AGREEMENT_INPUTS (fill per pilot, both sides sign a page)
SCOPE_FOLDER= / ALLOWED_ACTIONS= / FORBIDDEN (customer's never-touch list) /
GATES (who answers money/auth/publish/destructive, max latency) /
DURATION (2 weeks, dates) / PRICE_VARIANT (a/b/c per offer) + refund rule /
SUCCESS_CRITERIA ref (measurement report) / EXIT (either side stops anytime;
customer keeps all proof cards + state export) / DATA (inventory below).

## SUPPORT_BOUNDARIES
We do: fix our setup, re-run the witness test, explain any proof card line,
pause/resume on request, export state at exit. We do NOT: do the chore
manually for them, expand scope mid-pilot, debug their other tools, promise
24/7 (response: next working day). Support channel: one email thread per
pilot. Anything outside -> new pilot or declined in writing.

## PRIVACY_CHECKLIST (operator runs through with customer, tick + initial)
[ ] No passwords/keys stored by us (customer types gates themselves).
[ ] State dir location shown; customer can open/delete it.
[ ] Proof cards contain file names -- confirm no secret names in scope.
[ ] No data leaves the customer machine in pilot phase (localhost only).
[ ] Exit = state export handed over + our copies deleted on request.

## DATA_PROCESSING_INVENTORY (pilot phase, minimal)
HELD: task envelopes (ids, timestamps), result records + artifact hashes
(not contents beyond what the chore itself writes in their folder),
heartbeat/availability timestamps, proof cards. NOT HELD: credentials,
file contents outside scope, biometrics, third-party personal data.
LOCATION: customer machine (+ operator email thread). RETENTION: pilot +
30 days, then deleted unless extended in writing.

## SETUP_CHECKLIST (operator, 10 min before STEP_2)
[ ] Python 3.9+, Flask + gunicorn installed per install notes (prep only).
[ ] deploy/.env with fresh keys (never the dev-secret placeholders).
[ ] STATE_FILE path outside any synced folder (no iCloud/Dropbox races).
[ ] Port 8080 free (or configured other); /health answers.
[ ] Scope folder exists, forbidden paths verified absent from config.
[ ] Witness-test script + proof-card sample printed or on screen.
