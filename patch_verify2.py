import os

for root, _, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                code = f.read()
            
            if '"received_runtime_identity": "test"' in code:
                # Some tests might have task available, but how do we know?
                # Actually, in most tests that I broke, they just need to use the actual server binding.
                pass

