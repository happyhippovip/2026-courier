import re
import glob

def patch_file(path):
    with open(path, "r") as f:
        code = f.read()
    
    def replacer(match):
        method = match.group(1)
        inner = match.group(2)
        if "timeout=" not in inner:
            return f"requests.{method}({inner}, timeout=30)"
        return match.group(0)
        
    new_code = re.sub(r'requests\.(get|post|put|delete|patch|head|options)\((.*?)\)', replacer, code, flags=re.DOTALL)
    
    if new_code != code:
        with open(path, "w") as f:
            f.write(new_code)
        print(f"Patched {path}")

for f in glob.glob("scripts/**/*.py", recursive=True):
    patch_file(f)

