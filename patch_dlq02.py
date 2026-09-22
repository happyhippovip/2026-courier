with open("tests/test_DLQ02_freshness_bound.py", "r") as f:
    c = f.read()

# Remove the static import
c = c.replace("from dlq01_refresh import record as base_record, base_guard", "")

# Add dynamic import function
get_base_code = """
def get_base():
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("dlq01_refresh", "/tmp/dlq01_refresh.py")
    dlq = importlib.util.module_from_spec(spec)
    sys.modules["dlq01_refresh"] = dlq
    spec.loader.exec_module(dlq)
    return dlq.record, dlq.base_guard
"""
c = c.replace('sys.path.insert(0, "/tmp")', 'sys.path.insert(0, "/tmp")\n' + get_base_code)

# Replace all rec = base_record() with the dynamic version
c = c.replace("rec = base_record()", "base_record, base_guard = get_base()\n    rec = base_record()")

with open("tests/test_DLQ02_freshness_bound.py", "w") as f:
    f.write(c)
