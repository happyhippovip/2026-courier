with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

load_logic = """
            # Resource / Heat protection
            load1, load5, load15 = os.getloadavg()
            is_hot = load1 > 8.0  # Simple threshold for max local executions/pressure
            payload_hb = {"worker_id": config["WORKER_ID"]}
            if is_hot:
                write_log(f"System is hot (load {load1:.2f}). Pausing claims.")
                payload_hb["available"] = False
"""
c = c.replace("""            # Heartbeat
            res, err = http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})""", 
            """            # Heartbeat""" + load_logic + """
            res, err = http_post(config, "/workers/heartbeat", payload_hb)""")

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(c)
