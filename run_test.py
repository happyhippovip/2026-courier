import tempfile
import pathlib
import traceback
from tests.test_build_antigravity_worker_job_uncovered import test_build_worker_job_missing_coverage

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    try:
        test_build_worker_job_missing_coverage(pathlib.Path(d))
        print("SUCCESS")
    except Exception as e:
        traceback.print_exc()
