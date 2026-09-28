import os
import sys

def apply_patch():
    path = "scripts/revenue_worker_adapter.py"
    if not os.path.exists(path):
        print(f"{path} not found")
        sys.exit(1)
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    patched = content.replace("import urllib.request, json\n                    req", "import urllib.request\n                    req")
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    print("Patch successfully applied to revenue_worker_adapter.py (fix local json)")

if __name__ == "__main__":
    apply_patch()
