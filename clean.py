import os, glob
for pattern in ["coordination/mac_to_windows/opportunities.json", "events/opportunity-queue/*.json", "coordination/windows_to_mac/results/*.json", "coordination/local_requests/*.json", "coordination/mac_to_windows/acks/*.json", "coordination/mac_to_windows/archive/*.json"]:
    for f in glob.glob(pattern):
        try:
            os.remove(f)
        except Exception:
            pass
