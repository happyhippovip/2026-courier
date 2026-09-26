# TASK_18: Trace: Worker Selection -> Dispatch

STATUS=DONE
NEW_EVIDENCE=Trace server/app.py:330-345. Server generates uuid dispatch_id, creates attempt_id f'{task_id}:attempt:{attempts}', sets task['status'] = 'DISPATCHED', marks worker unavailable.
PROVEN=Dispatch mints fresh dispatch_id and binds worker exclusively.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_19
