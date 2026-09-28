#!/usr/bin/env python3
import json
import os
import sqlite3
import hashlib
from datetime import datetime

JSONL_PATH = "ops/ai/wall_ledger/ledger.jsonl"
DB_PATH = "ops/ai/wall_ledger/ledger.db"

def init_db(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL,
            evidence_path TEXT,
            fingerprint TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            block_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

def compute_block_hash(task_id, status, evidence_path, fingerprint, prev_hash):
    raw = f"{task_id}|{status}|{evidence_path}|{fingerprint}|{prev_hash}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def migrate():
    if not os.path.exists(JSONL_PATH):
        print(f"No JSONL ledger found at {JSONL_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    cursor = conn.cursor()
    
    # Check if empty
    cursor.execute("SELECT COUNT(*) FROM ledger")
    if cursor.fetchone()[0] > 0:
        print("Database already populated. Skipping migration.")
        return

    print("Migrating JSONL to cryptographic SQLite ledger (Blockchain structure)...")
    
    prev_hash = "GENESIS_BLOCK_00000000000000000000000000000000"
    count = 0
    
    with open(JSONL_PATH, 'r') as f:
        for line in f:
            if not line.strip(): continue
            data = json.loads(line.strip())
            task_id = data.get("TASK_ID", "UNKNOWN")
            status = data.get("STATUS", "UNKNOWN")
            evidence_path = data.get("EVIDENCE_PATH", "")
            fingerprint = data.get("FINGERPRINT", "")
            
            block_hash = compute_block_hash(task_id, status, evidence_path, fingerprint, prev_hash)
            
            try:
                cursor.execute('''
                    INSERT INTO ledger (task_id, status, evidence_path, fingerprint, prev_hash, block_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (task_id, status, evidence_path, fingerprint, prev_hash, block_hash))
                prev_hash = block_hash
                count += 1
            except sqlite3.IntegrityError:
                # task_id must be unique
                pass
                
    conn.commit()
    print(f"Successfully migrated {count} entries to {DB_PATH}")
    
    # Backup old jsonl
    backup_path = f"{JSONL_PATH}.migrated.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    os.rename(JSONL_PATH, backup_path)
    print(f"Archived old JSONL to {backup_path}")

if __name__ == "__main__":
    migrate()
