import os
import shutil
import tempfile
import psutil
import logging

logger = logging.getLogger(__name__)

def cleanup_temp_if_large(max_size_gb: float = 1.0):
    """
    Cleans up the %TEMP% directory if it exceeds the specified maximum size.
    """
    temp_dir = tempfile.gettempdir()
    
    # Calculate size
    total_size = 0
    try:
        for dirpath, _, filenames in os.walk(temp_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except Exception as e:
        logger.warning(f"Error calculating TEMP size: {e}")
        return

    total_gb = total_size / (1024 * 1024 * 1024)
    logger.debug(f"Current TEMP size: {total_gb:.2f} GB")

    if total_gb > max_size_gb:
        logger.info(f"TEMP size ({total_gb:.2f} GB) exceeds limit ({max_size_gb} GB). Cleaning up...")
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for name in files:
                try:
                    os.remove(os.path.join(root, name))
                except OSError:
                    pass
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except OSError:
                    pass
        logger.info("TEMP cleanup finished.")

def terminate_orphaned_drivers():
    """
    Terminates orphaned edge and chrome driver processes.
    """
    target_names = ["msedgedriver.exe", "chromedriver.exe", "msedge.exe", "chrome.exe"]
    logger.info("Checking for orphaned browser and driver processes...")
    
    for proc in psutil.process_iter(['pid', 'name', 'ppid']):
        try:
            if proc.info['name'] and proc.info['name'].lower() in target_names:
                try:
                    parent = psutil.Process(proc.info['ppid'])
                    if parent.name().lower() == 'explorer.exe' or proc.info['ppid'] == 1:
                        # Process might be an orphan if parent is explorer or init
                        logger.info(f"Terminating suspected orphaned process {proc.info['name']} (PID: {proc.info['pid']})")
                        proc.terminate()
                        proc.wait(timeout=3)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    try:
                        proc.kill()
                    except:
                        pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def run_sweeper():
    cleanup_temp_if_large()
    terminate_orphaned_drivers()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_sweeper()
