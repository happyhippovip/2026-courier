# MUSE-45 T-R — Server route-contract cross-check (read-only)

Branch fix-cb1-new @ 329abd80. server/app.py routes vs daemon-called endpoints.
P3 file: READ ONLY (route + result-handler skim, no edits). Shell DOWN.

## Route matrix (OBSERVED)

| Daemon call | Server route | Verdict |
|---|---|---|
| /workers/register | :181 POST | EXISTS |
| /workers/heartbeat | :241 POST | EXISTS |
| /tasks/claim | :260 POST | EXISTS |
| /tasks/result | :352 POST | EXISTS |
| /artifacts (upload) | ABSENT | absent-BY-DESIGN (both daemons gate upload behind COURIER_ARTIFACT_UPLOAD opt-in; "P3 cutover" pending per code comments) |

## /tasks/result semantics vs daemon classifiers (COMPATIBLE)

- Exact resend (9-field match incl. run_id/result_id) -> 200 ACK_DUPLICATE
  (:367-368): idempotent redelivery SUPPORTED server-side, matching both
  daemons' redeliver-same-payload behavior.
- Processed-task conflict / not-awaiting-result -> 409 (:369-370, :373-374);
  contract violation / unknown task -> 400 (:380-381, :413). All 4xx ->
  both daemons classify REJECTED-final (mac: not-"5"; win: <500) -> release
  path. Compatible.
- SUCCESS -> RESULT_RECEIVED pending /verify (:385-386); FAILED -> retry <3
  else FAILED_TERMINAL (:388-392). Daemons don't consume the distinction
  post-delivery (correct: delivery ACK ends their duty).
- ARTIFACT_STORE.check_reference validates artifact_id refs (:377-379):
  server-side artifact validation exists despite no upload route (local
  store class; consistent with opt-in).

## Notes (INFO only)

- Win daemon comment (:117) names "200 IGNORED" for already-processed; server
  says ACK_DUPLICATE. Comment-only drift; behavior-compatible (daemons accept
  any 200 as DELIVERED). No action.
- Extra server routes (/health, /status, /goals, /walls, /unregister,
  /reclaim_stale, /pending_verification, /verify, /resume) serve other
  clients; out of daemon-contract scope.

## Verdict

No contract mismatch on any daemon-called route. T-R closes the loop opened
by T-O/T-Q (daemons) from the server side. No finding above INFO.
