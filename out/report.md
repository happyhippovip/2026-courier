# Repo Reality Check — 2026-courier-candidate

Commit: `65bf8b08d998c776681a93f019a21eec589bf2f5`

Files scanned: 2050 · high 3 · medium 50 · low 44

Read-only scan; no code was executed. Secret findings show location and type only.

## Secrets (10)

- **low** `github_token` — tests/test_evaluate_memory_proposal_for_auto_approval.py:86: test fixture shape (low entropy, in tests/)
- **low** `private_key_block` — tests/test_evaluate_memory_proposal_for_auto_approval.py:89: test fixture shape (low entropy, in tests/)
- **low** `github_token` — tests/test_register_social_channel.py:22: test fixture shape (low entropy, in tests/)
- **low** `github_token` — tests/test_run_antigravity_bridge.py:16: test fixture shape (low entropy, in tests/)
- **low** `openai_style_key` — tests/test_run_antigravity_bridge.py:17: test fixture shape (low entropy, in tests/)
- **low** `github_token` — tests/test_run_antigravity_bridge.py:73: test fixture shape (low entropy, in tests/)
- **low** `github_token` — tests/test_run_codex_bridge.py:17: test fixture shape (low entropy, in tests/)
- **low** `openai_style_key` — tests/test_run_codex_bridge.py:18: test fixture shape (low entropy, in tests/)
- **low** `github_token` — tests/test_run_codex_bridge.py:56: test fixture shape (low entropy, in tests/)
- **low** `private_key_block` — tests/test_run_content_production_pipeline.py:49: test fixture shape (low entropy, in tests/)

## Safety (2)

- **high** `KILL_BY_NAME` — scripts/windows_worker/stop.bat:3: taskkill /F /IM Courier.exe 2>NUL
- **medium** `WILDCARD_BIND` — deploy/run-supervisor.sh:23: gunicorn -w 1 --threads 4 -b 0.0.0.0:8080 server.app:app &

## Hygiene (39)

- **high** `generated_or_private_file_tracked` — scripts/windows_worker/dist/libs/certifi/cacert.pem: tracked; usually belongs in .gitignore
- **medium** `binary_committed` — events/digital-assets/dist/FruitKI_3D_Commercial_Pack_v1.0.0.zip: 1 KiB without build provenance
- **medium** `binary_committed` — events/revenue-opportunities/offerings/kibey_ai_marketplace/dist/KIBEY_PILOT_DELIVERY_PACKAGE_v1.0.0.zip: 2 KiB without build provenance
- **medium** `generated_or_private_file_tracked` — pytest.log: tracked; usually belongs in .gitignore
- **medium** `binary_committed` — scripts/windows_worker/Courier.exe: 9 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/CourierWorker-v1.zip: 13790 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/Courier_Debug.exe: 9 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/Courier.exe: 9 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/bin/bottle.exe: 45 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/bin/cffi-gen-src.exe: 45 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/bin/flask.exe: 45 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/bin/idna.exe: 45 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/bin/normalizer.exe: 45 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/clr_loader/ffi/dlls/amd64/ClrLoader.dll: 10 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/clr_loader/ffi/dlls/x86/ClrLoader.dll: 10 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/pythonnet/runtime/Python.Runtime.dll: 440 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/webview/lib/Microsoft.Web.WebView2.Core.dll: 634 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/webview/lib/Microsoft.Web.WebView2.WinForms.dll: 38 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/webview/lib/WebBrowserInterop.x64.dll: 7 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/webview/lib/WebBrowserInterop.x86.dll: 7 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/webview/lib/pywebview-android.jar: 13 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/webview/lib/runtimes/win-arm64/native/WebView2Loader.dll: 143 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/webview/lib/runtimes/win-x64/native/WebView2Loader.dll: 158 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/libs/webview/lib/runtimes/win-x86/native/WebView2Loader.dll: 119 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/libcrypto-3.dll: 5070 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/libffi-8.dll: 38 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/libssl-3.dll: 768 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/python.exe: 100 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/python3.dll: 65 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/python311.dll: 5664 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/python311.zip: 4185 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/pythonw.exe: 99 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/sqlite3.dll: 1504 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/vcruntime140.dll: 116 KiB without build provenance
- **medium** `binary_committed` — scripts/windows_worker/dist/python/vcruntime140_1.dll: 48 KiB without build provenance
- **medium** `generated_or_private_file_tracked` — server/crash.log: tracked; usually belongs in .gitignore
- **medium** `generated_or_private_file_tracked` — server/server.log: tracked; usually belongs in .gitignore
- **medium** `generated_or_private_file_tracked` — test_failures.log: tracked; usually belongs in .gitignore
- **medium** `generated_or_private_file_tracked` — test_output.log: tracked; usually belongs in .gitignore

