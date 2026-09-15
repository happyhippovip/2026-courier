import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from next_safe_work_router import NextSafeWorkRouter, COURIER_DIR
router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
res = router.evaluate_next_safe_work()
import json
print(json.dumps(res, indent=2))
