#!/usr/bin/env python3
"""
Courier External Worker Bootstrap
Run this on any Windows or Mac machine to attach to the Courier Server.
"""
import os
import sys
import time
import json
import logging
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

# Config
SERVER_URL = os.environ.get('COURIER_SERVER_URL')
WORKER_TOKEN = os.environ.get('COURIER_WORKER_TOKEN')
WORKER_ID = os.environ.get('COURIER_WORKER_ID', 'anonymous-worker')
CAPABILITIES = os.environ.get('COURIER_CAPABILITIES', 'generic').split(',')
STATE_DIR = Path(os.environ.get('COURIER_WORKER_STATE', Path.home() / '.courier_worker'))

# Setup bounded logging
STATE_DIR.mkdir(parents=True, exist_ok=True)
log_file = STATE_DIR / 'worker.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=3) if hasattr(logging, 'handlers') else logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('worker')

if not SERVER_URL or not WORKER_TOKEN:
    logger.error('Missing COURIER_SERVER_URL or COURIER_WORKER_TOKEN')
    sys.exit(1)

def http_post(endpoint, data):
    req = urllib.request.Request(
        f"{SERVER_URL.rstrip('/')}/{endpoint}",
        data=json.dumps(data).encode('utf-8'),
        headers={'Authorization': f'Bearer {WORKER_TOKEN}', 'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))

def poll_for_task():
    try:
        return http_post('api/v1/worker/poll', {'worker_id': WORKER_ID, 'capabilities': CAPABILITIES})
    except urllib.error.HTTPError as e:
        if e.code != 404:  # 404 means no tasks
            logger.warning(f'Server HTTP {e.code}: {e.reason}')
    except Exception as e:
        logger.error(f'Connection failed: {e}')
    return None

def execute_task(task):
    task_id = task.get('task_id', 'unknown')
    instruction = task.get('instruction', '')
    logger.info(f'Executing task {task_id}: {instruction}')
    
    model_path = os.environ.get('COURIER_LOCAL_AI_MODEL', r'C:\Users\lol\local_ai\qwen2.5-1.5b.gguf')
    llama_cli = os.environ.get('COURIER_LLAMA_CLI', r'C:\Users\lol\local_ai\llama-cli.exe')
    
    if not os.path.exists(model_path) or not os.path.exists(llama_cli):
        return {
            'schema_version': '2.0',
            'task_id': task_id,
            'source': WORKER_ID,
            'payload': {'verdict': 'FAIL', 'message': 'Local AI executable or model not found'}
        }
        
    try:
        # Prompt engineering for deterministic JSON
        prompt = f"Respond ONLY in valid JSON. Instruction: {instruction}\n{{\"status\": \"ok\", \"response\": \""
        
        cmd = [
            llama_cli,
            "-m", model_path,
            "-p", prompt,
            "-n", "128",
            "--no-display-prompt"
        ]
        
        logger.info(f'Running local AI: {" ".join(cmd)}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            logger.error(f'llama-cli failed with code {result.returncode}')
            return {
                'schema_version': '2.0',
                'task_id': task_id,
                'source': WORKER_ID,
                'payload': {'verdict': 'FAIL', 'message': f'llama-cli crashed with code {result.returncode}'}
            }
            
        output = result.stdout.strip()
        # Attempt to parse json from the output
        try:
            # We forced it to start with {"status": "ok", "response": "
            # So if we prepend the '{' we might get valid JSON, or we can just return it raw
            parsed = json.loads(output)
            verdict = 'PASS'
            message = parsed
        except json.JSONDecodeError:
            verdict = 'FAIL'
            message = f"Invalid JSON output: {output}"
            
        result_payload = {'verdict': verdict, 'message': message}
        
    except Exception as e:
        logger.error(f"Execution error: {e}")
        result_payload = {'verdict': 'FAIL', 'message': str(e)}

    return {
        'schema_version': '2.0',
        'task_id': task_id,
        'source': WORKER_ID,
        'payload': result_payload
    }

def submit_result(result):
    try:
        http_post('api/v1/worker/submit', result)
        logger.info(f'Successfully submitted result for {result["task_id"]}')
        return True
    except Exception as e:
        logger.error(f'Failed to submit result: {e}')
        return False

def main():
    logger.info(f'Starting worker {WORKER_ID} connecting to {SERVER_URL}')
    logger.info(f'Capabilities: {CAPABILITIES}')
    
    backoff = 1
    while True:
        try:
            task = poll_for_task()
            if task and task.get('task_id'):
                backoff = 1
                result = execute_task(task)
                submit_result(result)
            else:
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 30)
        except KeyboardInterrupt:
            logger.info('Shutting down')
            break
        except Exception as e:
            logger.error(f'Unexpected error in loop: {e}')
            time.sleep(backoff)
            backoff = min(backoff * 1.5, 30)

if __name__ == '__main__':
    main()