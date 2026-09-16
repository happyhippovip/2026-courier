import subprocess
import os
import time
import signal

def get_process_tree():
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,ppid,pcpu,pmem,command"]).decode("utf-8")
    except Exception:
        return []
    
    processes = []
    lines = out.strip().split('\n')
    if len(lines) <= 1:
        return []
        
    for line in lines[1:]:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            pcpu = float(parts[2])
            pmem = float(parts[3])
            cmd = parts[4]
            processes.append({
                "pid": pid,
                "ppid": ppid,
                "pcpu": pcpu,
                "pmem": pmem,
                "cmd": cmd
            })
        except ValueError:
            continue
    return processes

def enforce_resource_safety():
    procs = get_process_tree()
    
    my_pid = os.getpid()
    
    # 1. Identify all Courier/Antigravity owned processes
    courier_procs = []
    for p in procs:
        cmd_lower = p['cmd'].lower()
        if "courier" in cmd_lower or "agy" in cmd_lower or "antigravity" in cmd_lower:
            # Exclude our own grep / ps commands and the Antigravity UI app
            if "grep" not in cmd_lower and "ps -eo" not in cmd_lower and "/users/user/desktop/antigravity" not in cmd_lower:
                courier_procs.append(p)
                
    orphans_killed = 0
    top_cpu = ""
    top_mem = ""
    throttled = False
    
    # Check for excessive CPU/MEM among courier procs
    total_cpu = 0.0
    for p in courier_procs:
        total_cpu += p['pcpu']
        
    if total_cpu > 150.0: # e.g. 1.5 cores purely for background workers
        throttled = True

    # 2. Detect orphans
    # An orphan is a process whose PPID is 1 (init) AND it's a worker/limit_wrapper/agy process
    # Or if its parent is no longer a courier process or alive
    alive_pids = {p['pid'] for p in procs}
    
    for p in courier_procs:
        if p['pid'] == my_pid:
            continue # Don't kill ourselves
            
        # Is it an orphan?
        is_orphan = False
        if p['ppid'] == 1:
            is_orphan = True
        elif p['ppid'] not in alive_pids:
            is_orphan = True
            
        # Also kill if it's another daemon.py (Duplicate worker protection!)
        if "daemon.py" in p['cmd'] and p['pid'] != my_pid:
            # duplicate worker!
            is_orphan = True
            
        if is_orphan and ("limit_wrapper.sh" in p['cmd'] or "agy" in p['cmd'] or "daemon.py" in p['cmd']):
            # Terminate exactly this PID
            try:
                os.kill(p['pid'], signal.SIGTERM)
                orphans_killed += 1
            except ProcessLookupError:
                pass
                
    # Hard kill after grace
    if orphans_killed > 0:
        time.sleep(2)
        procs_after = get_process_tree()
        for p in procs_after:
            cmd_lower = p['cmd'].lower()
            if p['pid'] != my_pid and ("limit_wrapper.sh" in cmd_lower or "agy" in cmd_lower or "daemon.py" in cmd_lower):
                if p['ppid'] == 1 or p['ppid'] not in alive_pids or ("daemon.py" in cmd_lower):
                    try:
                        os.kill(p['pid'], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                        
    if courier_procs:
        top_cpu_proc = max(courier_procs, key=lambda x: x['pcpu'])
        top_mem_proc = max(courier_procs, key=lambda x: x['pmem'])
        top_cpu = f"PID {top_cpu_proc['pid']} ({top_cpu_proc['pcpu']}%) - {top_cpu_proc['cmd'][:30]}"
        top_mem = f"PID {top_mem_proc['pid']} ({top_mem_proc['pmem']}%) - {top_mem_proc['cmd'][:30]}"

    return {
        "throttled": throttled,
        "top_cpu": top_cpu,
        "top_mem": top_mem,
        "orphans_killed": orphans_killed
    }
