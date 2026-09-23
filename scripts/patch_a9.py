from pathlib import Path

motor_path = Path("scripts/cannon_motor.py")
content = motor_path.read_text()
if "SINGLETON_LOCK_FAILED" not in content:
    content = content.replace(
        '''    def __init__(self, state_dir, behaviors=None, hooks=None):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir = self.state_dir / "results"
        self.motor_file = self.state_dir / "motor.json"
        self.behaviors = behaviors or {}
        self.hooks = hooks or {}
        self._load()''',
        '''    def __init__(self, state_dir, behaviors=None, hooks=None):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir = self.state_dir / "results"
        self.motor_file = self.state_dir / "motor.json"
        
        try:
            import fcntl
            self.lock_file = open(self.state_dir / ".singleton.lock", "w")
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError) as exc:
            raise MotorError("SINGLETON_LOCK_FAILED") from exc
            
        self.behaviors = behaviors or {}
        self.hooks = hooks or {}
        self._load()'''
    )
    motor_path.write_text(content)
