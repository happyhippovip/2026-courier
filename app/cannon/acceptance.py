import json
import os
import shutil
import sys
from pathlib import Path
import uuid

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / 'tests'))

from cannon.adapters import LiveMuseAdapter
from cannon_support import SNAPSHOT, IsolatedCore, load_core, step
from cannon.importer import Importer
from cannon.storage import ROOT, atomic, digest, owned
from cannon.controller import Controller, resource_state

def run_acceptance():
    DEMO = owned(ROOT / 'data' / 'cannon-acceptance')
    if DEMO.exists(): shutil.rmtree(DEMO)
    DEMO.mkdir(parents=True, exist_ok=True)
    
    workspace = owned(DEMO / 'workspace'); workspace.mkdir(parents=True, exist_ok=True)
    
    os.chdir(workspace)
    api, verifier = load_core()
    core = IsolatedCore(api, verifier, DEMO / 'core')
    adapter = LiveMuseAdapter(SNAPSHOT / 'scripts/integration_contract.py', workspace)
    
    try:
        source = DEMO / 'tasks.jsonl'
        my_step = step('acceptance-01')
        my_step.pop('artifacts', None)
        my_step['target_capability'] = 'cannon.fake'
        my_step['worker_id'] = core.worker_ids[0]
        
        records = [{'id': 'acceptance-01', 'kind': 'TASK', 'task': my_step}]
        
        lines = [json.dumps(r, sort_keys=True, separators=(',', ':')) for r in records]
        serialized = "\n".join(lines) + "\n"
        source.write_text(serialized, encoding='utf-8')
        
        importer = Importer(DEMO / 'import')
        chk = importer.ingest(source, 'live-acceptance-' + uuid.uuid4().hex)
        
        receipt = importer.submit_authorized([(r['id'], digest(r)) for r in records], core, 'explicit-acceptance-start')
        core.goal_ids = [receipt['goal_id']]
        
        controller = Controller(DEMO / 'controller', core, adapter, mode='NORMAL', resources=resource_state)
        controller.control('RESUME')
        state = controller.run(max_starts=10)
        
        packet = {
            'kind': 'WINDOWS_CANNON_V1_ACCEPTANCE_PACKET',
            'status': 'SUCCESS' if state['metrics']['DONE'] == 1 else 'FAILED',
            'controller_state': state,
            'goal_id': receipt['goal_id']
        }
        atomic(ROOT / 'WINDOWS_CANNON_V1_ACCEPTANCE_PACKET.md', 
               f"# WINDOWS CANNON V1 ACCEPTANCE PACKET\n\n```json\n{json.dumps(packet, indent=2)}\n```\n")
        
        print("Acceptance done. Status:", packet['status'])
        
    finally:
        adapter.close()
        core.close()

if __name__ == '__main__':
    run_acceptance()
