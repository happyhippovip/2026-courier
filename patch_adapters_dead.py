import re

with open("app/cannon/adapters.py", "r") as f:
    content = f.read()

# 1. Remove unused digest import
content = content.replace("from .storage import ROOT, atomic, digest, owned, read", "from .storage import ROOT, atomic, owned, read")

# 2. Remove tempfile in execute_canary
content = content.replace("        import tempfile\n", "")

# 3. Replace LiveMuseAdapter.execute body
start_idx = content.find("    def execute(self, task, folder, persist_identity):\n        raise ValueError('LEGACY_EXIT_ONLY_ADAPTER_DISABLED_USE_VERIFIED_CANARY')")
if start_idx != -1:
    end_idx = content.find("    def cancel(self, execution_id):", start_idx)
    if end_idx != -1:
        new_execute = "    def execute(self, task, folder, persist_identity):\n        raise ValueError('LEGACY_EXIT_ONLY_ADAPTER_DISABLED_USE_VERIFIED_CANARY')\n\n"
        content = content[:start_idx] + new_execute + content[end_idx:]
        print("Patched execute!")
    else:
        print("End not found")
else:
    print("Start not found")

with open("app/cannon/adapters.py", "w") as f:
    f.write(content)
