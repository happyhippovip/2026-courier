# Workflow-Patch (nicht angewendet) – revenue_v1_baseline.yml + courier_motor.yml

Grund: Pushes mit Änderungen an `.github/workflows/` werden abgelehnt, weil dem verwendeten Token der `workflow`-Scope fehlt. Beide Workflow-Dateien sind in diesem Branch unverändert. Anwenden muss jemand mit `workflow`-Scope (oder über den GitHub-Editor).

## Inhalt
**revenue_v1_baseline.yml**
1. Zeile 23: Beispieltext → `EUR 99 (Einführungspreis, nicht validiert)`. Der Preis ist intern festgelegt, aber nicht durch einen zahlenden Kunden validiert.
2. Upload der Worker-Artefakte um `work_dir/report_de.md` ergänzen. **Pflicht**: ohne diese Datei ergibt der unabhängige Verifier fail-closed `FAIL`.
3. In worker-, verifier- und handoff-Job: `actions/setup-python` gepinnt auf `5fda3b95a4ea91299a34e894583c3862153e4b97` (v7.0.0, per `gh api repos/actions/setup-python/git/ref/tags/v7.0.0` ermittelt), Python 3.12, danach `python -m pip install PyYAML==6.0.3`. Alle drei Jobs brauchen denselben Parser, sonst weichen die `parse_modes` ab → `MISMATCH` (der handoff-Job ruft beim `reconcile` erneut den Verifier auf). Die Aufrufe nutzen danach `python` (setup-python) statt `python3`.
4. In verifier- und handoff-Job: den unabhängigen Verifier **gepinnt aus `integration/v1`** holen (`git fetch --depth=1 origin integration/v1` + `git show FETCH_HEAD:scripts/revenue_v1_independent_verifier.py` in `$RUNNER_TEMP`) und über `REVENUE_V1_INDEPENDENT_VERIFIER` an `revenue_v1_safety_baseline.py` übergeben (Unterstützung dafür ist in `scripts/revenue_v1_safety_baseline.py`, `independent_verifier_path()`, schon enthalten). Damit kann ein PR den Verifier, der ihn prüft, nicht selbst verändern. Commit und sha256 des verwendeten Verifiers werden im Log ausgegeben; sha256 und Version stehen zusätzlich in `verified.json` (`independent_verifier`).

   **Wichtig:** Das funktioniert erst, wenn `scripts/revenue_v1_independent_verifier.py` in `integration/v1` liegt. Stand 13.10.2026: `origin/integration/v1` = `5b2a8c194afb4ea70316a766f0201a13d58ba94f`, Datei dort **nicht vorhanden** → der Schritt würde mit `git show`-Fehler abbrechen (fail-closed, kein PASS). Reihenfolge daher: Verifier zuerst nach `integration/v1` mergen, dann diesen Patch anwenden.

