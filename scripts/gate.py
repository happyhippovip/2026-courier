import os
import time

def _parse_env_int(key, default=None):
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        parsed = int(val)
        if parsed <= 0:
            return default
        return parsed
    except ValueError:
        return default

def gate(start_time, tasks_done, consecutive_errors, idle_seconds=0, task_seconds=0):
    """
    Checks various limits and returns a stop reason if a limit is exceeded, 
    otherwise returns None.
    
    Environment limits:
    LIMIT_ZEIT: Max total execution time in seconds.
    LIMIT_KONTINGENT: Max total tasks.
    SERIENFEHLER: Max consecutive errors.
    IDLE_SECONDS: Max idle time.
    TASK_SECONDS: Max time for a single task.
    """
    limit_zeit = _parse_env_int("LIMIT_ZEIT")
    limit_kontingent = _parse_env_int("LIMIT_KONTINGENT")
    serienfehler = _parse_env_int("SERIENFEHLER")
    limit_idle = _parse_env_int("IDLE_SECONDS")
    limit_task = _parse_env_int("TASK_SECONDS")
    
    if limit_zeit is not None:
        if time.time() - start_time >= limit_zeit:
            return "LIMIT_ZEIT_REACHED"
            
    if limit_kontingent is not None:
        if tasks_done >= limit_kontingent:
            return "LIMIT_KONTINGENT_REACHED"
            
    if serienfehler is not None:
        if consecutive_errors >= serienfehler:
            return "SERIENFEHLER_REACHED"
            
    if limit_idle is not None:
        if idle_seconds >= limit_idle:
            return "IDLE_SECONDS_REACHED"
            
    if limit_task is not None:
        if task_seconds >= limit_task:
            return "TASK_SECONDS_REACHED"
            
    return None
