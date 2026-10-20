import os
import shutil
import tempfile
import psutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OWNED_TEMP_PREFIXES = ("scoped_dir", "courier_tmp_", ".outbox-", ".crash-")
OWNED_DRIVER_NAMES = frozenset({"msedgedriver.exe", "chromedriver.exe", "msedgedriver", "chromedriver"})


def _is_owned_temp_entry(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in OWNED_TEMP_PREFIXES)


def cleanup_temp_if_large(max_size_gb: float = 1.0, temp_dir: Optional[str] = None) -> int:
    """
    Cleans up only Courier/WebDriver-owned entries inside the %TEMP% directory
    if their combined size exceeds the specified maximum size. Never deletes
    arbitrary user or system files in %TEMP%.
    """
    target_temp = temp_dir or tempfile.gettempdir()
    if not os.path.isdir(target_temp):
        return 0

    owned_entries = []
    total_size = 0
    try:
        for entry in os.scandir(target_temp):
            if not _is_owned_temp_entry(entry.name):
                continue
            owned_entries.append(entry.path)
            if entry.is_symlink():
                continue
            if entry.is_file(follow_symlinks=False):
                total_size += entry.stat(follow_symlinks=False).st_size
            elif entry.is_dir(follow_symlinks=False):
                for dirpath, _, filenames in os.walk(entry.path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        if not os.path.islink(fp):
                            try:
                                total_size += os.path.getsize(fp)
                            except OSError:
                                pass
    except Exception as e:
        logger.warning(f"Error calculating owned TEMP size: {e}")
        return 0

    total_gb = total_size / (1024 * 1024 * 1024)
    logger.debug(f"Current owned TEMP size: {total_gb:.2f} GB")

    removed_count = 0
    if total_gb > max_size_gb:
        logger.info(
            f"Owned TEMP size ({total_gb:.2f} GB) exceeds limit ({max_size_gb} GB). Cleaning owned entries..."
        )
        for path in owned_entries:
            try:
                if os.path.islink(path) or os.path.isfile(path):
                    os.remove(path)
                    removed_count += 1
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    removed_count += 1
            except OSError:
                pass
        logger.info("TEMP cleanup finished.")
    return removed_count


def terminate_orphaned_drivers() -> int:
    """
    Terminates only orphaned WebDriver processes (chromedriver/msedgedriver) whose parent
    process no longer exists. Never targets user browsers (chrome.exe / msedge.exe) or
    processes parented by explorer.exe.
    """
    logger.info("Checking for orphaned WebDriver processes...")
    terminated = 0

    for proc in psutil.process_iter(["pid", "name", "ppid"]):
        try:
            proc_name = (proc.info.get("name") or "").lower()
            if proc_name not in OWNED_DRIVER_NAMES:
                continue
            ppid = proc.info.get("ppid")
            is_orphan = False
            if ppid == 1 and os.name != "nt":
                is_orphan = True
            elif ppid:
                try:
                    parent = psutil.Process(ppid)
                    # Never kill anything parented by explorer.exe or an active parent
                    if parent.name().lower() == "explorer.exe" or parent.is_running():
                        is_orphan = False
                except psutil.NoSuchProcess:
                    is_orphan = True
                except psutil.AccessDenied:
                    is_orphan = False

            if is_orphan:
                logger.info(f"Terminating orphaned driver {proc.info['name']} (PID: {proc.info['pid']})")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
                terminated += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return terminated


def run_sweeper():
    cleanup_temp_if_large()
    terminate_orphaned_drivers()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_sweeper()
