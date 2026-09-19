from tests.test_antigravity_continuous import test_antigravity_continuous_queue_participation
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
    test_antigravity_continuous_queue_participation(Path(tmp))
