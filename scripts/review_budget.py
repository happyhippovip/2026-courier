class ReviewBudgetManager:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
    
    def evaluate_review_requirement(self, **kwargs):
        return {"decision": "NO_REVIEW"}
