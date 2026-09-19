import subprocess
import sys
import time
import json
import psutil
from pathlib import Path
import tempfile
import os

print("--- CANNON START PATH ANALYSIS ---")
print("1. UI-Prozess: browser (Chrome/Edge) or Node.js (operator-surface)")
print("2. Cannon Controller: scripts/windows_worker/daemon.py")
print("3. Wrapper/Launcher: powershell.exe (-NoProfile -NonInteractive -Command -)")
print("4. Tatsächlicher Python Worker/Child: python.exe (spawned inside powershell)")
print("PID/Start time info can be fetched via psutil.")

