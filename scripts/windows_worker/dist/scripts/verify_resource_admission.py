import psutil
import sys

def verify_resource_admission(min_cpu_percent_idle=20, min_memory_mb=512, min_disk_mb=1024):
    errors = []
    
    # 1. CPU
    cpu_usage = psutil.cpu_percent(interval=1)
    if cpu_usage > (100 - min_cpu_percent_idle):
        errors.append(f"CPU is too busy: {cpu_usage}% used.")
        
    # 2. RAM
    mem = psutil.virtual_memory()
    free_mb = mem.available / (1024 * 1024)
    if free_mb < min_memory_mb:
        errors.append(f"Not enough RAM available: {free_mb:.2f} MB (Required: {min_memory_mb} MB).")
        
    # 3. Disk
    disk = psutil.disk_usage('/')
    free_disk_mb = disk.free / (1024 * 1024)
    if free_disk_mb < min_disk_mb:
        errors.append(f"Not enough Disk space: {free_disk_mb:.2f} MB (Required: {min_disk_mb} MB).")
        
    if not errors:
        print("RESOURCE ADMISSION VALID: Host is ready for heavy jobs.")
        sys.exit(0)
    else:
        print("RESOURCE ADMISSION FAILED (BACKOFF REQUIRED):")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)

if __name__ == "__main__":
    verify_resource_admission()
