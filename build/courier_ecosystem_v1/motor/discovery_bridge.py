import sqlite3
import time
import uuid
import sys
from pathlib import Path
import json

scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))
try:
    from general_engineering_discovery_engine import GeneralEngineeringDiscoveryEngine
except ImportError:
    GeneralEngineeringDiscoveryEngine = None

def run_discovery_pass(conn):
    if not GeneralEngineeringDiscoveryEngine:
        return
        
    try:
        engine = GeneralEngineeringDiscoveryEngine(repo_dir=Path(scripts_dir.parent))
        candidates, _, _ = engine.run_general_discovery()
        
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS discovery_history (fingerprint TEXT PRIMARY KEY, created_at REAL)")
        
        for cand in candidates:
            fp = cand.task_id
            c.execute("SELECT 1 FROM discovery_history WHERE fingerprint=?", (fp,))
            if not c.fetchone():
                c.execute("INSERT INTO discovery_history (fingerprint, created_at) VALUES (?, ?)", (fp, time.time()))
                
                tid = f"task_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}"
                
                inst = f"echo 'Executing {cand.task_type}: {cand.evidence_location}' > scratch/{fp}.done"
                eff = f"scratch/{fp}.done"
                    
                priority = 5
                if cand.task_type == "SAFE_LOCAL_ENGINEERING":
                    priority = 10
                    
                c.execute("INSERT INTO tasks (task_id, status, instruction, expected_effects, priority) VALUES (?, 'PENDING', ?, ?, ?)", 
                          (tid, inst, json.dumps(eff), priority))
                print(f"[DiscoveryBridge] Discovered and inserted real task: {tid}")
                
        conn.commit()
    except Exception as e:
        import traceback
        print(f"[DiscoveryBridge] Error: {e}\n{traceback.format_exc()}")