**courier_motor.yml** (Ursache der roten Push-Runs, siehe unten)
5. Die fehlende Zeile `on:` wieder einfügen. Commit `a3a77c7e6` („ci(motor): stop auto-reconcile commits …“, #57) hat `on:` zusammen mit dem `push`-Trigger gelöscht; seitdem ist die Datei ungültiges YAML (`expected <block end>, but found '<block mapping start>'`, Zeile 6). GitHub legt dann bei jedem Push einen fehlgeschlagenen Run ohne Jobs an. Nach dem Fix bleibt nur `workflow_dispatch`, so wie es der Kommentar beabsichtigt; Push-Runs entstehen dann nicht mehr.

## Anwenden
```bash
sed -n "/^```diff$/,/^```$/p" docs/revenue_v1/WORKFLOW_PATCH.md | sed "1d;\$d" > /tmp/wf.diff && git apply /tmp/wf.diff
git add .github/workflows/revenue_v1_baseline.yml .github/workflows/courier_motor.yml
git commit -m "ci: fix courier_motor on: key; revenue-v1 pinned python+PyYAML, report_de.md upload, pinned verifier"
```
Geprüft am 13.10.2026: `git apply --check` läuft auf diesem Stand sauber (auch nach Extraktion aus dieser Datei); beide Zieldateien parsen mit PyYAML (Trigger je `workflow_dispatch`).

## Unified diff
```diff
--- a/.github/workflows/courier_motor.yml
+++ b/.github/workflows/courier_motor.yml
@@ -1,5 +1,6 @@
 name: Courier Motor
 
+on:
   # Runtime state must never be committed to git. The 5-minute cron and the
   # commit/push of server/state/central_state.json are disabled; the motor can
   # still be run manually for diagnostics, but it no longer persists state.
--- a/.github/workflows/revenue_v1_baseline.yml
+++ b/.github/workflows/revenue_v1_baseline.yml
@@ -20,7 +20,7 @@
         required: true
         type: string
       price_currency:
-        description: 'Agreed Price and Currency (e.g. USD 500.00)'
+        description: 'Agreed Price and Currency (e.g. EUR 99 (Einführungspreis, nicht validiert))'
         required: true
         type: string
       delivery_destination:
@@ -88,9 +88,17 @@
               "human_minutes": 0
             }' > task.json
           
+      - name: Set up Python (pinned)
+        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
+        with:
+          python-version: "3.12"
+
+      - name: Install PyYAML
+        run: python -m pip install PyYAML==6.0.3
+
       - name: Execute Revenue V1 Worker
         run: |
-          python3 scripts/revenue_v1_safety_baseline.py worker task.json work_dir > result.json
+          python scripts/revenue_v1_safety_baseline.py worker task.json work_dir > result.json
           
       - name: Upload Worker Artifacts
         uses: actions/upload-artifact@v4
@@ -100,6 +108,7 @@
             task.json
             work_dir/report.json
             work_dir/report.md
+            work_dir/report_de.md
             result.json
 
   verifier:
@@ -116,9 +125,25 @@
         with:
           name: worker-artifacts
           
+      - name: Set up Python (pinned)
+        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
+        with:
+          python-version: "3.12"
+
+      - name: Install PyYAML
+        run: python -m pip install PyYAML==6.0.3
+
+      - name: Fetch pinned independent verifier from integration/v1
+        # Requires scripts/revenue_v1_independent_verifier.py to exist on integration/v1.
+        run: |
+          git fetch --depth=1 origin integration/v1
+          git show FETCH_HEAD:scripts/revenue_v1_independent_verifier.py > "$RUNNER_TEMP/revenue_v1_independent_verifier.py"
+          echo "REVENUE_V1_INDEPENDENT_VERIFIER=$RUNNER_TEMP/revenue_v1_independent_verifier.py" >> "$GITHUB_ENV"
+          echo "Pinned verifier from integration/v1 @ $(git rev-parse FETCH_HEAD), sha256 $(sha256sum "$RUNNER_TEMP/revenue_v1_independent_verifier.py" | cut -d' ' -f1)"
+
       - name: Execute Independent Verifier
         run: |
-          python3 scripts/revenue_v1_safety_baseline.py verify task.json work_dir result.json > verified.json
+          python scripts/revenue_v1_safety_baseline.py verify task.json work_dir result.json > verified.json
           
       - name: Upload Verified Result
         uses: actions/upload-artifact@v4
@@ -147,6 +172,22 @@
         with:
           name: verified-artifacts
           
+      - name: Set up Python (pinned)
+        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
+        with:
+          python-version: "3.12"
+
+      - name: Install PyYAML
+        run: python -m pip install PyYAML==6.0.3
+
+      - name: Fetch pinned independent verifier from integration/v1
+        # Requires scripts/revenue_v1_independent_verifier.py to exist on integration/v1.
+        run: |
+          git fetch --depth=1 origin integration/v1
+          git show FETCH_HEAD:scripts/revenue_v1_independent_verifier.py > "$RUNNER_TEMP/revenue_v1_independent_verifier.py"
+          echo "REVENUE_V1_INDEPENDENT_VERIFIER=$RUNNER_TEMP/revenue_v1_independent_verifier.py" >> "$GITHUB_ENV"
+          echo "Pinned verifier from integration/v1 @ $(git rev-parse FETCH_HEAD), sha256 $(sha256sum "$RUNNER_TEMP/revenue_v1_independent_verifier.py" | cut -d' ' -f1)"
+
       - name: Create PR and Handoff
         env:
           GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
@@ -191,7 +232,7 @@
           HANDOFFEOF
           
           # 5. Run Reconciler
-          python3 scripts/revenue_v1_safety_baseline.py reconcile task.json work_dir verified.json handoff.json "$PR_NUMBER" "$PROPOSAL_HEAD" "main" > reconciliation.json
+          python scripts/revenue_v1_safety_baseline.py reconcile task.json work_dir verified.json handoff.json "$PR_NUMBER" "$PROPOSAL_HEAD" "main" > reconciliation.json
           
           # 6. Output for artifacts
           cat reconciliation.json
```
