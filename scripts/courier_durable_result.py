import sqlite3
import json
from dataclasses import dataclass, asdict
from typing import Optional, List

class AmbiguousResultError(RuntimeError):
    pass

class MalformedResultError(ValueError):
    pass

@dataclass
class DurableResult:
    goal_id: str
    task_id: str
    attempt_id: int
    worker_id: str
    provider: str
    session_identity: str
    input_identity: str
    result_state: str
    result_refs: List[str]
    commit_identity: Optional[str]
    started_at: str
    finished_at: str
    effect_classification: str
    verification_required: bool
    human_gate: str
    error_identity: Optional[str]

    def validate(self):
        if not self.goal_id or not self.task_id or self.attempt_id is None:
            raise MalformedResultError("Missing primary identity fields")
        if not self.worker_id or not self.provider or not self.session_identity:
            raise MalformedResultError("Missing worker/session identity fields")
        if not self.result_state or not self.effect_classification:
            raise MalformedResultError("Missing state/effect classification")

class DurableResultLedger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS durable_results (
                    task_id TEXT,
                    attempt_id INTEGER,
                    goal_id TEXT,
                    worker_id TEXT,
                    provider TEXT,
                    session_identity TEXT,
                    input_identity TEXT,
                    result_state TEXT,
                    result_refs TEXT,
                    commit_identity TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    effect_classification TEXT,
                    verification_required INTEGER,
                    human_gate TEXT,
                    error_identity TEXT,
                    PRIMARY KEY (task_id, attempt_id)
                )
            """)

    def record_result(self, result: DurableResult):
        result.validate()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            
            cursor.execute("SELECT * FROM durable_results WHERE task_id=? AND attempt_id=?", 
                           (result.task_id, result.attempt_id))
            existing = cursor.fetchone()
            
            # Serialize refs to JSON string for comparison and storage
            refs_json = json.dumps(result.result_refs)
            
            if existing:
                # Map row back to dict for easy comparison
                cols = [col[0] for col in cursor.description]
                existing_dict = dict(zip(cols, existing))
                
                # Check for exact match (Idempotency)
                # Note: sqlite booleans are 0/1
                is_match = (
                    existing_dict['goal_id'] == result.goal_id and
                    existing_dict['worker_id'] == result.worker_id and
                    existing_dict['provider'] == result.provider and
                    existing_dict['session_identity'] == result.session_identity and
                    existing_dict['input_identity'] == result.input_identity and
                    existing_dict['result_state'] == result.result_state and
                    existing_dict['result_refs'] == refs_json and
                    existing_dict['commit_identity'] == result.commit_identity and
                    existing_dict['started_at'] == result.started_at and
                    existing_dict['finished_at'] == result.finished_at and
                    existing_dict['effect_classification'] == result.effect_classification and
                    bool(existing_dict['verification_required']) == result.verification_required and
                    existing_dict['human_gate'] == result.human_gate and
                    existing_dict['error_identity'] == result.error_identity
                )
                
                if is_match:
                    return # Idempotent replay, safe to ignore
                else:
                    raise AmbiguousResultError(f"Conflicting result for {result.task_id} attempt {result.attempt_id}")
            
            cursor.execute("""
                INSERT INTO durable_results (
                    task_id, attempt_id, goal_id, worker_id, provider, session_identity,
                    input_identity, result_state, result_refs, commit_identity,
                    started_at, finished_at, effect_classification, verification_required,
                    human_gate, error_identity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.task_id, result.attempt_id, result.goal_id, result.worker_id,
                result.provider, result.session_identity, result.input_identity,
                result.result_state, refs_json, result.commit_identity, result.started_at,
                result.finished_at, result.effect_classification, 
                1 if result.verification_required else 0,
                result.human_gate, result.error_identity
            ))
