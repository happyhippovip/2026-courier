import unittest
import sys
import time

def run_tests():
    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    for test in suite:
        print(f"Running {test}...")
        sys.stdout.flush()
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(test)

if __name__ == "__main__":
    run_tests()
