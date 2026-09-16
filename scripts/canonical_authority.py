class CanonicalAuthority:
    def acquire_scopes(self, owner_id, task_id, scopes):
        return True, 1, None
    
    def release_scopes(self, owner_id, task_id, scopes):
        return True, 1, None
        
    def acquire_heavy_authority(self, owner_id, task_id, metadata):
        return True, 1, None
        
    def release_heavy_authority(self, owner_id, task_id, metadata):
        return True, 1, None
