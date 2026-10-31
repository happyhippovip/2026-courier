# WK-INTEGRATOR-006 – Integrationstest CP-1..CP-5 lokal (Dry-Run), 29.10.2026 18:53–18:55 MEZ
Tree 481eabda53881c9f90429fad7f8531ce98e1eca2 = 9afe8706 (PR 2 + 2b) + CP1, CP2, CP3, CP4, CP5A, CP5B, CP5_CRED aus PIPELINE_RECOVERY_2026-10-29 (alle `git apply --check` OK, SUMS der Ordner OK). Nur die mitgelieferten Tests (gemockt bzw. Dry-Run, Socket in CP5-Tests blockiert), kein echter Render, kein Upload, kein Netz-Write.

| Datei | passed/failed/errors/skipped |
|---|---|
| test_render_godot_movie.py (CP1) | 13/0/0/0 |
| test_media_verify.py (CP2, ffmpeg lokal) | 14/0/0/0 |
| test_run_content_production_pipeline.py (CP3) | 35/0/0/0 |
| test_content_missions.py (CP4) | 9/0/0/0 |
| test_ledger_engine.py (CP4-Regression) | 62/0/0/0 |
| test_publish_youtube.py + test_youtube_dryrun.py (CP5A) | 6+6/0/0/0 |
| test_publish_tiktok_inbox.py (CP5B) | 9/0/0/0 |
| test_credential_ref.py (CP5_CRED) | 12/0/0/0 |
| test_ledger_v1_bridge.py, test_serve.py (RC-0060) | 40, 24/0/0/0 |
| tests/hub/test_hub_product.py | 65/**2**/0/0 |
| **Summe** | **295 / 2 / 0 / 0** |

Die 2 Fehlschläge sind dieselben PR-2b-Probleme wie in PYTEST_0060.log (offline-vs-Token-Reihenfolge, Test-Proxy ohne Resolve-Header), nicht CP-bedingt. Akzeptanz „passed“ damit **nicht** erfüllt. Pipeline-Stufen CP1–CP5 untereinander: keine Fehlschläge.
