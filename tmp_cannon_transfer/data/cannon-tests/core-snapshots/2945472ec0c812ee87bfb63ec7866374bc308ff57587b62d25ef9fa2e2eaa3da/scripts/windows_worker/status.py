#!/usr/bin/env python3
import sqlite3
import json
import os
import sys
from pathlib import Path
from datetime import datetime

def check_status():
    print("=== Windows Worker Local Queue Status ===")
    
    state_dir = Path(__file__).parent / 'state'
    db_path = state_dir / 'queue.db'
    
    if not db_path.exists():
        print(f"No local queue database found at {db_path}")
        return
        
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check Inbox
            cursor.execute("SELECT status, count(*) as c FROM inbox GROUP BY status")
            inbox_stats = cursor.fetchall()
            print("\n-- Inbox --")
            if not inbox_stats:
                print("  Empty")
            else:
                for row in inbox_stats:
                    print(f"  {row['status']}: {row['c']}")
                    
            # Check Outbox
            cursor.execute("SELECT status, count(*) as c FROM outbox GROUP BY status")
            outbox_stats = cursor.fetchall()
            print("\n-- Outbox --")
            if not outbox_stats:
                print("  Empty")
            else:
                for row in outbox_stats:
                    print(f"  {row['status']}: {row['c']}")
                    
            # Look for running tasks
            cursor.execute("SELECT task_id, added_at FROM inbox WHERE status = 'RUNNING'")
            running = cursor.fetchall()
            if running:
                print("\n-- Currently Running Tasks --")
                for row in running:
                    print(f"  Task ID: {row['task_id']}")
                    print(f"  Started: {row['added_at']}")
            
            # Look for stuck pending tasks in outbox
            cursor.execute("SELECT task_id, completed_at FROM outbox WHERE status = 'PENDING'")
            pending_outbox = cursor.fetchall()
            if pending_outbox:
                print("\n-- Pending Results to Send --")
                for row in pending_outbox:
                    print(f"  Task ID: {row['task_id']}")
                    print(f"  Completed: {row['completed_at']}")
                    
    except Exception as e:
        print(f"Error reading local queue: {e}")

if __name__ == '__main__':
    check_status()