## Supply (34)

- **low** `action_pinned_by_tag` — .github\workflows\courier-codex.yml:22: actions/checkout@v5
- **low** `action_pinned_by_tag` — .github\workflows\courier-codex.yml:57: actions/checkout@v5
- **low** `action_pinned_by_tag` — .github\workflows\courier-codex.yml:61: openai/codex-action@v1
- **low** `action_pinned_by_tag` — .github\workflows\courier-codex.yml:86: actions/checkout@v5
- **low** `action_pinned_by_tag` — .github\workflows\courier_motor.yml:26: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\courier_motor.yml:48: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\courier_motor.yml:53: actions/setup-python@v5
- **low** `action_pinned_by_tag` — .github\workflows\courier_worker.yml:27: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\courier_worker.yml:137: actions/upload-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\deploy-pages.yml:32: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\deploy-pages.yml:43: actions/configure-pages@v4
- **low** `action_pinned_by_tag` — .github\workflows\deploy-pages.yml:46: actions/upload-pages-artifact@v3
- **low** `action_pinned_by_tag` — .github\workflows\deploy-pages.yml:52: actions/deploy-pages@v4
- **low** `action_pinned_by_tag` — .github\workflows\deploy-static.yml:21: actions/checkout@v5
- **low** `action_pinned_by_tag` — .github\workflows\host-endurance-soak.yml:42: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\host-endurance-soak.yml:44: actions/setup-python@v5
- **low** `action_pinned_by_tag` — .github\workflows\host-endurance-soak.yml:65: actions/upload-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\host-endurance-soak.yml:79: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\host-endurance-soak.yml:81: actions/download-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\host-endurance-soak.yml:98: actions/upload-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:38: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:96: actions/upload-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:112: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:115: actions/download-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:124: actions/upload-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:138: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:141: actions/download-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:146: actions/download-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\revenue_v1_baseline.yml:200: actions/upload-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\v1-ci.yml:33: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\v1-ci.yml:35: actions/setup-python@v5
- **low** `action_pinned_by_tag` — .github\workflows\v1-ci.yml:78: actions/upload-artifact@v4
- **low** `action_pinned_by_tag` — .github\workflows\v1-ci.yml:100: actions/checkout@v4
- **low** `action_pinned_by_tag` — .github\workflows\v1-ci.yml:101: actions/setup-node@v4

## Workflows (12)

- **high** `ci_failed_env` — tests: Clean runner tests failed
- **medium** `timeout` — .github/workflows/courier-codex.yml: Missing timeout-minutes configuration.
- **medium** `concurrency` — .github/workflows/courier-codex.yml: Missing concurrency block.
- **medium** `mutation_risk` — .github/workflows/courier-codex.yml: git push detected in workflow.
- **medium** `mutation_risk` — .github/workflows/courier_motor.yml: git push detected in workflow.
- **medium** `timeout` — .github/workflows/courier_worker.yml: Missing timeout-minutes configuration.
- **medium** `timeout` — .github/workflows/deploy-pages.yml: Missing timeout-minutes configuration.
- **medium** `timeout` — .github/workflows/deploy-static.yml: Missing timeout-minutes configuration.
- **medium** `concurrency` — .github/workflows/deploy-static.yml: Missing concurrency block.
- **medium** `timeout` — .github/workflows/revenue_v1_baseline.yml: Missing timeout-minutes configuration.
- **medium** `concurrency` — .github/workflows/revenue_v1_baseline.yml: Missing concurrency block.
- **medium** `mutation_risk` — .github/workflows/revenue_v1_baseline.yml: git push detected in workflow.
