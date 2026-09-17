import re
import glob

def patch_file(path):
    with open(path, "r") as f:
        code = f.read()
    
    def replacer(match):
        inner = match.group(1)
        if "timeout=" not in inner:
            return f"subprocess.run({inner}, timeout=60)"
        return match.group(0)
        
    new_code = re.sub(r'subprocess\.run\((.*?)\)', replacer, code, flags=re.DOTALL)
    
    if new_code != code:
        with open(path, "w") as f:
            f.write(new_code)
        print(f"Patched {path}")

for f in glob.glob("tests/**/*.py", recursive=True):
    patch_file(f)

