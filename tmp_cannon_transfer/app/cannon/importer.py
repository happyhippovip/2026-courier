"""Streaming import receipts, not a second task queue or execution authority."""
import json
import os
import shutil
from pathlib import Path
from .storage import InstanceLock, atomic, digest, file_hash, owned, read

MAX_LINE = 65536


class Importer:
    def __init__(self, directory):
        self.root = owned(directory)

    def ingest(self, source, import_id=None, limit=256):
        if not 1 <= limit <= 1000:
            raise ValueError('Import window must be 1..1000 records')
        source = Path(source)
        content_hash = file_hash(source)
        import_id = import_id or content_hash
        folder = self.root / 'imports' / digest(import_id)
        with InstanceLock(self.root):
            checkpoint = read(folder / 'cursor.json')
            if checkpoint and checkpoint['source_sha256'] != content_hash:
                raise ValueError('IMPORT_ID_CONTENT_CONFLICT')
            if not checkpoint:
                folder.mkdir(parents=True, exist_ok=True)
                original = folder / 'original.bin'
                with source.open('rb') as src, original.open('wb') as dst:
                    shutil.copyfileobj(src, dst, 65536); dst.flush(); os.fsync(dst.fileno())
                if file_hash(original) != content_hash:
                    raise ValueError('SOURCE_CHANGED_DURING_IMPORT')
                checkpoint = dict(import_id=import_id, source_sha256=content_hash, offset=0,
                                  line=0, imported=0, reused=0, conflicts=0, invalid=0, eof=False,
                                  format='jsonl' if source.suffix.lower() == '.jsonl' else 'txt')
                atomic(folder / 'cursor.json', checkpoint)
            if checkpoint['eof']:
                return checkpoint
            # Never execute text or infer authorization from imported flags.
            with (folder / 'original.bin').open('rb') as stream:
                stream.seek(checkpoint['offset'])
                for _ in range(limit):
                    raw = stream.readline(MAX_LINE + 1)
                    if not raw:
                        checkpoint['eof'] = True; break
                    if len(raw) > MAX_LINE:
                        raise ValueError('RECORD_TOO_LARGE_AT_BYTE_' + str(checkpoint['offset']))
                    line = checkpoint['line'] + 1
                    try:
                        text = raw.decode('utf-8-sig' if line == 1 else 'utf-8').rstrip('\r\n')
                        record = json.loads(text) if checkpoint['format'] == 'jsonl' else {'kind': 'NOTE', 'text': text}
                        if not isinstance(record, dict):
                            raise ValueError('Record must be an object')
                        rid = record.get('id', f'{import_id}:{line}')
                        if not isinstance(rid, str) or not rid or len(rid) > 256:
                            raise ValueError('Invalid record id')
                        receipt_path = self.root / 'receipts' / (digest(rid) + '.json')
                        old = read(receipt_path)
                        fingerprint = digest(record)
                        if old and old['fingerprint'] != fingerprint:
                            checkpoint['conflicts'] += 1
                            atomic(folder / f'conflict-{line}.json', {'id': rid, 'old': old['fingerprint'], 'new': fingerprint})
                        elif old:
                            # A crash after receipt persistence but before cursor persistence
                            # is a replay, not a second logical import.
                            checkpoint['reused'] += 1
                        else:
                            atomic(receipt_path, {'id': rid, 'record': record, 'fingerprint': fingerprint,
                                                  'source_import': import_id, 'line': line,
                                                  'execution_authorized': False})
                            checkpoint['imported'] += 1
                    except (ValueError, UnicodeError) as exc:
                        checkpoint['invalid'] += 1
                        atomic(folder / f'invalid-{line}.json', {'line': line, 'reason': str(exc)[:200]})
                    checkpoint.update(offset=stream.tell(), line=line)
                    atomic(folder / 'cursor.json', checkpoint)
            atomic(folder / 'cursor.json', checkpoint)
            return checkpoint

    def submit_authorized(self, selections, core, request_id):
        """Explicit user selections bind exact content; notes cannot auto-run.

        Bounded one-goal admission uses Courier's canonical idempotency key.
        A pending receipt stays pending on transport uncertainty and is replayed
        with that same key. No local DONE or task graph is manufactured.
        """
        if not 1 <= len(selections) <= 100:
            raise ValueError('Select 1..100 task records')
        with InstanceLock(self.root):
            steps = []
            for rid, approved_fingerprint in selections:
                item = read(self.root / 'receipts' / (digest(rid) + '.json'))
                if not item or item['fingerprint'] != approved_fingerprint or item['record'].get('kind') != 'TASK':
                    raise ValueError(f'EXPLICIT_CURRENT_TASK_AUTHORIZATION_REQUIRED: item={item} approved={approved_fingerprint}')
                task = item['record'].get('task')
                if not isinstance(task, dict) or not isinstance(task.get('instruction'), str):
                    raise ValueError('Missing canonical task instruction')
                steps.append(task)
            payload = {'goal_text': 'Cannon: explicitly selected bounded work', 'terminal': True,
                       'workflow_plan': steps, 'client_request_id': 'cannon-' + request_id}
            path = self.root / 'admissions' / (digest(request_id) + '.json')
            prior = read(path)
            if prior and prior['fingerprint'] != digest(payload):
                raise ValueError('ADMISSION_CONTENT_CONFLICT')
            if prior and prior.get('goal_id'):
                return prior
            receipt = {'fingerprint': digest(payload), 'state': 'PENDING', 'request_id': request_id}
            atomic(path, receipt)
            response = core.request('POST', '/goals', payload)
            if not response.get('goal_id'):
                raise ValueError('Canonical intake did not return goal_id')
            receipt.update(state='SUBMITTED', goal_id=response['goal_id'])
            atomic(path, receipt)
            return receipt
