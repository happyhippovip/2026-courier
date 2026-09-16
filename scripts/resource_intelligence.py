class ResourceIntelligenceManager:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
    
    def classify_process(self, *args, **kwargs):
        return "UNKNOWN"
        
    def context_for_role(self, *args, **kwargs):
        return {}
