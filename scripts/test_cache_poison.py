import py_compile
import os
import sys
import importlib

# 1. Create a dummy module
module_code_v1 = "def get_state(): return 'V1_STATE'"
with open("poison_test.py", "w") as f:
    f.write(module_code_v1)

# 2. Compile to .pyc (forces cache generation)
py_compile.compile("poison_test.py", cfile="__pycache__/poison_test.pyc")

# 3. Modify the source to simulate a code update
module_code_v2 = "def get_state(): return 'V2_STATE'"
with open("poison_test.py", "w") as f:
    f.write(module_code_v2)

# 4. Import and see if we bleed state
import poison_test

# 5. Output the result
print(f"Resulting State: {poison_test.get_state()}")
