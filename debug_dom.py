import sys
from pathlib import Path
import json

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "tests"))
import test_cannon_yolo
test_cannon_yolo.ROOT = ROOT

st = test_cannon_yolo.STATUS
print(test_cannon_yolo.dom(test_cannon_yolo.new_js(), st, ROOT / "tmp"))
