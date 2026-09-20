import re

with open("scripts/run_snitch_watchdog.py", "r") as f:
    content = f.read()

replacement = """try:
    from resource_intelligence import ResourceIntelligenceManager
except ImportError:
    try:
        from scripts.resource_intelligence import ResourceIntelligenceManager
    except ImportError:
        class ResourceIntelligenceManager:
            def __init__(self, repo_dir): pass
            def classify_process(self, *args, **kwargs): return "UNKNOWN_RESOURCE_CLASSIFICATION"
            def context_for_role(self, *args, **kwargs): return {}"""

content = re.sub(
    r'try:\s*from resource_intelligence import ResourceIntelligenceManager\s*except ImportError:\s*from scripts.resource_intelligence import ResourceIntelligenceManager',
    replacement,
    content,
    flags=re.MULTILINE
)

with open("scripts/run_snitch_watchdog.py", "w") as f:
    f.write(content)
