# MUSE_TURBO_M01 — A1_CONFINEMENT_FALSIFIER (Post-Codex/RUN-Paket)

- ROLE=M01, HOST=MAC, PROVIDER=MUSE, MODE=READ_ONLY_C2, LEDGER=FROZEN
- TIP=ae0030c8 (WINDOWS_CENTRAL_WRITER_FINAL_COMMIT_8), verified 2026-09-28
- CODEX=ABSENT (`ops/ai/live/CODEX_HIGH_RESULT_CURRENT.md` ENOENT; bridge `MUSE_BRIDGE_01_16_BLOCKED.md` = BLOCKED/GATE pending) → Post-Codex-Paket, keine Codex-Anpassung
- Methode: nur `git show`/`grep` am Tip, null Source-Edits, null Runs, null Suite (Testkörper als wiederverwendete Evidence gelesen, nicht re-exekutiert)
- Claimant: MUSE C2 (Shard 05 separat abgeschlossen; peer-held: MUSE_TURBO_06)

## F1 — Absoluter Artifact-Pfad escapet das Download-Verzeichnis

- CLAIM=Der GitHub-Adapter liest Evidence nur innerhalb von `directory`.
- SOURCE_TRUTH=`scripts/github_worker_adapter.py:75` `verify_result`: `evidence_file = directory / artifact.get("path", "")`, danach `is_file()` + `read_bytes()` ohne Guard (Tip-Read; kein `is_safe_artifact_name`-, kein `resolve`/`relative_to`-Gebrauch in der Datei).
- FALSE_GREEN_PATH=Result mit `"path": "/etc/hostname"` (o.ä.) + passender `sha256`: `Path("/dl") / "/etc/hostname"` → `/etc/hostname` (pathlib-Semantik); Hash stimmt bei bekanntem Inhalt → Evidence-Check PASST für eine Datei, die nie CI-Evidence war. Integrität reduziert sich auf "zeigt auf Bytes mit bekanntem Hash".
- INDEPENDENT_EVIDENCE=Tip-Codezeile oben + deterministische pathlib-Semantik (kein Test, keine Ausführung nötig); kein existierender Fingerprint deckt Adapter-Pfad-Confinement ab (G07-Lane ist test-only Identity, keine Traversal-Abdeckung).
- MINIMUM_FIX_OR_GUARD=`artifact.get("path")` mit `is_safe_artifact_name` (aus `scripts/artifact_store.py`) prüfen + `resolve().is_relative_to(directory.resolve())` vor `read_bytes`; sonst `ValueError`.
- MINIMUM_TEST=Result mit absolutem Pfad → `ValueError`; relativer legitimer Pfad → Pass (unverändert).
- DISPROVEN_OR_CONFIRMED=CONFIRMED (Confinement-Claim falsifiziert)

## F2 — `..`-Traversal escapet das Download-Verzeichnis

- CLAIM=wie F1.
- SOURCE_TRUTH=gleiche Zeile wie F1; keine Normalisierung vor dem Read.
- FALSE_GREEN_PATH=`"path": "../../<sibling>/<known-file>"` löst aus `directory` heraus auf; mit passendem `sha256` → PASS ohne echte Evidence.
- INDEPENDENT_EVIDENCE=Tip-Codezeile + Pfadauflösungs-Semantik; kein Gegen-Guard in Datei.
- MINIMUM_FIX_OR_GUARD=identisch F1 (ein Guard deckt F1+F2+F3 ab).
- MINIMUM_TEST=`..`-Pfad → `ValueError`.
- DISPROVEN_OR_CONFIRMED=CONFIRMED

## F3 — Drive-/UNC-Pfade (Windows-Host)

- CLAIM=wie F1, plattformübergreifend.
- SOURCE_TRUTH=gleiche Zeile; Adapter läuft auf Windows-Hosts (`powershell`/`taskkill`-Kontext der Worker-Linie), `Path("C:/...")` bzw. UNC nach `/`-Verknüpfung absolut.
- FALSE_GREEN_PATH=`"path": "C:/Windows/...bekannt"` + Hash → PASS ohne CI-Evidence.
- INDEPENDENT_EVIDENCE=Tip-Codezeile; `is_safe_artifact_name` (Artifact-Store) zeigt die im Repo bereits kanonische Abwehr (drive/root/`..`-Check) — im Adapter nicht verwendet.
- MINIMUM_FIX_OR_GUARD=identisch F1.
- MINIMUM_TEST=Drive-/UNC-Pfad → `ValueError`.
- DISPROVEN_OR_CONFIRMED=CONFIRMED (gleiche Wurzel wie F1/F2; ein Fix)

