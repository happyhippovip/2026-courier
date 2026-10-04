# attic/ (owned by L1)

Files moved out of the active tree because nothing in the product, the tests
or the workflows reads them. They are kept in place (not deleted) so their
history and content stay one click away.

- Nothing in `attic/` is imported, collected by pytest (`testpaths = tests`)
  or packaged.
- A file moves back only through an L1 integration step that names the reader
  that needs it.
- Each subfolder is one logged move; see `docs/v1/INTEGRATION_LOG.md`.

| Folder | Moved in | Contents |
|---|---|---|
| `root-scratch-2026-10-01/` | L1 cycle 2, hygiene step | Former repo-root scratch: smoke scripts (`test_canary.py`, `test_retry.py`, `phase8_workforce_temp.py`), sample tasks (`dummy_task*.json`, `task.json`, `test_mac_task.json`) and outputs that scripts or workflows wrote into the root (`result.json`, `gemini_result*.json`, `handoff.json`, `reconciliation.json`, `founder_concierge_result.json`, `agy_test_*.txt`). The writers still write at the root; those names are now ignored there. |
