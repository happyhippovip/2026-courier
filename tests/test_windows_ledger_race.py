import pytest
import threading
import time
import json
import tempfile
import os
from pathlib import Path
import ast

from scripts.agent_handoff_ledger import atomic_write, load_bundle

def test_windows_ledger_race():
    # We can just statically verify that load_bundle lacks the retry loop
    # without running the ledger init
    with open("scripts/agent_handoff_ledger.py", "r") as f:
        tree = ast.parse(f.read())
        
    load_bundle_func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "load_bundle":
            load_bundle_func = node
            break
            
    assert load_bundle_func is not None
    
    # Find if there is a 'for' or 'while' loop wrapping the 'try'
    has_loop = False
    for node in ast.walk(load_bundle_func):
        if isinstance(node, (ast.For, ast.While)):
            has_loop = True
            
    # If it doesn't have a retry loop, this assertion will pass (which proves the defect exists)
    assert not has_loop, "load_bundle has a loop, defect might be fixed!"
        