## F4 — `path: null` crasht statt fail-closed (Robustheit, kein Bypass)

- CLAIM=Fehlgeformte Pfade werden sauber als `ValueError` abgewiesen.
- SOURCE_TRUTH=`artifact.get("path", "")` liefert `None` bei explizitem null → `directory / None` → `TypeError`, nicht `ValueError`; Caller `run()` (Z.161) fängt nur Ablauf-Fehlerklassen implizit — `TypeError` entweicht als Crash statt kontrolliertem Reject.
- FALSE_GREEN_PATH=kein falsches PASS (fail-closed per Crash), aber falscher Fehlertyp + kein sauberer State-Pfad.
- INDEPENDENT_EVIDENCE=Tip-Codezeilen 75 + 161.
- MINIMUM_FIX_OR_GUARD=`isinstance(path, str)`-Check → `ValueError` (fällt aus demselben Guard wie F1).
- MINIMUM_TEST=`path: null` / numerisch → `ValueError`, kein `TypeError`.
- DISPROVEN_OR_CONFIRMED=CONFIRMED (minor)

## F5 — Kein Confinement-Guard im Adapter vorhanden (Negativ-Nachweis)

- CLAIM=Ein übersehener Guard könnte F1–F4 bereits abfangen.
- SOURCE_TRUTH=`grep` am Tip: null Treffer für `is_safe_artifact_name|resolve|relative_to` in `scripts/github_worker_adapter.py`; einziger `verify_result`-Caller ist `run()` Z.161 ohne vorgeschaltete Pfadprüfung.
- FALSE_GREEN_PATH=n/a (stellt sicher, dass F1–F4 keine toten Befunde sind).
- INDEPENDENT_EVIDENCE=Negativ-Grep am Tip-SHA.
- MINIMUM_FIX_OR_GUARD=n/a.
- MINIMUM_TEST=n/a.
- DISPROVEN_OR_CONFIRMED=CONFIRMED (kein Guard vorhanden)

## F6 — Leerstring-Pfad bleibt fail-closed (Gegen-Pin, kein Defect)

- CLAIM=Auch degenerierte Pfade dürfen kein falsches PASS erzeugen.
- SOURCE_TRUTH=`directory / ""` → `directory` selbst → `is_file()` False → `ValueError` ("evidence artifact hash does not match").
- FALSE_GREEN_PATH=keiner.
- INDEPENDENT_EVIDENCE=Tip-Codezeile + `is_file`-Semantik für Verzeichnisse.
- MINIMUM_FIX_OR_GUARD=keiner.
- MINIMUM_TEST=bestehendes Verhalten; optionaler Pin-Test `""` → `ValueError`.
- DISPROVEN_OR_CONFIRMED=DISPROVEN (als Defect widerlegt — Verhalten korrekt)

## Abschluss

- CONFIRMED=F1, F2, F3 (eine Wurzel: ungeprüfter `directory / worker_path`-Join → falsifizierter Confinement-Claim), F4 (minor, `TypeError` statt `ValueError`), F5 (Negativ-Nachweis)
- DISPROVEN=F6 (Leerstring fail-closed, korrekt)
- MISSING_EVIDENCE=keine Code-Evidence offen; physischer Exploit-Proof untersagt (kein RUN) und für den Guard-Entscheid nicht nötig — pathlib-Semantik + Tip-Zeile sind deterministisch
- OWNER_PACKET=WINDOWS_CENTRAL_WRITER (Tip-Owner; ein Guard + zwei Tests; G07-Identity-Lane unberührt lassen)
- BEFORE_RUN1=F1/F2/F3 (Adapter liest hostfremde Bytes mit echten Creds auf dem Runner vor RUN_1 schließen)
- BEFORE_RUN2=(leer)
- BEFORE_FREEZE=F4
- DEFER=(leer — kein Ledger/Canary/Gate-Anteil)
- DO_NOT_REPEAT=M01 vs ae0030c8 (F1–F6); Shard-05-Paket steht separat; MUSE_TURBO_06 peer-owned
