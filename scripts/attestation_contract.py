"""Server-owned verification receipts; no caller identity is an authority."""
import hashlib
import json
import re
import time

MAX_AGE = 172800
CHAIN = ('goal_id', 'task_id', 'attempt_id', 'dispatch_id', 'execution_ref')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def principal(key):
    return 'principal_' + hashlib.sha256(('Bearer ' + key).encode()).hexdigest()


def current_receipt(receipt, task, goal, binding, producer, verifier, now=None):
    """Revalidate persisted authority and content on every use, including replay."""
    now = time.time() if now is None else now
    if not isinstance(receipt, dict) or not producer or not verifier or producer == verifier:
        return False
    try:
        result = task['result']
        verification = task['verification']
        return bool(
            receipt['producer_principal'] == producer == task['producer_principal']
            and receipt['verifier_principal'] == verifier == verification['verifier_principal']
            and receipt['binding'] == binding == task['server_binding']
            and re.fullmatch(r'[0-9a-f]{40}', binding['sha'])
            and re.fullmatch(r'courier-server:[0-9a-f]{32}', binding['runtime'])
            and all(receipt[k] == task[k] == result[k] for k in CHAIN)
            and receipt['result_id'] == result['result_id'] == verification['result_id']
            and receipt['result_sha256'] == fingerprint(result)
            and receipt['artifacts'] == result['artifacts'] == verification['artifacts']
            and bool(receipt['artifacts'])
            and receipt['verdict'] == verification['verdict'] == 'PASS'
            and task['status'] == 'RECONCILED' and goal['status'] == 'DONE'
            and receipt['received_at'] == task['result_received_at']
            and receipt['verified_at'] == verification['verified_at']
            and 0 <= now - receipt['received_at'] <= MAX_AGE
            and receipt['received_at'] <= receipt['verified_at'] <= now
        )
    except (KeyError, TypeError, ValueError):
        return False
