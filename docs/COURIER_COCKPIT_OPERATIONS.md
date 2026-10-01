# Courier Cockpit operations

## Customer-facing endpoints

- `http://127.0.0.1:8080/health` is the Courier API health check. A small JSON
  response such as `{"status":"healthy"}` is expected; it is not the visual UI.
- `http://127.0.0.1:8088/` is the Courier Chief Operations Cockpit.

Keeping the API and cockpit on separate ports prevents the UI launcher from
mistaking a healthy API listener for an already-running cockpit.

## Starting and checking the existing cockpit

Run the repository's idempotent launcher:

```sh
python3 scripts/launch_visual_studio.py
```

The launcher leaves an existing listener untouched and reports either
`STUDIO_ALREADY_RUNNING` or `STUDIO_STARTED`. Its bounded startup log is stored
in the operating system's temporary directory as
`2026-courier-visual-studio.log`.

## September 2026 startup incident

The cockpit returned `ERR_CONNECTION_REFUSED` while the Courier API health
check remained healthy. The cockpit process was exiting during import because
optional enrichment registries were absent from the deployed repository. A
single grouped import made those optional modules a hard startup dependency.

The repair keeps the core Chief Commander and Bodyguard components mandatory,
but loads capability, skill, connector, standing-objective, resource, and live
truth enrichments independently. Missing enrichments now render their existing
safe empty/unknown fallback state instead of taking down the whole cockpit.

The regression test `tests/test_visual_studio_startup.py` imports the production
server in the same repository shape and fails if an optional enrichment again
becomes a hard startup dependency.
