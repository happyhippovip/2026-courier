# LANE 30 — Physical Result Identity Tuple (READ_ONLY)

DATE=2026-09-28. HEAD=34b0a42 (re-verifiziert). Kein RUN, kein Edit.

## Angriff -> erforderliches Identitaetselement (jeweils Code-Beleg)

1. STALE_ARTIFACT_REUSE (Artifact aus Dispatch X in Dispatch Y referenziert):
   Ref muss `artifact_id` tragen, Record-Bindung ueber
   (goal,task,attempt,dispatch,worker)+name+sha; Server prueft
   `check_reference` (artifact_store.py:133-144), Verifier `verify_uploaded_artifact`
   (:147-159). STATUS=PRESENT (3 Schichten: Upload :184-191, Result :377-379, Verify).
2. WRONG_ATTEMPT (attempt:1-Result nach attempt:2-Dispatch): Result muss
   attempt_id+dispatch_id tragen, Server exakter Match (contract.py:138-140);
   Retry mintet frische IDs (app.py:327-331). STATUS=PRESENT.
3. WRONG_WORKER (Worker B postet fuer A): worker_id exakter Match + Holder-Check
   (app.py:372, contract :138-140); Save nur im Match-Zweig (:410). STATUS=PRESENT
   (Key-Besitz vorausgesetzt; geteilte Keys ausserhalb Threat-Modell).
4. WRONG_TASK (Result an falschen Task): task_id+goal_id exakter Match
   (contract :138-140). STATUS=PRESENT.
5. WRONG_RUN (zwei Executions, ein Dispatch; PID-Reuse ueber Zeit/Hosts):
   run_id ist HEUTE `str(pid)` mit Fallback `"win-native"` (daemon.py:207,216) —
   weder zeit- noch host-eindeutig; Server prueft nur non-empty (contract :141-143).
   ERFORDERLICH: run_ref=(machine_id, pid, process_start_time); Server muss
   zweiten distinkten run_ref pro Dispatch abweisen (oder an first-seen binden).
   STATUS=GAP (Daemon-Seite verhindert Recompute via RESULT_READY :140,336 —
   Server-Seite blind).
6. WRONG_BRANCH_RUNTIME (Result aus anderem Code/anderer Runtime): HEUTE NICHTS —
   kein Feld, kein Check. ERFORDERLICH: source_sha (Kandidaten-SHA des Workers)
   + runtime_class (Toolchain/Host-Klasse); Server/Verifier vergleichen gegen
   akzeptierten Kandidaten. STATUS=GAP (groesste Luecke dieser Lane).

## Kanonisches Tupel (minimal, unabhaengig)

RESULT_IDENTITY = (
  goal_id, task_id, attempt_id, dispatch_id, worker_id,
  run_ref=(machine_id, pid, process_start_time),
  result_id,
  source_sha, runtime_class,
  artifacts=[{path, sha256, size, artifact_id}]
)
mit artifact_id = server-issue ueber
(binding{goal,task,attempt,dispatch,worker}, name, sha256).

## Unabhaengigkeits-Nachweis (Drop-Test)

- Ohne attempt/dispatch -> 2 gelingt (stale attempt bindet).
- Ohne worker_id -> 3 gelingt (fremder Poster).
- Ohne task/goal -> 4 gelingt (Task-Verwechslung).
- Ohne run_ref -> 5 gelingt (zweite Execution unsichtbar).
- Ohne source_sha/runtime -> 6 gelingt (falscher Code unsichtbar).
- Ohne artifact_id-Bindung -> 1 gelingt (stale Blob-Referenz).
Jedes Element besiegt genau einen Angriff; keines ist aus den anderen ableitbar.

## Uebergabe
- PRESENT (4/6): 1,2,3,4 — Code-Pfade total, kein Fix.
- GAP (2/6): 5 (run_ref serverseitig), 6 (source_sha/runtime_class).
  Beides braucht Owner-Entscheid (Feld + Pruefort), kein Ad-hoc-Patch.
  Bis dahin: physikalische Witnesse muessen Run/Quelle ausserhalb der
  Identitaet belegen (Prozess-Log, Worktree-SHA) — vgl. Lane 33/34.
