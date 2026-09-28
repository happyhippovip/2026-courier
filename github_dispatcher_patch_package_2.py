import os
import sys

def apply_patch():
    path = "scripts/courier_github_dispatcher.py"
    if not os.path.exists(path):
        print(f"{path} not found")
        sys.exit(1)
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    old_block = """                if json.loads(state_file.read_text(encoding="utf-8")).get("status") == "POSTED":
                    continue"""
                    
    new_block = """                status = json.loads(state_file.read_text(encoding="utf-8")).get("status")
                if status in ("POSTED", "POSTED_FAILED"):
                    continue"""
                            
    if old_block not in content:
        if "POSTED_FAILED" in content and "status in" in content:
            print("Patch already applied.")
            return
        print("Could not find the target block to patch.")
        sys.exit(1)
        
    patched = content.replace(old_block, new_block)
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    print("Patch successfully applied to courier_github_dispatcher.py")

if __name__ == "__main__":
    apply_patch()
