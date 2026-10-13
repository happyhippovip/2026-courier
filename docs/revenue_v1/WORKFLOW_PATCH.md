# Workflow-Patch für revenue_v1_baseline.yml (nicht angewendet)

Grund: Ein Push mit Änderung an `.github/workflows/` wurde abgelehnt, weil dem verwendeten Token der `workflow`-Scope fehlt. Die Workflow-Datei ist in diesem Branch unverändert (Stand 481fd0ba). Der frühere Commit mit Workflow-Änderung liegt lokal im Backup-Branch `revenue-v1-with-workflow` (a4d58ed8).

Inhalt:
1. Zeile 23: Beispieltext `USD 500.00` → `EUR 99.00` (Preis Revenue V1).
2. Upload der Worker-Artefakte um `work_dir/report_de.md` ergänzen. **Pflicht** seit dem unabhängigen Verifier: fehlt `report_de.md` im Verifier-/Handoff-Job, ergibt der Verifier fail-closed `FAIL`.
3. `PyYAML==6.0.3` vor Worker, Verifier **und** Handoff installieren. Der Handoff-Job ruft beim `reconcile` erneut den unabhängigen Verifier auf. Ohne PyYAML in einem Job weichen die `parse_modes` (yaml/text) ab → `MISMATCH`.
   Hinweis (nicht geprüft): Ob `pip install` mit dem System-`python3` auf `ubuntu-latest` ohne `--break-system-packages` erlaubt ist (PEP 668), ist ungeprüft; daher der Fallback. Alternative: `actions/setup-python` vorschalten.
4. Der unabhängige Verifier selbst braucht keine Workflow-Änderung: `revenue_v1_safety_baseline.py verify` und `reconcile` starten ihn bereits als eigenen Prozess (`scripts/revenue_v1_independent_verifier.py`). Er holt den Commit selbst von `https://github.com/<owner>/<repo>.git` (Netzwerk im Verifier-Job nötig; ist bei GitHub-Runnern gegeben).

## Anwenden (nur durch jemanden mit `workflow`-Scope bzw. über die GitHub-Weboberfläche)
```bash
sed -n "/^```diff$/,/^```$/p" docs/revenue_v1/WORKFLOW_PATCH.md | sed "1d;\$d" > /tmp/wf.diff && git apply /tmp/wf.diff
git add .github/workflows/revenue_v1_baseline.yml
git commit -m "ci(revenue-v1): EUR 99.00 example, upload report_de.md, install PyYAML"
```
Geprüft am 13.10.2026: `git apply --check` läuft auf diesem Stand sauber (auch nach Extraktion aus dieser Datei).

## Unified diff
```diff
--- a/.github/workflows/revenue_v1_baseline.yml
+++ b/.github/workflows/revenue_v1_baseline.yml
@@ -20,7 +20,7 @@
         required: true
         type: string
       price_currency:
-        description: 'Agreed Price and Currency (e.g. USD 500.00)'
+        description: 'Agreed Price and Currency (e.g. EUR 99.00)'
         required: true
         type: string
       delivery_destination:
@@ -88,6 +88,9 @@
               "human_minutes": 0
             }' > task.json
           
+      - name: Install PyYAML
+        run: python3 -m pip install --user PyYAML==6.0.3 || python3 -m pip install --user --break-system-packages PyYAML==6.0.3
+
       - name: Execute Revenue V1 Worker
         run: |
           python3 scripts/revenue_v1_safety_baseline.py worker task.json work_dir > result.json
@@ -100,6 +103,7 @@
             task.json
             work_dir/report.json
             work_dir/report.md
+            work_dir/report_de.md
             result.json
 
   verifier:
@@ -116,6 +120,9 @@
         with:
           name: worker-artifacts
           
+      - name: Install PyYAML
+        run: python3 -m pip install --user PyYAML==6.0.3 || python3 -m pip install --user --break-system-packages PyYAML==6.0.3
+
       - name: Execute Independent Verifier
         run: |
           python3 scripts/revenue_v1_safety_baseline.py verify task.json work_dir result.json > verified.json
@@ -147,6 +154,9 @@
         with:
           name: verified-artifacts
           
+      - name: Install PyYAML
+        run: python3 -m pip install --user PyYAML==6.0.3 || python3 -m pip install --user --break-system-packages PyYAML==6.0.3
+
       - name: Create PR and Handoff
         env:
           GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```
