import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, LocalWorkerAdapterBoundary

boundary = LocalWorkerAdapterBoundary(workspace_dir=Path(".").resolve())
dispatcher = CourierSafetyDispatcher(workspace_dir=Path(".").resolve(), adapter_boundary=boundary)

try:
    dispatcher.reconcile_orphans()
except Exception as e:
    print("TOP LEVEL EXCEPTION:", repr(e))
