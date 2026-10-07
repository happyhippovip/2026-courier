# Mac Exact-Binding Inputs (RUN_1 / RUN_2)

## Environment / Config
BINDING_FIELD=COURIER_SERVER
SOURCE=run_1_mac.sh (python3 -m server.app --port=8080)
CURRENTLY_BINDABLE=YES (http://127.0.0.1:8080)
CANDIDATE_SENSITIVE=NO
MISSING=None
RETEST_TRIGGER=Port or server launch failure

BINDING_FIELD=COURIER_API_KEY
SOURCE=Environment
CURRENTLY_BINDABLE=YES (Provided by Mac Worker host)
CANDIDATE_SENSITIVE=NO
MISSING=None
RETEST_TRIGGER=Auth Failure

## Repositories / Filesystem
BINDING_FIELD=repo_root
SOURCE=Mac worker filesystem
CURRENTLY_BINDABLE=YES (/Users/user/Downloads/2026-courier)
CANDIDATE_SENSITIVE=NO
MISSING=None
RETEST_TRIGGER=Path change

BINDING_FIELD=source_ref
SOURCE=git
CURRENTLY_BINDABLE=YES (FINAL_SHA: 3c2aa5160002bdb7e2647ab87a0cef2a6f2a3ec4)
CANDIDATE_SENSITIVE=YES
MISSING=None
RETEST_TRIGGER=New candidate SHA

## Processes
BINDING_FIELD=server_process
SOURCE=python3 -m server.app
CURRENTLY_BINDABLE=YES (PID tracked in logs/server.pid)
CANDIDATE_SENSITIVE=YES
MISSING=None
RETEST_TRIGGER=PID conflict

BINDING_FIELD=worker_process
SOURCE=python3 -m scripts.integration_contract
CURRENTLY_BINDABLE=YES (Logs to logs/worker_run1.log)
CANDIDATE_SENSITIVE=YES
MISSING=None
RETEST_TRIGGER=Process crash

BINDING_FIELD=verifier_process
SOURCE=python3 -m scripts.courier_verifier --target=A
CURRENTLY_BINDABLE=YES
CANDIDATE_SENSITIVE=YES
MISSING=None
RETEST_TRIGGER=Process crash
