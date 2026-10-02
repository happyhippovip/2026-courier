# Legacy tests (owned by L1)

This directory holds tests of the pre-v1 runtime (snapshot state in
`server/state/central_state.json`, the legacy `server/app.py` routes,
`scripts/*` workers) **after** an L2–L6 component has replaced the behaviour
they cover. It is empty until the first replacement lands.

Rules:

1. A test moves here only in an L1 integration step. That step's entry in
   `docs/v1/INTEGRATION_LOG.md` names the moved test and the v1 test (golden or
   lane-owned) that now covers the behaviour.
2. Moved tests keep running in the regression gate. Only an explicit, logged
   L1 decision may exclude a legacy test from the gate, and only together
   with removing the legacy code it covers.
3. No `skip`/`xfail` markers are added to hide a failure. A legacy test that
   breaks because its code was intentionally removed is deleted together with
   that code in the same logged step.
4. New tests are never written here. v1 behaviour is tested in `tests/golden/`
   (L1) or in the owning lane's tests.
