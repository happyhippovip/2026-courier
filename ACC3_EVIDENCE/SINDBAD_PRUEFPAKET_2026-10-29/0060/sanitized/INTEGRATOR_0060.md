# WK-PRUEFER-003/012 Integrator RC-0060 – VERIFIED (3+3 passed), mit Hinweis
29.10.2026 MEZ · Courier Prüfer · read-only · Kopien unter /tmp · SPEND=0

- PYTEST_0060_a209b3fe.log 6a7945c372abd6ba0ae4d9ce38430dc8264f3991b26e3c02484f535e78478df4
- PYTEST_0060_9afe8706.log 64478c4d6320cebfdaa10fb78a7d9bfde044d4a93c19e52246a663c9366ee59c
- ERGEBNISSE/INTEGRATOR/SHA256SUMS a1935879bb2685ee43a15ed9954ea8e8d0e88e646b00ad9a252bf521c09d4949: `sha256sum -c` alle OK (listet PR_STACK-Dateien, nicht die zwei Logs).
- Tree nachgebaut: Worktree 26ee2348 + EC1→E0→E0b→E0-Tests→E0v2→EC1v2 (6/6 apply) → write-tree **a209b3fec444cc3af7d02f153c696d57991ae9d0**, Diff-sha c6f89a83… ✔; + PR2b-Patch → **9afe8706ee94bbd554efdbff5dc4666a0bf19f64** ✔.
- tests/test_gate2_two_workkeys.py selbst: a209b3fe **3 passed**, 9afe8706 **3 passed**.
- Hinweis (nicht grün im Log): tests/hub a209b3fe 15 failed/128 passed, 9afe8706 3 failed/145 passed (u. a. test_kolibri_view, auch auf Trunk bekannt). „3 passed“ gilt nur für gate2, nicht für RC-0060 gesamt.
