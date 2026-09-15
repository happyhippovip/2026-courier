import os
import time
import sys
import logging
import argparse
from datetime import datetime, timezone

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from chief.scheduled_cycle import execute_windows_validation_cycle
from chief.control_plane import ControlPlane

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("linux_daemon")

def run_daemon(poll_interval: int):
    logger.info(f"Starting Courier linux daemon. Poll interval: {poll_interval}s")
    cp = ControlPlane()
    
    # Ensure environment variables are loaded if configured via shell
    
    while True:
        try:
            res = execute_windows_validation_cycle(cp=cp)
            status = res.get("cycle_status")
            
            # Quiescent state optimization
            if status == "QUIESCENT":
                # Do nothing, just sleep
                time.sleep(poll_interval)
            elif status == "ACTIVE_REQUEST_IN_FLIGHT":
                logger.info(f"Active request in flight: {res.get('mission_id')} - {res.get('windows_validation_request_id')}")
                time.sleep(poll_interval)
            elif status == "GOAL_TASK_EXECUTED":
                logger.info(f"Executed autonomous goal task: {res.get('autonomous_result')}")
                # Don't sleep much if we just executed a task
                time.sleep(1)
            else:
                logger.info(f"Cycle completed with status: {status}")
                time.sleep(poll_interval)
                
        except Exception as e:
            logger.error(f"Error during validation cycle: {e}", exc_info=True)
            # Sleep longer on error to prevent tight crash loop
            time.sleep(poll_interval * 2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Courier Linux Headless Daemon")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    args = parser.parse_args()
    
    run_daemon(args.interval)
